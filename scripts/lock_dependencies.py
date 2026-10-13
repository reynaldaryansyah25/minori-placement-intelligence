"""Save resolved versions as pip constraints, excluding the editable project."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    output = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze", "--exclude-editable"], text=True
    )
    entries = sorted(
        line for line in output.splitlines() if line and not line.startswith("#") and "==" in line
    )
    (ROOT / "requirements.lock").write_text(
        "# Resolved Python 3.12 dependency constraints.\n"
        "# Direct requirements are defined only in pyproject.toml.\n"
        "# Regenerate in the project .venv after deliberate dependency updates.\n"
        + "\n".join(entries)
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(entries)} resolved dependency versions.")


if __name__ == "__main__":
    main()
