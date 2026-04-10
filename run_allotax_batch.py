import argparse
import csv
from itertools import combinations
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
ONE_GRAM_DIR = PROJECT_ROOT / "1-gram"
TWO_GRAM_DIR = PROJECT_ROOT / "2-gram"
THREE_GRAM_DIR = PROJECT_ROOT / "3-gram"
FIGURES_DIR = PROJECT_ROOT / "figures"
ALPHA = "0.17"
PARQUET_BATCH_SIZE = 50000


def ensure_utf8_runtime() -> None:
    if sys.flags.utf8_mode:
        return

    result = subprocess.run(
        [str(VENV_PYTHON), "-X", "utf8", str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=str(PROJECT_ROOT),
    )
    raise SystemExit(result.returncode)


def verify_runtime() -> None:
    expected_python = str(VENV_PYTHON.resolve())
    active_python = str(Path(sys.executable).resolve())

    if active_python.lower() != expected_python.lower():
        raise RuntimeError(
            "This script should be run with the project venv interpreter.\n"
            f"Expected: {expected_python}\n"
            f"Active:   {active_python}\n"
            "Run:\n"
            rf"  {expected_python} {Path(__file__).resolve()}"
        )

    if shutil.which("node") is None:
        raise RuntimeError("Node.js was not found on PATH.")


def is_punctuation_token(token: str) -> bool:
    return bool(token) and not any(char.isalnum() for char in token)


def parse_int_like(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip()
    if not text:
        return None
    return int(text.replace(",", ""))


def parse_text_like(value: object) -> str:
    return "" if value is None else str(value).strip()


def csv_to_allotax_json(input_path: Path, output_path: Path, drop_punc: bool = True) -> None:
    with input_path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        sample = src.read(4096)
        src.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        except csv.Error:
            dialect = csv.get_dialect("excel")
        reader = csv.DictReader(src, dialect=dialect)
        fieldnames = {name.strip().lower(): name for name in (reader.fieldnames or [])}

        rows: list[dict[str, object]] = []
        for row in reader:
            if "types" in fieldnames and "counts" in fieldnames:
                token = (row.get(fieldnames["types"]) or "").strip()
                count_text = (row.get(fieldnames["counts"]) or "").strip()
                total_unique_text = (
                    row.get(fieldnames.get("totalunique", ""))
                    or row.get(fieldnames.get("total_unique", ""))
                    or ""
                ).strip()
                probs_text = (row.get(fieldnames.get("probs", "")) or "").strip()
                if not token or not count_text:
                    continue
                rows.append(
                    {
                        "types": token,
                        "counts": int(count_text.replace(",", "")),
                        "totalunique": int(total_unique_text.replace(",", "")) if total_unique_text else 0,
                        "probs": float(probs_text) if probs_text else 0.0,
                    }
                )
                continue

            if "unigram" in fieldnames and "count" in fieldnames:
                token = (row.get(fieldnames["unigram"]) or "").strip()
                count_text = (row.get(fieldnames["count"]) or "").strip()
                if not token or not count_text:
                    continue
                if drop_punc and is_punctuation_token(token):
                    continue
                rows.append(
                    {
                        "types": token,
                        "counts": int(count_text.replace(",", "")),
                    }
                )

    if rows and "totalunique" not in rows[0]:
        total_unique = len(rows)
        total_counts = sum(int(row["counts"]) for row in rows)
        for row in rows:
            count = int(row["counts"])
            row["totalunique"] = total_unique
            row["probs"] = count / total_counts if total_counts else 0.0

    with output_path.open("w", encoding="utf-8", newline="") as dst:
        json.dump(rows, dst, indent=4)
        dst.write("\n")


def parquet_to_allotax_json(input_path: Path, output_path: Path, drop_punc: bool = True) -> None:
    if pq is None:
        raise RuntimeError(
            "pyarrow is required to convert parquet inputs to allotax JSON. "
            "Install it in the project venv first."
        )

    parquet_file = pq.ParquetFile(input_path)
    fieldnames = {name.strip().lower(): name for name in parquet_file.schema_arrow.names}
    token_field = fieldnames.get("types") or fieldnames.get("unigram")
    count_field = fieldnames.get("counts") or fieldnames.get("count")

    if not token_field or not count_field:
        raise ValueError(
            f"Could not find token/count columns in parquet file {input_path}. "
            "Expected one of: types/counts or unigram/count."
        )

    apply_drop_punc = "unigram" in fieldnames and "count" in fieldnames
    total_unique = 0
    total_counts = 0

    for batch in parquet_file.iter_batches(
        columns=[token_field, count_field],
        batch_size=PARQUET_BATCH_SIZE,
    ):
        tokens = batch.column(0).to_pylist()
        counts = batch.column(1).to_pylist()
        for token_value, count_value in zip(tokens, counts):
            token = parse_text_like(token_value)
            count = parse_int_like(count_value)
            if not token or count is None:
                continue
            if apply_drop_punc and drop_punc and is_punctuation_token(token):
                continue
            total_unique += 1
            total_counts += count

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as dst:
        dst.write("[\n")
        first = True
        for batch in parquet_file.iter_batches(
            columns=[token_field, count_field],
            batch_size=PARQUET_BATCH_SIZE,
        ):
            tokens = batch.column(0).to_pylist()
            counts = batch.column(1).to_pylist()
            for token_value, count_value in zip(tokens, counts):
                token = parse_text_like(token_value)
                count = parse_int_like(count_value)
                if not token or count is None:
                    continue
                if apply_drop_punc and drop_punc and is_punctuation_token(token):
                    continue

                row = {
                    "types": token,
                    "counts": count,
                    "totalunique": total_unique,
                    "probs": count / total_counts if total_counts else 0.0,
                }
                if not first:
                    dst.write(",\n")
                dst.write(json.dumps(row, ensure_ascii=False))
                first = False
        dst.write("\n]\n")


def ensure_json(input_path: Path, output_path: Path | None = None, drop_punc: bool = True) -> Path:
    if input_path.suffix.lower() == ".json":
        return input_path

    json_path = output_path or input_path.with_suffix(".json")
    if json_path.exists() and json_path.stat().st_mtime >= input_path.stat().st_mtime:
        return json_path

    if input_path.suffix.lower() == ".parquet":
        parquet_to_allotax_json(input_path=input_path, output_path=json_path, drop_punc=drop_punc)
        return json_path

    csv_to_allotax_json(input_path=input_path, output_path=json_path, drop_punc=drop_punc)
    return json_path


def label_to_slug(label: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in label.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "reference"


def render_pair(path1: Path, path2: Path, output_path: Path, label1: str, label2: str) -> None:
    from py_allotax.generate_svg import generate_svg

    if output_path.exists():
        print(f"skipping existing: {output_path.name}")
        return

    print(f"rendering: {output_path.name}")
    generate_svg(
        str(path1),
        str(path2),
        str(output_path),
        ALPHA,
        label1,
        label2,
        "html",
    )


def default_output_dir(gram_size: str, pairwise_books: bool) -> Path:
    if pairwise_books:
        if gram_size == "1":
            return FIGURES_DIR / "1grams" / "book-pairs"
        if gram_size == "2":
            return FIGURES_DIR / "2grams" / "book-pairs"
        raise ValueError("Pairwise book rendering currently supports only --gram-size 1 or 2.")

    return FIGURES_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch-render py-allotax figures for humans and wiki comparisons.")
    parser.add_argument(
        "--compare-to",
        choices=["all", "humans", "wiki"],
        default="all",
        help="Which comparison set to render. Default: all.",
    )
    parser.add_argument(
        "--stories",
        nargs="*",
        help="Optional story slugs to render. Defaults to all stories.",
    )
    parser.add_argument(
        "--pairwise-books",
        action="store_true",
        help="Render unordered book-v-book pairs for the selected stories instead of humans/wiki comparisons.",
    )
    parser.add_argument(
        "--gram-size",
        choices=["1", "2", "3"],
        default="1",
        help="Which n-gram dataset to render. Default: 1.",
    )
    parser.add_argument(
        "--humans-path",
        type=Path,
        help=(
            "Optional override for the humans/reference dataset used in --compare-to humans. "
            "Supports .csv, .json, and .parquet."
        ),
    )
    parser.add_argument(
        "--humans-label",
        help=(
            "Optional label for --humans-path. Defaults to the file stem when --humans-path "
            "is provided, otherwise the built-in humans label."
        ),
    )
    parser.add_argument(
        "--wiki-path",
        type=Path,
        help=(
            "Optional override for the wiki/reference dataset used in --compare-to wiki. "
            "Supports .csv, .json, and .parquet."
        ),
    )
    parser.add_argument(
        "--wiki-label",
        help=(
            "Optional label for --wiki-path. Defaults to the file stem when --wiki-path "
            "is provided, otherwise the built-in wiki label."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory for rendered figures. Defaults to figures for humans/wiki mode and "
            "figures/<n>grams/book-pairs for --pairwise-books."
        ),
    )
    return parser


def main() -> int:
    ensure_utf8_runtime()
    verify_runtime()
    args = build_parser().parse_args()
    output_dir = args.output_dir or default_output_dir(args.gram_size, args.pairwise_books)
    output_dir.mkdir(parents=True, exist_ok=True)
    wiki_reference = None
    wiki_source = args.wiki_path

    if args.gram_size == "1":
        default_humans_path = ONE_GRAM_DIR / "humans.csv"
        humans_source = args.humans_path or default_humans_path
        humans = ensure_json(humans_source)
        default_wiki_path = ONE_GRAM_DIR / "wikitext-103-raw-v1-1grams.decisions.csv"
        wiki_source = args.wiki_path or default_wiki_path
        wiki_output_path = None
        if not args.wiki_path:
            wiki_output_path = ONE_GRAM_DIR / "wikitext-103-raw-v1-1grams.decisions.json"
        if args.compare_to in {"all", "wiki"}:
            wiki_reference = ensure_json(
                wiki_source,
                wiki_output_path,
            )
        stories = {
            "sapiens": ("Sapiens", ensure_json(ONE_GRAM_DIR / "Sapiens.csv")),
            "how-compassion-made-us-human": (
                "How Compassion Made Us Human",
                ONE_GRAM_DIR / "How Compassion Made Us Human The Evolutionary Origins of Tenderness, Trust and Moralit-1grams.json",
            ),
            "code-economy": (
                "The Code Economy",
                ONE_GRAM_DIR / "The Code Economy A Forty-Thousand Year History-1grams.json",
            ),
            "dawn-of-everything": (
                "The Dawn of Everything",
                ONE_GRAM_DIR / "The Dawn of Everything A New History of Humanity-1grams.json",
            ),
            "ultrasociety": (
                "Ultrasociety",
                ONE_GRAM_DIR / "Ultrasociety How 10,000 Years of War Made Humans the Greatest Cooperators on Earth-1grams.json",
            ),
        }
    elif args.gram_size == "2":
        default_humans_path = TWO_GRAM_DIR / "humans-2grams.csv"
        humans_source = args.humans_path or default_humans_path
        humans = ensure_json(humans_source)
        default_wiki_path = TWO_GRAM_DIR / "wikitext-2-raw-v1-2grams.parquet"
        wiki_source = args.wiki_path or default_wiki_path
        if args.compare_to in {"all", "wiki"}:
            wiki_reference = ensure_json(wiki_source)
        stories = {
            "sapiens": ("Sapiens", TWO_GRAM_DIR / "Sapiens-2grams.json"),
            "how-compassion-made-us-human": (
                "How Compassion Made Us Human",
                TWO_GRAM_DIR / "How Compassion Made Us Human The Evolutionary Origins of Tenderness, Trust and Moralit-2grams.json",
            ),
            "code-economy": (
                "The Code Economy",
                TWO_GRAM_DIR / "The Code Economy A Forty-Thousand Year History-2grams.json",
            ),
            "dawn-of-everything": (
                "The Dawn of Everything",
                TWO_GRAM_DIR / "The Dawn of Everything A New History of Humanity-2grams.json",
            ),
            "ultrasociety": (
                "Ultrasociety",
                TWO_GRAM_DIR / "Ultrasociety How 10,000 Years of War Made Humans the Greatest Cooperators on Earth-2grams.json",
            ),
        }
    else:
        default_humans_path = THREE_GRAM_DIR / "humans-3grams.csv"
        humans_source = args.humans_path or default_humans_path
        humans = ensure_json(humans_source)
        stories = {
            "sapiens": ("Sapiens", THREE_GRAM_DIR / "Sapiens-3grams.json"),
            "how-compassion-made-us-human": (
                "How Compassion Made Us Human",
                THREE_GRAM_DIR / "How Compassion Made Us Human The Evolutionary Origins of Tenderness, Trust and Moralit-3grams.json",
            ),
            "code-economy": (
                "The Code Economy",
                THREE_GRAM_DIR / "The Code Economy A Forty-Thousand Year History-3grams.json",
            ),
            "dawn-of-everything": (
                "The Dawn of Everything",
                THREE_GRAM_DIR / "The Dawn of Everything A New History of Humanity-3grams.json",
            ),
            "ultrasociety": (
                "Ultrasociety",
                THREE_GRAM_DIR / "Ultrasociety How 10,000 Years of War Made Humans the Greatest Cooperators on Earth-3grams.json",
            ),
        }

    if args.humans_path:
        humans_label = args.humans_label or humans_source.stem
    else:
        humans_label = args.humans_label or {
            "1": "humans",
            "2": "humans2grams",
            "3": "humans3grams",
        }[args.gram_size]
    humans_slug = label_to_slug(humans_label)

    if args.wiki_path:
        wiki_label = args.wiki_label or wiki_source.stem
    elif args.gram_size == "1":
        wiki_label = args.wiki_label or "wiki1grams"
    elif args.gram_size == "2":
        wiki_label = args.wiki_label or "wiki2grams"
    else:
        wiki_label = args.wiki_label or "wiki"
    wiki_slug = label_to_slug(wiki_label)

    selected_story_slugs = args.stories or list(stories.keys())
    unknown_story_slugs = [slug for slug in selected_story_slugs if slug not in stories]
    if unknown_story_slugs:
        raise ValueError(f"Unknown story slug(s): {', '.join(unknown_story_slugs)}")

    if args.stories:
        requested_story_slugs = set(args.stories)
        selected_stories = [
            (slug, stories[slug][0], stories[slug][1])
            for slug in stories
            if slug in requested_story_slugs
        ]
    else:
        selected_stories = [
            (slug, stories[slug][0], stories[slug][1])
            for slug in stories
        ]

    if args.gram_size == "3" and args.compare_to in {"all", "wiki"}:
        raise ValueError("3-gram rendering currently supports only --compare-to humans.")

    if args.pairwise_books:
        if args.gram_size == "3":
            raise ValueError("Pairwise book rendering currently supports only --gram-size 1 or 2.")

        for (left_slug, left_label, left_path), (right_slug, right_label, right_path) in combinations(selected_stories, 2):
            render_pair(
                left_path,
                right_path,
                output_dir / f"{left_slug}-v-{right_slug}.html",
                left_label,
                right_label,
            )
        return 0

    if args.compare_to in {"all", "humans"}:
        for slug, label, story_path in selected_stories:
            render_pair(
                humans,
                story_path,
                output_dir / f"{humans_slug}-v-{slug}.html",
                humans_label,
                label,
            )

    if args.compare_to in {"all", "wiki"} and args.gram_size in {"1", "2"}:
        for slug, label, story_path in selected_stories:
            render_pair(
                wiki_reference,
                story_path,
                output_dir / f"{wiki_slug}-v-{slug}.html",
                wiki_label,
                label,
            )

    if args.compare_to in {"all", "wiki"} and args.gram_size in {"1", "2"} and not args.stories:
        render_pair(
            wiki_reference,
            humans,
            output_dir / f"{wiki_slug}-v-humans.html",
            wiki_label,
            "humans",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
