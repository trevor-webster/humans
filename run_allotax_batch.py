import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
ONE_GRAM_DIR = PROJECT_ROOT / "1-gram"
FIGURES_DIR = PROJECT_ROOT / "figures"
ALPHA = "0.17"


def ensure_utf8_runtime() -> None:
    if sys.flags.utf8_mode:
        return

    result = subprocess.run(
        [str(VENV_PYTHON), "-X", "utf8", str(Path(__file__).resolve())],
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


def ensure_json(input_path: Path, output_path: Path | None = None, drop_punc: bool = True) -> Path:
    if input_path.suffix.lower() == ".json":
        return input_path

    json_path = output_path or input_path.with_suffix(".json")
    if json_path.exists() and json_path.stat().st_mtime >= input_path.stat().st_mtime:
        return json_path

    csv_to_allotax_json(input_path=input_path, output_path=json_path, drop_punc=drop_punc)
    return json_path


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
    return parser


def main() -> int:
    ensure_utf8_runtime()
    verify_runtime()
    args = build_parser().parse_args()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    humans = ensure_json(ONE_GRAM_DIR / "humans.csv")
    wiki1grams = ensure_json(
        ONE_GRAM_DIR / "wikipedia.uncased.unigrams.wrangled.csv",
        ONE_GRAM_DIR / "wikipedia.uncased.unigrams.wrangled.json",
    )
    sapiens = ensure_json(ONE_GRAM_DIR / "Sapiens.csv")

    stories = {
        "sapiens": ("Sapiens", sapiens),
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

    selected_story_slugs = args.stories or list(stories.keys())
    unknown_story_slugs = [slug for slug in selected_story_slugs if slug not in stories]
    if unknown_story_slugs:
        raise ValueError(f"Unknown story slug(s): {', '.join(unknown_story_slugs)}")

    selected_stories = [
        (slug, stories[slug][0], stories[slug][1])
        for slug in selected_story_slugs
    ]

    if args.compare_to in {"all", "wiki"} and not args.stories:
        render_pair(
            humans,
            wiki1grams,
            FIGURES_DIR / "humans-v-wiki1grams.html",
            "humans",
            "wiki1grams",
        )

    if args.compare_to in {"all", "humans"}:
        for slug, label, story_path in selected_stories:
            render_pair(
                story_path,
                humans,
                FIGURES_DIR / f"{slug}-v-humans.html",
                label,
                "humans",
            )

    if args.compare_to in {"all", "wiki"}:
        for slug, label, story_path in selected_stories:
            render_pair(
                story_path,
                wiki1grams,
                FIGURES_DIR / f"{slug}-v-wiki1grams.html",
                label,
                "wiki1grams",
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
