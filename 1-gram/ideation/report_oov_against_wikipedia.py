from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path


TOKEN_RE = re.compile(r"\S+")


def load_vocab(path: Path) -> set[str]:
    vocab: set[str] = set()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        reader = csv.DictReader(src, dialect="excel-tab")
        for row in reader:
            token = (row.get("unigram") or "").strip()
            if token:
                vocab.add(token.casefold())
    return vocab


def token_is_word(token: str) -> bool:
    return any(char.isalpha() for char in token)


def analyze_file(path: Path, vocab: set[str]) -> tuple[int, int, Counter[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    tokens = [match.group(0) for match in TOKEN_RE.finditer(text)]
    words = [token for token in tokens if token_is_word(token)]
    oov = Counter(token for token in words if token.casefold() not in vocab)
    return len(words), sum(oov.values()), oov


def write_report(output_path: Path, vocab_path: Path, file_reports: list[tuple[Path, int, int, Counter[str]]]) -> None:
    lines: list[str] = []
    lines.append("# Wikipedia OOV Report")
    lines.append("")
    lines.append(f"Reference vocabulary: `{vocab_path}`")
    lines.append("")

    for path, total_words, oov_total, oov_counter in file_reports:
        lines.append(f"## {path.name}")
        lines.append("")
        lines.append(f"- total word tokens: `{total_words}`")
        lines.append(f"- OOV word tokens: `{oov_total}`")
        lines.append(f"- unique OOV words: `{len(oov_counter)}`")
        lines.append("")
        lines.append("Top OOV words:")
        lines.append("")

        for token, count in oov_counter.most_common(100):
            lines.append(f"- `{token}`: `{count}`")

        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report words in text files that do not appear in a Wikipedia unigram vocabulary."
    )
    parser.add_argument(
        "--vocab",
        type=Path,
        default=Path("1-gram/wikipedia.uncased.unigrams.csv"),
        help="Path to the Wikipedia unigram vocabulary CSV/TSV.",
    )
    parser.add_argument(
        "--glob",
        dest="glob_pattern",
        default="books/*.cleaned.txt",
        help="Glob pattern for text files to analyze.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("1-gram/wikipedia_oov_report.md"),
        help="Output markdown report path.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    vocab_path = args.vocab
    if not vocab_path.is_file():
        parser.error(f"vocab file does not exist: {vocab_path}")

    file_paths = sorted(Path().glob(args.glob_pattern))
    if not file_paths:
        parser.error(f"no files matched: {args.glob_pattern}")

    vocab = load_vocab(vocab_path)
    file_reports = [(path, *analyze_file(path, vocab)) for path in file_paths]
    write_report(args.output, vocab_path, file_reports)

    print(f"vocab:   {vocab_path}")
    print(f"files:   {len(file_reports)}")
    print(f"output:  {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
