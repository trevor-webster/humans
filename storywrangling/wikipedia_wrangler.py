from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_INPUT = Path("1-gram/data_structured/wikipedia.uncased.unigrams.csv")
DEFAULT_OUTPUT = Path("1-gram/data_structured/wikipedia.uncased.unigrams.wrangled.csv")


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


def wrangle_wikipedia_unigrams(input_path: Path, output_path: Path, min_count: int) -> dict[str, int]:
    kept_rows = 0
    removed_pure_punctuation = 0
    removed_apostrophe_fragments = 0
    removed_below_cutoff = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        input_path.open("r", encoding="utf-8", newline="") as src,
        output_path.open("w", encoding="utf-8", newline="\n") as dst,
    ):
        reader = csv.DictReader(src, delimiter="\t")
        writer = csv.DictWriter(dst, fieldnames=["unigram", "count"], delimiter="\t", lineterminator="\n")
        writer.writeheader()

        for row in reader:
            token = (row.get("unigram") or "").strip()
            count_text = (row.get("count") or "").strip()
            if not token or not count_text:
                continue

            count = int(count_text)

            if is_pure_punctuation(token):
                removed_pure_punctuation += 1
                continue

            if is_apostrophe_fragment(token):
                removed_apostrophe_fragments += 1
                continue

            if count < min_count:
                removed_below_cutoff += 1
                continue

            writer.writerow({"unigram": token, "count": count})
            kept_rows += 1

    return {
        "kept_rows": kept_rows,
        "removed_pure_punctuation": removed_pure_punctuation,
        "removed_apostrophe_fragments": removed_apostrophe_fragments,
        "removed_below_cutoff": removed_below_cutoff,
        "output_size": output_path.stat().st_size,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Wrangle the raw Wikipedia unigram reference by removing pure punctuation, "
            "dropping standalone apostrophe fragments, and applying a minimum count cutoff."
        )
    )
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT, help="Input tab-delimited CSV.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output tab-delimited CSV written with Unix LF line endings.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=40,
        help="Minimum count required to keep a row.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")

    stats = wrangle_wikipedia_unigrams(args.input, args.output, args.min_count)

    print(f"input:   {args.input}")
    print(f"output:  {args.output}")
    print(f"kept:    {stats['kept_rows']}")
    print(f"removed pure punctuation:    {stats['removed_pure_punctuation']}")
    print(f"removed apostrophe shards:   {stats['removed_apostrophe_fragments']}")
    print(f"removed below count cutoff:  {stats['removed_below_cutoff']}")
    print(f"size:    {stats['output_size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
