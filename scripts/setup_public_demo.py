"""Configure only public-login variables in the existing ignored .env; never enables Funnel."""

import argparse
import csv
import getpass
import io
import os
import re
import secrets
import subprocess
from pathlib import Path

from minori_frontend.public_auth import password_hash

ROOT = Path(__file__).resolve().parents[1]


def restrict_access(path):
    if os.name == "nt":
        output = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
        sid = next(csv.reader(io.StringIO(output)))[1]
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
            check=True,
            capture_output=True,
        )
    else:
        path.chmod(0o600)


def configure(username, password, *, root=ROOT, generated=False):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
        raise ValueError(
            "Gunakan nama pengguna 3–64 karakter: huruf, angka, titik, garis bawah atau tanda hubung."
        )
    if len(password) < 16 or len(password) > 1024:
        raise ValueError("Kata sandi harus memuat 16–1024 karakter.")
    env = root / ".env"
    if not env.is_file():
        raise ValueError(
            "Konfigurasikan .env aplikasi terlebih dahulu; file tidak dibuat otomatis."
        )
    content = env.read_text(encoding="utf-8")
    values = {
        "PUBLIC_DEMO_USERNAME": username,
        "PUBLIC_DEMO_PASSWORD_HASH": password_hash(password),
    }
    for name, value in values.items():
        line = name + "='" + value + "'"
        pattern = rf"(?m)^{name}=.*$"
        content = (
            re.sub(pattern, lambda _, line=line: line, content)
            if re.search(pattern, content)
            else content.rstrip() + "\n" + line + "\n"
        )
    env.write_text(content, encoding="utf-8")
    if generated:
        access = root / "data/runtime/public-demo-access.txt"
        access.parent.mkdir(parents=True, exist_ok=True)
        # Reserve and protect the file before storing the generated password.
        access.touch(mode=0o600, exist_ok=True)
        restrict_access(access)
        access.write_text(
            f"MINORI public demo — localhost:8502\nNama pengguna: {username}\nKata sandi: {password}\n",
            encoding="utf-8",
        )
        return access
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate a strong password and store it in a private ignored local file.",
    )
    parser.add_argument("--username", default="reviewer")
    args = parser.parse_args()
    if args.generate:
        password = secrets.token_urlsafe(32)
    else:
        password = getpass.getpass("Kata sandi peninjau (minimal 16 karakter): ")
        if password != getpass.getpass("Ulangi kata sandi: "):
            raise SystemExit("Kata sandi tidak sama. Konfigurasi tidak berubah.")
    try:
        access = configure(args.username, password, generated=args.generate)
    except (ValueError, OSError, subprocess.SubprocessError):
        raise SystemExit(
            "Konfigurasi belum disimpan dengan aman. Periksa nama pengguna, panjang kata sandi, dan izin berkas."
        ) from None
    print(
        "Login demo publik dikonfigurasi di .env. Kredensial backend tidak diubah. Funnel tetap nonaktif."
    )
    if access:
        print("Baca kredensial pada berkas privat lokal: " + str(access))


if __name__ == "__main__":
    main()
