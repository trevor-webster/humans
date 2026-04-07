from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storywrangling.storywrangler import (
    clean_text,
    lowercase_and_count_words,
    load_unigram_vocab,
    reconcile_cleaned_text,
    write_word_counts_csv,
    write_word_counts_json,
)


DEFAULT_BOOKS_DIR = PROJECT_ROOT / "books"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "1-gram"
DEFAULT_RECONCILE_VOCAB = DEFAULT_OUTPUT_DIR / "wikitext-103-raw-v1-1grams.decisions.csv"


def iter_source_books(books_dir: Path) -> list[Path]:
    return sorted(path for path in books_dir.glob("*.txt") if not path.name.endswith(".cleaned.txt"))


def cleaned_output_path(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}.cleaned{source_path.suffix}")


def counts_output_path(source_path: Path, output_dir: Path) -> Path:
    if source_path.stem == "Sapiens":
        return output_dir / "Sapiens.csv"

    story_name = re.sub(r"(?: \([^()]+\))+$", "", source_path.stem).strip()
    return output_dir / f"{story_name}-1grams.csv"


def json_output_path(csv_output_path: Path) -> Path:
    return csv_output_path.with_suffix(".json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate cleaned book texts and 1-gram outputs using the repo's "
            "current cleaning rules and an external unigram lexicon for OOV reconciliation."
        )
    )
    parser.add_argument(
        "--books-dir",
        type=Path,
        default=DEFAULT_BOOKS_DIR,
        help=f"Directory containing raw book .txt files. Default: {DEFAULT_BOOKS_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for 1-gram CSV/JSON outputs. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--reconcile-vocab",
        type=Path,
        default=DEFAULT_RECONCILE_VOCAB,
        help=f"Unigram lexicon used for OOV reconciliation. Default: {DEFAULT_RECONCILE_VOCAB}",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.books_dir.is_dir():
        raise FileNotFoundError(f"books directory does not exist: {args.books_dir}")
    if not args.reconcile_vocab.is_file():
        raise FileNotFoundError(f"reconciliation vocab does not exist: {args.reconcile_vocab}")

    source_books = iter_source_books(args.books_dir)
    if not source_books:
        raise FileNotFoundError(f"no source book .txt files found in: {args.books_dir}")

    vocab = load_unigram_vocab(args.reconcile_vocab)
    aggregate: Counter[str] = Counter()
    total_replacements = 0

    for source_path in source_books:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        cleaned_text = clean_text(source_text)
        cleaned_text, replacements = reconcile_cleaned_text(cleaned_text, vocab)
        counts = lowercase_and_count_words(cleaned_text)

        cleaned_path = cleaned_output_path(source_path)
        csv_output = counts_output_path(source_path, args.output_dir)
        json_output = json_output_path(csv_output)

        cleaned_path.write_text(cleaned_text, encoding="utf-8", newline="")
        write_word_counts_csv(counts, csv_output)
        write_word_counts_json(counts, json_output)

        aggregate.update(counts)
        total_replacements += replacements

        print(f"source:         {source_path.name}")
        print(f"cleaned:        {cleaned_path.name}")
        print(f"counts csv:     {csv_output.name}")
        print(f"counts json:    {json_output.name}")
        print(f"replacements:   {replacements}")
        print(f"totalunique:    {len(counts)}")
        print(f"totalcounts:    {sum(counts.values())}")
        print("")

    humans_csv = args.output_dir / "humans.csv"
    humans_json = args.output_dir / "humans.json"
    write_word_counts_csv(aggregate, humans_csv)
    write_word_counts_json(aggregate, humans_json)

    print(f"aggregate csv:  {humans_csv.name}")
    print(f"aggregate json: {humans_json.name}")
    print(f"aggregate unique: {len(aggregate)}")
    print(f"aggregate counts: {sum(aggregate.values())}")
    print(f"total replacements: {total_replacements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
