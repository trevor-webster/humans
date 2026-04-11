import argparse
import csv
from fractions import Fraction
import json
import math
import re
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
FIGURES_DIR = PROJECT_ROOT / "figures"
PARQUET_BATCH_SIZE = 50000
DEFAULT_ALPHA = "0.17"
FORMAT_CHOICES = ("pdf", "html", "rtd-json", "rtd-csv", "rtd-console")
NGRAM_OUTPUT_DIRS = {
    "1-gram": FIGURES_DIR / "1grams",
    "2-gram": FIGURES_DIR / "2grams",
    "3-gram": FIGURES_DIR / "3grams",
}
CANONICAL_LABELS = (
    ("How Compassion Made Us Human", ("how compassion made us human",)),
    ("Code Economy", ("the code economy", "code economy")),
    ("Dawn of Everything", ("the dawn of everything", "dawn of everything")),
    ("Ultrasociety", ("ultrasociety",)),
    ("Sapiens", ("sapiens",)),
    ("humans3grams", ("humans 3grams", "humans-3grams", "humans3grams")),
    ("humans2grams", ("humans 2grams", "humans-2grams", "humans2grams")),
    ("humans", ("humans",)),
    ("wikitext2-2grams", ("wikitext 2 raw v1 2grams", "wikitext-2-raw-v1-2grams", "wikitext2-2grams")),
    ("wikitext103", ("wikitext 103 raw v1 1grams", "wikitext-103-raw-v1-1grams", "wikitext103")),
)


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
            rf"  {expected_python} {Path(__file__).resolve()} ..."
        )

    if shutil.which("node") is None:
        raise RuntimeError("Node.js was not found on PATH.")


def resolve_input_path(raw_path: Path) -> Path:
    path = raw_path.expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


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

    output_path.parent.mkdir(parents=True, exist_ok=True)
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


def ensure_json(input_path: Path, output_path: Path | None = None, drop_punc: bool = True, force: bool = False) -> Path:
    if input_path.suffix.lower() == ".json":
        return input_path

    json_path = output_path or input_path.with_suffix(".json")
    if (
        not force
        and json_path.exists()
        and json_path.stat().st_mtime >= input_path.stat().st_mtime
    ):
        return json_path

    if input_path.suffix.lower() == ".parquet":
        parquet_to_allotax_json(input_path=input_path, output_path=json_path, drop_punc=drop_punc)
        return json_path

    csv_to_allotax_json(input_path=input_path, output_path=json_path, drop_punc=drop_punc)
    return json_path


def clean_inferred_label(text: str) -> str:
    label = text.strip()
    label = re.sub(r"\.cleaned$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"[-_ ]?(?:1|2|3)grams$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"[-_]+", " ", label)
    label = re.sub(r"\s+", " ", label)
    return label.strip() or "reference"


def canonicalize_label(label: str) -> str:
    lowered = label.casefold()
    for canonical, patterns in CANONICAL_LABELS:
        if any(pattern in lowered for pattern in patterns):
            return canonical
    return label


def infer_label(path: Path) -> str:
    raw_label = canonicalize_label(path.stem)
    if raw_label != path.stem:
        return raw_label
    return canonicalize_label(clean_inferred_label(path.stem))


def label_to_slug(label: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in label.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "reference"


def detect_ngram_family(path: Path) -> str | None:
    lowered_parts = [part.lower() for part in path.parts]
    for family in NGRAM_OUTPUT_DIRS:
        if family in lowered_parts:
            return family
    return None


def default_output_dir(path1: Path, path2: Path) -> Path:
    family1 = detect_ngram_family(path1)
    family2 = detect_ngram_family(path2)

    if family1 and family1 == family2:
        return NGRAM_OUTPUT_DIRS[family1]
    if family1 and not family2:
        return NGRAM_OUTPUT_DIRS[family1]
    if family2 and not family1:
        return NGRAM_OUTPUT_DIRS[family2]
    return FIGURES_DIR


def normalize_alpha(raw_alpha: str) -> str:
    text = raw_alpha.strip()
    if not text:
        raise ValueError("Alpha values must not be empty.")

    try:
        normalized = str(float(Fraction(text)))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Invalid alpha value: {raw_alpha}") from exc

    numeric = float(normalized)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"Alpha must be a finite value >= 0, got: {raw_alpha}")

    return normalized


def alpha_slug(raw_alpha: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "-", raw_alpha.strip()).strip("-").lower()
    return cleaned or "alpha"


def output_extension(desired_format: str) -> str:
    if desired_format == "pdf":
        return ".pdf"
    if desired_format == "html":
        return ".html"
    if desired_format == "rtd-json":
        return ".json"
    if desired_format == "rtd-csv":
        return ".csv"
    return ".txt"


def should_include_alpha_suffix(raw_alphas: list[str], normalized_alpha: str) -> bool:
    return len(raw_alphas) > 1 or normalized_alpha != DEFAULT_ALPHA


def build_output_path(
    output_dir: Path,
    label1: str,
    label2: str,
    desired_format: str,
    raw_alpha: str,
    normalized_alpha: str,
    raw_alphas: list[str],
) -> Path:
    base = f"{label_to_slug(label1)}-v-{label_to_slug(label2)}"
    if should_include_alpha_suffix(raw_alphas, normalized_alpha):
        base = f"{base}.alpha-{alpha_slug(raw_alpha)}"
    return output_dir / f"{base}{output_extension(desired_format)}"


def render_pair(
    path1: Path,
    path2: Path,
    output_path: Path,
    alpha: str,
    label1: str,
    label2: str,
    desired_format: str,
    force: bool,
) -> None:
    from py_allotax.generate_svg import generate_svg

    if output_path.exists() and not force:
        print(f"skipping existing: {output_path.name}")
        return

    print(f"rendering: {output_path.name}")
    generate_svg(
        str(path1),
        str(path2),
        str(output_path),
        alpha,
        label1,
        label2,
        desired_format,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a single allotax comparison for two input systems.")
    parser.add_argument("system1", type=Path, help="First input dataset (.csv, .json, or .parquet).")
    parser.add_argument("system2", type=Path, help="Second input dataset (.csv, .json, or .parquet).")
    parser.add_argument(
        "--alpha",
        nargs="+",
        default=[DEFAULT_ALPHA],
        help="One or more alpha values. Accepts decimals or fractions like 1/12.",
    )
    parser.add_argument("--label1", help="Optional display label for system1.")
    parser.add_argument("--label2", help="Optional display label for system2.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for rendered output. Defaults to figures/1grams, 2grams, 3grams, or figures.",
    )
    parser.add_argument(
        "--format",
        default="html",
        choices=FORMAT_CHOICES,
        help="Output format to pass through to py-allotax. Default: html.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerender even if the target output already exists.",
    )
    return parser


def main() -> int:
    ensure_utf8_runtime()
    verify_runtime()
    args = build_parser().parse_args()

    input1 = resolve_input_path(args.system1)
    input2 = resolve_input_path(args.system2)

    missing_inputs = [str(path) for path in (input1, input2) if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"Missing input file(s): {', '.join(missing_inputs)}")

    output_dir = resolve_input_path(args.output_dir) if args.output_dir else default_output_dir(input1, input2)
    output_dir.mkdir(parents=True, exist_ok=True)

    label1 = args.label1 or infer_label(input1)
    label2 = args.label2 or infer_label(input2)

    json1 = ensure_json(input1, force=args.force)
    json2 = ensure_json(input2, force=args.force)

    normalized_alphas = [(raw_alpha, normalize_alpha(raw_alpha)) for raw_alpha in args.alpha]

    for raw_alpha, normalized_alpha in normalized_alphas:
        output_path = build_output_path(
            output_dir=output_dir,
            label1=label1,
            label2=label2,
            desired_format=args.format,
            raw_alpha=raw_alpha,
            normalized_alpha=normalized_alpha,
            raw_alphas=args.alpha,
        )
        render_pair(
            path1=json1,
            path2=json2,
            output_path=output_path,
            alpha=normalized_alpha,
            label1=label1,
            label2=label2,
            desired_format=args.format,
            force=args.force,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
