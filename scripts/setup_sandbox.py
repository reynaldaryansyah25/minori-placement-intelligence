"""Add distinct sandbox credentials to the existing ignored .env without changing other values."""

import re
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / ".env"
    if not destination.is_file():
        raise SystemExit("Prepare the existing .env and public login first")
    original = destination.read_text(encoding="utf-8")
    values = {
        line.partition("=")[0].strip(): line.partition("=")[2].strip().strip("\"'")
        for line in original.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    updates = []
    revised = original
    for name in ("SANDBOX_GATEWAY_TOKEN", "SANDBOX_WORKER_TOKEN"):
        if not values.get(name):
            line = name + "=" + secrets.token_urlsafe(48)
            if name in values:
                revised = re.sub(r"(?m)^\s*" + name + r"\s*=.*$", line, revised)
            else:
                updates.append(line)
    if updates:
        revised += "\n# Isolated interactive public sandbox\n" + "\n".join(updates) + "\n"
    if revised != original:
        destination.write_text(revised, encoding="utf-8")
    print("Sandbox credentials prepared in .env; existing credentials and public login unchanged.")


if __name__ == "__main__":
    main()
