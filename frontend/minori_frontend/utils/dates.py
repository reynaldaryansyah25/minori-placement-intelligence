"""Date and time conversions in Asia/Jakarta (WIB) timezone."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

ID_MONTHS = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Mei",
    "Jun",
    "Jul",
    "Agu",
    "Sep",
    "Okt",
    "Nov",
    "Des",
]


def now_wib() -> datetime:
    """Current aware datetime in Asia/Jakarta."""
    return datetime.now(JAKARTA_TZ)


def parse_to_wib(value: str | datetime | date | None) -> datetime | None:
    """Parse string or naive/aware datetime into Asia/Jakarta aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=JAKARTA_TZ)
        return value.astimezone(JAKARTA_TZ)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, 0, 0, tzinfo=JAKARTA_TZ)
    if isinstance(value, str):
        try:
            # Handle standard ISO strings
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=JAKARTA_TZ)
            return dt.astimezone(JAKARTA_TZ)
        except Exception:
            return None
    return None


def format_datetime_id(value: str | datetime | date | None, with_timezone: bool = True) -> str:
    """Format to readable Indonesian string: e.g. '16 Okt 2026, 14:00 WIB'."""
    parsed = parse_to_wib(value)
    if parsed is None:
        return "—"
    month_name = ID_MONTHS[parsed.month]
    time_str = parsed.strftime("%H:%M")
    tz_suffix = " WIB" if with_timezone else ""
    return f"{parsed.day} {month_name} {parsed.year}, {time_str}{tz_suffix}"


def format_date_id(value: str | datetime | date | None) -> str:
    """Format date to Indonesian string: e.g. '16 Okt 2026'."""
    parsed = parse_to_wib(value)
    if parsed is None:
        return "—"
    month_name = ID_MONTHS[parsed.month]
    return f"{parsed.day} {month_name} {parsed.year}"


def to_iso_wib(dt: datetime) -> str:
    """Ensure timezone is aware Asia/Jakarta and return ISO string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JAKARTA_TZ)
    return dt.astimezone(JAKARTA_TZ).isoformat()
