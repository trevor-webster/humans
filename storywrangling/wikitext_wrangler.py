from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

import pandas as pd
try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storywrangling.storywrangler import (
    lowercase_and_count_ngrams,
    write_counts_csv,
)


DEFAULT_INPUT = Path(r"c:\Users\twebster\Desktop\PoCS\wikitext\wikitext-103-raw-v1")


def is_lfs_pointer(path: Path) -> bool:
    if path.stat().st_size > 1024:
        return False

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    return text.startswith("version https://git-lfs.github.com/spec/v1")


def iter_parquet_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        paths = [input_path]
    else:
        paths = sorted(input_path.glob("*.parquet"))

    if not paths:
        raise FileNotFoundError(f"no parquet files found in: {input_path}")

    pointer_paths = [path for path in paths if is_lfs_pointer(path)]
    if pointer_paths:
        joined = ", ".join(path.name for path in pointer_paths[:3])
        raise RuntimeError(
            "Git LFS pointer files detected instead of real parquet data. "
            f"Run `git lfs pull` in the WikiText repo first. Example files: {joined}"
        )

    return paths


def normalize_wikitext_text(text: str) -> str:
    cleaned = "" if text is None else str(text)
    cleaned = re.sub(r"(?<=\S)\s*@-@\s*(?=\S)", "-", cleaned)
    cleaned = re.sub(r"(?<=\S)\s*@,@\s*(?=\S)", ",", cleaned)
    cleaned = re.sub(r"(?<=\S)\s*@\.@\s*(?=\S)", ".", cleaned)
    return cleaned


def count_text_ngrams(text: str, gram_size: int, filter_junk_tokens: bool) -> Counter[str]:
    normalized_text = normalize_wikitext_text(text)
    return lowercase_and_count_ngrams(
        normalized_text,
        ngram_size=gram_size,
        filter_junk_tokens=filter_junk_tokens,
    )


def iter_text_values(input_path: Path, batch_size: int) -> tuple[object, ...]:
    for parquet_path in iter_parquet_paths(input_path):
        if pq is not None:
            parquet_file = pq.ParquetFile(parquet_path)
            for batch in parquet_file.iter_batches(columns=["text"], batch_size=batch_size):
                yield from batch.column(0).to_pylist()
            continue

        frame = pd.read_parquet(parquet_path, columns=["text"])
        yield from frame["text"].tolist()


def default_output_path(
    input_path: Path,
    gram_size: int,
    output_format: str,
) -> Path:
    stem = input_path.stem if input_path.is_file() else input_path.name
    output_dir = PROJECT_ROOT / f"{gram_size}-gram"
    return output_dir / f"{stem}-{gram_size}grams.{output_format}"


def write_counts_parquet(counts: Counter[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(counts.most_common(), columns=["types", "counts"])
    frame.to_parquet(output_path, index=False)


def write_counts_output(counts: Counter[str], output_path: Path) -> None:
    suffix = output_path.suffix.casefold()
    if suffix == ".parquet":
        write_counts_parquet(counts, output_path)
        return
    if suffix == ".csv":
        write_counts_csv(counts, output_path)
        return
    raise ValueError(f"Unsupported output suffix: {output_path.suffix}. Use .csv or .parquet")


def build_counts(
    input_path: Path,
    gram_size: int,
    filter_junk_tokens: bool,
    min_count: int,
    batch_size: int,
) -> tuple[Counter[str], int]:
    counts: Counter[str] = Counter()
    processed_rows = 0

    for text in iter_text_values(input_path, batch_size=batch_size):
        processed_rows += 1
        source_text = "" if text is None else str(text)
        counts.update(count_text_ngrams(source_text, gram_size=gram_size, filter_junk_tokens=filter_junk_tokens))

    if min_count > 0:
        counts = Counter({token: count for token, count in counts.items() if count >= min_count})

    return counts, processed_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert WikiText parquet shards into the repo's n-gram CSV format. "
            "Defaults are tuned for wikitext-103-raw-v1 with no count cutoff."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to a WikiText parquet directory or a single parquet shard.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path. Supports .csv or .parquet. Defaults to 1-gram/ or 2-gram/ based on --gram-size.",
    )
    parser.add_argument(
        "--output-format",
        choices=["csv", "parquet"],
        default="csv",
        help="Default output format when --output is omitted. Default: csv",
    )
    parser.add_argument(
        "--gram-size",
        type=int,
        choices=[1, 2],
        default=1,
        help="Which n-gram size to build. Default: 1",
    )
    parser.add_argument(
        "--filter-junk-tokens",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Apply shared pre-count token filtering before counting to reduce memory use and keep "
            "book/wiki token rules aligned. Default: true"
        ),
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=0,
        help="Minimum count required to keep a token. Default: 0",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50000,
        help="Parquet batch size for streaming reads. Lower values use less memory. Default: 50000",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or default_output_path(
        input_path=input_path,
        gram_size=args.gram_size,
        output_format=args.output_format,
    )

    if not input_path.exists():
        parser.error(f"input path does not exist: {input_path}")

    counts, processed_rows = build_counts(
        input_path=input_path,
        gram_size=args.gram_size,
        filter_junk_tokens=args.filter_junk_tokens,
        min_count=args.min_count,
        batch_size=args.batch_size,
    )
    write_counts_output(counts, output_path)

    print(f"input:                  {input_path}")
    print(f"output:                 {output_path}")
    print(f"gram size:              {args.gram_size}")
    print(f"processed rows:         {processed_rows}")
    print(f"filter junk tokens:     {args.filter_junk_tokens}")
    print(f"min_count:              {args.min_count}")
    print(f"batch size:             {args.batch_size}")
    print(f"totalunique:            {len(counts)}")
    print(f"totalcounts:            {sum(counts.values())}")
    if output_path.suffix.casefold() == ".parquet":
        print("parquet columns:        types, counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
