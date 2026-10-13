"""Form and input validation helpers for candidate and vacancy data."""

import re
from datetime import date


def validate_required(value: str | None, field_name: str) -> str | None:
    if not value or not value.strip():
        return f"{field_name} wajib diisi."
    return None


def validate_reference(reference: str | None) -> str | None:
    if not reference or not reference.strip():
        return "Nomor referensi wajib diisi."
    cleaned = reference.strip()
    if len(cleaned) < 3 or len(cleaned) > 80:
        return "Nomor referensi harus terdiri dari 3 hingga 80 karakter."
    if not re.match(r"^[A-Za-z0-9_\-\.]+$", cleaned):
        return "Referensi hanya boleh menggunakan huruf, angka, tanda strip (-), titik, dan underscore."
    return None


def validate_positive_int(
    value: int | None, field_name: str, allow_zero: bool = False
) -> str | None:
    if value is None:
        return f"{field_name} wajib diisi."
    if allow_zero and value < 0:
        return f"{field_name} tidak boleh negatif."
    if not allow_zero and value <= 0:
        return f"{field_name} harus lebih besar dari 0."
    return None


def validate_date_range(
    start: date | None,
    end: date | None,
    msg: str = "Tanggal selesai tidak boleh sebelum tanggal mulai.",
) -> str | None:
    if start and end and end < start:
        return msg
    return None
