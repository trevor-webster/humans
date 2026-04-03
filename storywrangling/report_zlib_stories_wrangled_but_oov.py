from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from storywrangling.storywrangler import reconcile_token


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
    oov = Counter(token for token in words if not reconcile_token(token, vocab).is_known)
    return len(words), sum(oov.values()), oov


def format_percent(part: int, whole: int) -> str:
    if whole == 0:
        return "0.00%"
    return f"{(part / whole) * 100:.2f}%"


def write_report(output_path: Path, vocab_path: Path, file_reports: list[tuple[Path, int, int, Counter[str]]]) -> None:
    lines: list[str] = []
    overall_total_words = sum(total_words for _, total_words, _, _ in file_reports)
    overall_oov_total = sum(oov_total for _, _, oov_total, _ in file_reports)

    lines.append("# Zlib Stories Wrangled But OOV")
    lines.append("")
    lines.append(f"Reference vocabulary: `{vocab_path}`")
    lines.append(f"Overall OOV: `{overall_oov_total}` / `{overall_total_words}` = `{format_percent(overall_oov_total, overall_total_words)}`")
    lines.append("")

    for path, total_words, oov_total, oov_counter in file_reports:
        lines.append(f"## {path.name}")
        lines.append("")
        lines.append(f"- OOV percent: `{format_percent(oov_total, total_words)}`")
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
        description="Report remaining OOV words in wrangled z-lib story texts against a Wikipedia unigram vocabulary."
    )
    parser.add_argument(
        "--vocab",
        type=Path,
        default=Path("1-gram/data_structured/wikipedia.uncased.unigrams.wrangled.csv"),
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
        default=Path("1-gram/ideation/zlib_stories_wrangled_but_oov.md"),
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
