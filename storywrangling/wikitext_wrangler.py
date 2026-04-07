from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storywrangling.storywrangler import lowercase_and_count_words, write_word_counts_csv


DEFAULT_INPUT = Path(r"c:\Users\twebster\Desktop\PoCS\wikitext\wikitext-103-raw-v1")
DEFAULT_OUTPUT = Path("1-gram/wikitext-103-raw-v1-1grams.csv")


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


def is_pure_punctuation(token: str) -> bool:
    return bool(token) and all(not char.isalnum() for char in token)


def is_apostrophe_fragment(token: str) -> bool:
    if "'" not in token:
        return False

    if token == "n't":
        return True

    if token.startswith("'") or token.endswith("'"):
        return any(char.isalpha() for char in token.replace("'", ""))

    return False


def apply_wiki_decisions(counts: Counter[str]) -> Counter[str]:
    filtered: Counter[str] = Counter()
    for token, count in counts.items():
        if is_pure_punctuation(token):
            continue
        if is_apostrophe_fragment(token):
            continue
        filtered[token] = count
    return filtered


def build_counts(
    input_path: Path,
    apply_decisions_rules: bool,
    min_count: int,
) -> tuple[Counter[str], int]:
    counts: Counter[str] = Counter()
    processed_rows = 0

    for parquet_path in iter_parquet_paths(input_path):
        frame = pd.read_parquet(parquet_path, columns=["text"])

        for text in frame["text"].fillna(""):
            processed_rows += 1
            source_text = text if isinstance(text, str) else str(text)
            counts.update(lowercase_and_count_words(source_text))

    if apply_decisions_rules:
        counts = apply_wiki_decisions(counts)

    if min_count > 0:
        counts = Counter({token: count for token, count in counts.items() if count >= min_count})

    return counts, processed_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert WikiText parquet shards into the repo's unigram CSV format. "
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
        default=DEFAULT_OUTPUT,
        help="CSV output path. Default: 1-gram/wikitext-103-raw-v1-1grams.csv",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=0,
        help="Minimum count required to keep a token. Default: 0",
    )
    parser.add_argument(
        "--apply-decisions-rules",
        action="store_true",
        help=(
            "Apply Wikipedia decision filters after counting: drop pure punctuation "
            "and standalone apostrophe fragments. Default: false"
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    if not input_path.exists():
        parser.error(f"input path does not exist: {input_path}")

    counts, processed_rows = build_counts(
        input_path=input_path,
        apply_decisions_rules=args.apply_decisions_rules,
        min_count=args.min_count,
    )
    write_word_counts_csv(counts, output_path)

    print(f"input:                  {input_path}")
    print(f"output:                 {output_path}")
    print(f"processed rows:         {processed_rows}")
    print(f"apply decisions rules:  {args.apply_decisions_rules}")
    print(f"min_count:              {args.min_count}")
    print(f"totalunique:            {len(counts)}")
    print(f"totalcounts:            {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
