"""Download BankChurners.csv from Kaggle into data/raw/ if it is not already there."""
import shutil
import subprocess
import sys
from pathlib import Path

from src.paths import KAGGLE_DATASET, RAW_CSV, RAW_DIR

MANUAL_STEPS = f"""
Could not download the data automatically. Do this by hand:

  1. Open https://www.kaggle.com/datasets/{KAGGLE_DATASET}
  2. Click Download and unzip the file.
  3. Put BankChurners.csv here: {RAW_CSV}

To fix the automatic download instead, create a Kaggle API token
(Kaggle > Settings > API) and save it under {Path.home() / '.kaggle'}.
"""


def find_kaggle_cli() -> str | None:
    """Prefer the CLI installed next to the running interpreter (the venv)."""
    scripts_dir = Path(sys.executable).parent
    for name in ("kaggle.exe", "kaggle"):
        candidate = scripts_dir / name
        if candidate.exists():
            return str(candidate)
    return shutil.which("kaggle")


def main() -> None:
    if RAW_CSV.exists():
        print(f"Raw data already present: {RAW_CSV}")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cli = find_kaggle_cli()
    if cli is None:
        sys.exit("Kaggle CLI not found." + MANUAL_STEPS)

    result = subprocess.run(
        [cli, "datasets", "download", "-d", KAGGLE_DATASET, "-p", str(RAW_DIR), "--unzip"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not RAW_CSV.exists():
        sys.exit(f"Kaggle download failed:\n{result.stdout}\n{result.stderr}" + MANUAL_STEPS)
    print(f"Downloaded {RAW_CSV}")


if __name__ == "__main__":
    main()
