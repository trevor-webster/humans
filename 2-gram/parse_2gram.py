from __future__ import annotations

import argparse
from pathlib import Path


def line_has_two_untagged_tokens(line: str) -> bool:
    stripped = line.rstrip("\n")
    if not stripped:
        return False

    parts = stripped.split("\t", 1)
    key = parts[0].strip()
    tokens = key.split()

    if len(tokens) < 2:
        return False

    first_two = tokens[:2]
    return all("_" not in token for token in first_two)


def parse_file(input_path: Path, output_path: Path) -> tuple[int, int]:
    kept = 0
    removed = 0

    with input_path.open("r", encoding="utf-8", errors="replace") as src:
        with output_path.open("w", encoding="utf-8", newline="") as dst:
            for line in src:
                if line_has_two_untagged_tokens(line):
                    dst.write(line)
                    kept += 1
                else:
                    removed += 1

    return kept, removed


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.name}.parsed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Filter Google Books 2-gram files so only rows whose first two "
            "key tokens do not contain underscores are kept."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to an input 2-gram file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file path. Defaults to <input>.parsed",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or default_output_path(input_path)

    if not input_path.is_file():
        parser.error(f"input file does not exist: {input_path}")

    kept, removed = parse_file(input_path, output_path)

    print(f"input:   {input_path}")
    print(f"output:  {output_path}")
    print(f"kept:    {kept}")
    print(f"removed: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
