import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
DATA_PATH_1 = PROJECT_ROOT / "1-gram" / "boys_1968.json"
DATA_PATH_2 = PROJECT_ROOT / "1-gram" / "boys_1968.json"
OUTPUT_PATH = PROJECT_ROOT / "test.pdf"


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
            "Run one of:\n"
            rf"  {expected_python} {Path(__file__).resolve()}\n"
            rf"  source /c/Users/twebster/Desktop/PoCS/humans/.venv/Scripts/activate && python {Path(__file__).name}"
        )

    if shutil.which("node") is None:
        raise RuntimeError(
            "Node.js was not found on PATH. Install Node globally or run this script "
            "from a shell where `node` is available."
        )

    missing_inputs = [str(path) for path in (DATA_PATH_1, DATA_PATH_2) if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"Missing input file(s): {', '.join(missing_inputs)}")


def main() -> None:
    ensure_utf8_runtime()
    verify_runtime()
    from py_allotax.generate_svg import generate_svg

    generate_svg(
        str(DATA_PATH_1),
        str(DATA_PATH_2),
        str(OUTPUT_PATH),
        "0.17",
        "Boys 1968",
        "Boys 1968",
    )


if __name__ == "__main__":
    main()
