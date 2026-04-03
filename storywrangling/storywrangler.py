from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


NORMALIZE_MAP = {
    "\u00a0": " ",
    "\u2002": " ",
    "\u2003": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u202f": " ",
    "\ufeff": "",
    "â": " ",
    "â€¦": "...",
    "â€“": "-",
    "â€”": "-",
    "â€˜": "'",
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
    "Ã¢â‚¬Ëœ": "'",
    "Ã¢â‚¬â„¢": "'",
    "Ã¢â‚¬Å“": '"',
    "Ã¢â‚¬Â": '"',
    "Ã¢â‚¬Â¦": "...",
    "Ã¢â‚¬â€œ": "-",
    "Ã¢â‚¬â€": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "–": "-",
    "—": "-",
    "…": "...",
}


ALLOWED_HYPHEN_PREFIXES = {
    "anti",
    "counter",
    "inter",
    "mega",
    "micro",
    "mid",
    "multi",
    "neo",
    "non",
    "post",
    "pre",
    "proto",
    "pseudo",
    "re",
    "semi",
    "sub",
    "super",
    "ultra",
}

APOSTROPHE_SUFFIXES = ("'s", "s'", "n't", "'d", "'ll", "'m", "'re", "'ve")


@dataclass(frozen=True)
class TokenReconciliation:
    is_known: bool
    replacement: str | None = None


def normalize_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    for source, target in NORMALIZE_MAP.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def keep_punctuation(char: str, prev_char: str, next_char: str) -> bool:
    prev_is_word = prev_char.isalnum() or prev_char == "_"
    next_is_word = next_char.isalnum() or next_char == "_"
    return char in {".", ",", "-", "'"} and prev_is_word and next_is_word


def remove_layout_artifacts(text: str, titles: list[str]) -> str:
    title_variants = {title.strip().casefold() for title in titles if title.strip()}
    seen_titles: set[str] = set()
    kept_lines: list[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        folded = line.casefold()

        if not line:
            kept_lines.append("")
            continue

        if re.fullmatch(r"\*+(?:\s+\*+)+", line):
            continue

        if re.fullmatch(r"[ivxlcdm]+", line) or re.fullmatch(r"[IVXLCDM]+", line):
            continue

        if line == "Q":
            continue

        if title_variants and folded in title_variants:
            if folded in seen_titles:
                continue
            seen_titles.add(folded)

        kept_lines.append(raw_line)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def clean_text(text: str, titles: list[str] | None = None) -> str:
    cleaned = normalize_text(text)
    cleaned = remove_layout_artifacts(cleaned, titles or [])

    result: list[str] = []
    length = len(cleaned)

    for index, char in enumerate(cleaned):
        prev_char = cleaned[index - 1] if index > 0 else ""
        next_char = cleaned[index + 1] if index + 1 < length else ""

        if char.isalnum() or char.isspace():
            result.append(char)
            continue

        if keep_punctuation(char, prev_char, next_char):
            result.append(char)
            continue

        result.append(" ")

    cleaned = "".join(result)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() + "\n"


def lowercase_and_count_words(text: str) -> Counter[str]:
    lowered = text.casefold()
    counts: Counter[str] = Counter()

    for token in re.findall(r"\S+", lowered):
        if any(char.isalpha() for char in token):
            counts[token] += 1

    return counts


def reconcile_token(token: str, vocab: set[str]) -> TokenReconciliation:
    folded = token.casefold()
    if folded in vocab:
        return TokenReconciliation(is_known=True)

    apostrophe_result = reconcile_apostrophe_token(token, vocab)
    if apostrophe_result.is_known:
        return apostrophe_result

    dot_result = reconcile_dot_token(token, vocab)
    if dot_result.is_known:
        return dot_result

    hyphen_result = reconcile_hyphen_token(token, vocab)
    if hyphen_result.is_known:
        return hyphen_result

    return TokenReconciliation(is_known=False)


def reconcile_apostrophe_token(token: str, vocab: set[str]) -> TokenReconciliation:
    lowered = token.casefold()
    for suffix in APOSTROPHE_SUFFIXES:
        if lowered.endswith(suffix) and len(token) > len(suffix):
            base = token[: -len(suffix)]
            if base.casefold() in vocab:
                return TokenReconciliation(is_known=True)
    return TokenReconciliation(is_known=False)


def reconcile_hyphen_token(token: str, vocab: set[str]) -> TokenReconciliation:
    if "-" not in token:
        return TokenReconciliation(is_known=False)

    pieces = token.split("-")
    alpha_pieces = [piece for piece in pieces if any(char.isalpha() for char in piece)]
    if len(alpha_pieces) < 2:
        return TokenReconciliation(is_known=False)

    joined = "".join(pieces)
    if joined.casefold() in vocab:
        return TokenReconciliation(is_known=True, replacement=joined)

    for index, piece in enumerate(alpha_pieces):
        folded_piece = piece.casefold()
        if index == 0 and folded_piece in ALLOWED_HYPHEN_PREFIXES:
            continue
        if folded_piece not in vocab:
            return TokenReconciliation(is_known=False)

    return TokenReconciliation(is_known=True)


def reconcile_dot_token(token: str, vocab: set[str]) -> TokenReconciliation:
    if "." not in token:
        return TokenReconciliation(is_known=False)

    pieces = token.split(".")
    vocab_matches = [
        piece for piece in pieces if piece and any(char.isalpha() for char in piece) and piece.casefold() in vocab
    ]
    if len(vocab_matches) != 1:
        return TokenReconciliation(is_known=False)

    for piece in pieces:
        if not piece or piece in vocab_matches:
            continue
        if any(char.isalpha() for char in piece):
            return TokenReconciliation(is_known=False)

    replacement = vocab_matches[0]
    return TokenReconciliation(is_known=True, replacement=replacement)


def load_unigram_vocab(path: Path) -> set[str]:
    vocab: set[str] = set()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        reader = csv.DictReader(src, dialect="excel-tab")
        for row in reader:
            token = (row.get("unigram") or "").strip()
            if token:
                vocab.add(token.casefold())
    return vocab


def reconcile_cleaned_text(text: str, vocab: set[str]) -> tuple[str, int]:
    replacements = 0

    def replace_match(match: re.Match[str]) -> str:
        nonlocal replacements
        token = match.group(0)
        result = reconcile_token(token, vocab)
        if result.replacement and result.replacement != token:
            replacements += 1
            return result.replacement
        return token

    reconciled = re.sub(r"\S+", replace_match, text)
    return reconciled, replacements


def default_counts_output_path(input_path: Path, output_dir: Path) -> Path:
    story_name = input_path.stem.removesuffix(".cleaned")
    story_name = re.sub(r"(?: \([^()]+\))+$", "", story_name).strip()
    return output_dir / f"{story_name}-1grams.csv"


def default_json_output_path(csv_output_path: Path) -> Path:
    return csv_output_path.with_suffix(".json")


def build_structured_rows(counts: Counter[str]) -> list[dict[str, float | int | str]]:
    total_unique = len(counts)
    total_counts = sum(counts.values())
    rows: list[dict[str, float | int | str]] = []

    for word, count in counts.most_common():
        rows.append(
            {
                "types": word,
                "counts": count,
                "probs": count / total_counts if total_counts else 0.0,
                "total_unique": total_unique,
                "totalunique": total_unique,
            }
        )

    return rows


def write_word_counts_csv(counts: Counter[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_structured_rows(counts)
    with output_path.open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(["types", "counts", "probs", "total_unique"])
        for row in rows:
            writer.writerow([row["types"], row["counts"], row["probs"], row["total_unique"]])


def write_word_counts_json(counts: Counter[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_structured_rows(counts)
    json_rows = [
        {
            "types": row["types"],
            "counts": row["counts"],
            "totalunique": row["totalunique"],
            "probs": row["probs"],
        }
        for row in rows
    ]

    with output_path.open("w", encoding="utf-8", newline="") as dst:
        json.dump(json_rows, dst, indent=4)
        dst.write("\n")


def concat_story_counts(input_dir: Path, csv_output_path: Path, json_output_path: Path) -> Counter[str]:
    aggregate: Counter[str] = Counter()

    for csv_path in sorted(input_dir.glob("*-1grams.csv")):
        with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as src:
            reader = csv.DictReader(src)
            for row in reader:
                token = (row.get("types") or "").strip()
                count_text = (row.get("counts") or "").strip()
                if not token or not count_text:
                    continue
                aggregate[token] += int(count_text)

    write_word_counts_csv(aggregate, csv_output_path)
    write_word_counts_json(aggregate, json_output_path)
    return aggregate


def default_output_path(input_path: Path) -> Path:
    story_name = re.sub(r"(?: \([^()]+\))+$", "", input_path.stem).strip()
    return input_path.with_name(f"{story_name}.cleaned{input_path.suffix}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Clean downloaded text corpora with targeted mojibake normalization, "
            "layout artifact removal, and punctuation retention only inside words/numbers."
        )
    )
    parser.add_argument("input", type=Path, help="Path to the source text corpus.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output text path. Defaults to <input>.cleaned<suffix>",
    )
    parser.add_argument(
        "--title",
        action="append",
        default=[],
        help="Standalone repeated title/header line to remove after the first occurrence. Repeat as needed.",
    )
    parser.add_argument(
        "--reconcile-vocab",
        type=Path,
        help="Optional Wikipedia unigram vocabulary used to reconcile safe OOV artifacts in cleaned text.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or default_output_path(input_path)

    if not input_path.is_file():
        parser.error(f"input file does not exist: {input_path}")

    source_text = input_path.read_text(encoding="utf-8", errors="replace")
    cleaned_text = clean_text(source_text, titles=args.title)
    replacements = 0
    if args.reconcile_vocab:
        vocab = load_unigram_vocab(args.reconcile_vocab)
        cleaned_text, replacements = reconcile_cleaned_text(cleaned_text, vocab)
    output_path.write_text(cleaned_text, encoding="utf-8", newline="")

    print(f"input:   {input_path}")
    print(f"output:  {output_path}")
    print(f"chars:   {len(cleaned_text)}")
    if args.reconcile_vocab:
        print(f"reconciled replacements: {replacements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
