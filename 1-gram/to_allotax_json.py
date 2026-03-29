from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def is_punctuation_token(token: str) -> bool:
    return bool(token) and not any(char.isalnum() for char in token)


def parse_row(row: dict[str, str], drop_punc: bool) -> dict[str, object] | None:
    token = (row.get("unigram") or "").strip()
    count_text = (row.get("count") or "").strip()

    if not token or not count_text:
        return None

    if drop_punc and is_punctuation_token(token):
        return None

    count = int(count_text.replace(",", ""))
    return {
        "types": token,
        "counts": count,
    }


def detect_dialect(input_path: Path) -> csv.Dialect:
    with input_path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        sample = src.read(4096)

    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t")
    except csv.Error:
        return csv.get_dialect("excel-tab")


def convert_file(input_path: Path, output_path: Path, drop_punc: bool) -> tuple[int, int, int]:
    rows: list[dict[str, object]] = []
    dialect = detect_dialect(input_path)

    with input_path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        reader = csv.DictReader(src, dialect=dialect)
        for row in reader:
            parsed = parse_row(row, drop_punc)
            if parsed is not None:
                rows.append(parsed)

    total_unique = len(rows)
    total_counts = sum(int(row["counts"]) for row in rows)

    for row in rows:
        count = int(row["counts"])
        row["totalunique"] = total_unique
        row["probs"] = count / total_counts if total_counts else 0.0

    with output_path.open("w", encoding="utf-8", newline="") as dst:
        json.dump(rows, dst, indent=4)
        dst.write("\n")

    return total_unique, total_counts, len(rows)


def default_output_path(input_path: Path) -> Path:
    return input_path.with_suffix(".json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a unigram CSV file into the allotax JSON structure with "
            "types, counts, totalunique, and probs."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the source unigram CSV file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JSON path. Defaults to replacing the input extension with .json",
    )
    parser.add_argument(
        "--drop-punc",
        type=parse_bool,
        default=True,
        help="Drop tokens made entirely of punctuation. Default: true",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or default_output_path(input_path)

    if not input_path.is_file():
        parser.error(f"input file does not exist: {input_path}")

    total_unique, total_counts, written = convert_file(
        input_path=input_path,
        output_path=output_path,
        drop_punc=args.drop_punc,
    )

    print(f"input:        {input_path}")
    print(f"output:       {output_path}")
    print(f"drop_punc:    {args.drop_punc}")
    print(f"totalunique:  {total_unique}")
    print(f"totalcounts:  {total_counts}")
    print(f"written:      {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
