from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path


def parse_line(line: str) -> dict[str, object] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#RANKING"):
        return None

    parts = stripped.split()
    if len(parts) < 5:
        return None

    word = parts[1]
    count_text = parts[-3]
    percent_text = parts[-2]

    count = int(count_text.replace(",", ""))
    prob = float(Decimal(percent_text.rstrip("%")) / Decimal("100"))

    return {
        "types": word,
        "counts": count,
        "probs": prob,
    }


def convert_file(input_path: Path, output_path: Path) -> tuple[int, int]:
    rows: list[dict[str, object]] = []

    with input_path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            parsed = parse_line(line)
            if parsed is not None:
                rows.append(parsed)

    total_unique = len(rows)
    for row in rows:
        row["totalunique"] = total_unique

    with output_path.open("w", encoding="utf-8", newline="") as dst:
        json.dump(rows, dst, indent=4)
        dst.write("\n")

    return total_unique, len(rows)


def default_output_path(input_path: Path) -> Path:
    return input_path.with_suffix(".json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a frequency text file into the JSON structure used by "
            "the 1-gram data files."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the source text file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JSON path. Defaults to replacing the input extension with .json",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or default_output_path(input_path)

    if not input_path.is_file():
        parser.error(f"input file does not exist: {input_path}")

    total_unique, written = convert_file(input_path, output_path)

    print(f"input:        {input_path}")
    print(f"output:       {output_path}")
    print(f"totalunique:  {total_unique}")
    print(f"written:      {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
