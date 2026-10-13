"""Formatting utilities for scores, labels, and text displays."""

from minori_frontend.utils.constants import PROGRAM_MAP, STATUS_COLORS


def score_to_100(score: float | None) -> float | None:
    """Convert 0.0..1.0 float score to 0..100 scale."""
    if score is None:
        return None
    return round(score * 100, 1)


def format_score(score: float | None, suffix: str = "/ 100") -> str:
    """Format matching score for display."""
    if score is None:
        return "—"
    scaled = score_to_100(score)
    return f"{scaled:.1f} {suffix}".strip()


def format_program(program: str | None) -> str:
    """Format program identifier to Indonesian human label."""
    if not program:
        return "—"
    return PROGRAM_MAP.get(program.lower(), program.upper())


def format_status_label(status: str | None) -> str:
    """Get clean domain label from status code."""
    if not status:
        return "—"
    config = (
        STATUS_COLORS.get(status)
        or STATUS_COLORS.get(status.lower())
        or STATUS_COLORS.get(status.upper())
    )
    if config:
        return config["label"]
    return "Belum tersedia"


def truncate_text(text: str | None, max_length: int = 40) -> str:
    """Truncate long text cleanly with ellipsis."""
    if not text:
        return "—"
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def clean_uuid_display(uuid_val: str | None, chars: int = 8) -> str:
    """Display short readable tail of UUID."""
    if not uuid_val:
        return "—"
    clean = str(uuid_val).replace("-", "")
    return clean[-chars:].upper()


def format_currency_yen(amount: int | float | None) -> str:
    """Format numeric amount as Japanese Yen string (e.g. ¥250,000)."""
    if amount is None:
        return "—"
    return f"¥{int(amount):,}"
