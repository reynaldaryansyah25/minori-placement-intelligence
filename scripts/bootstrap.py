"""Create the local Python environment and private configuration."""

import re
import secrets
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_logged(command: list[str], log) -> None:
    """Stream installer output to the console and an ignored local log."""
    with subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    ) as process:
        for line in process.stdout:
            print(line, end="")
            log.write(line)
            log.flush()
        if process.wait() != 0:
            raise subprocess.CalledProcessError(process.returncode, command)


def initialize_env_file() -> None:
    """Preserve existing values and generate a key only when missing or blank."""
    target = ROOT / ".env"
    text = (
        target.read_text(encoding="utf-8")
        if target.exists()
        else (ROOT / ".env.example").read_text(encoding="utf-8")
    )
    entry = re.search(r"^N8N_ENCRYPTION_KEY=(.*)$", text, flags=re.MULTILINE)
    if entry is None:
        text += "\nN8N_ENCRYPTION_KEY=" + secrets.token_hex(32) + "\n"
    elif entry.group(1).strip() in {"", '""', "''"}:
        text = (
            text[: entry.start()]
            + ("N8N_ENCRYPTION_KEY=" + secrets.token_hex(32))
            + text[entry.end() :]
        )
    target.write_text(text, encoding="utf-8")
    token_entry = re.search(r"^INTERNAL_API_TOKEN=(.*)$", text, flags=re.MULTILINE)
    if token_entry is None:
        text += "\nINTERNAL_API_TOKEN=" + secrets.token_urlsafe(48) + "\n"
    elif token_entry.group(1).strip() in {"", '""', "''"}:
        text = (
            text[: token_entry.start()]
            + "INTERNAL_API_TOKEN="
            + secrets.token_urlsafe(48)
            + text[token_entry.end() :]
        )
    reviewer_entry = re.search(r"^REVIEWER_API_TOKEN=(.*)$", text, flags=re.MULTILINE)
    if reviewer_entry is None:
        text += "\nREVIEWER_API_TOKEN=" + secrets.token_urlsafe(32) + "\n"
    elif reviewer_entry.group(1).strip() in {"", '""', "''"}:
        text = (
            text[: reviewer_entry.start()]
            + "REVIEWER_API_TOKEN="
            + secrets.token_urlsafe(32)
            + text[reviewer_entry.end() :]
        )
    target.write_text(text, encoding="utf-8")
    print("Private .env configured; existing non-empty values preserved.")


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required. Run this script with a Python 3.12 interpreter.")
    initialize_env_file()
    environment = ROOT / ".venv"
    interpreter = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    pip_launcher = environment / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip")
    if not interpreter.exists() or not pip_launcher.exists():
        print("Creating .venv with Python 3.12...")
        venv.EnvBuilder(with_pip=True).create(environment)
    constraints = (
        ["--constraint", str(ROOT / "requirements.lock")]
        if (ROOT / "requirements.lock").exists()
        else []
    )
    results = ROOT / "test-results"
    results.mkdir(exist_ok=True)
    with (results / "installation.log").open("w", encoding="utf-8") as log:
        run_logged([str(interpreter), "-m", "pip", "install", "--upgrade", "pip"], log)
        run_logged(
            [str(interpreter), "-m", "pip", "install", *constraints, "-e", ".[frontend,dev]"],
            log,
        )
        run_logged([str(interpreter), "-m", "pip", "check"], log)
    print("Dependencies installed. Run the virtual environment's Python with scripts/verify.py.")


if __name__ == "__main__":
    main()
