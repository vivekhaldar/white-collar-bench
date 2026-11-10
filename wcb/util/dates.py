"""Date helpers. Benchmark dates are ISO strings: 'YYYY-MM-DD' or full ISO datetimes."""

from __future__ import annotations

import datetime as dt
import re

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(s: str | dt.date) -> dt.date:
    if isinstance(s, dt.datetime):
        return s.date()
    if isinstance(s, dt.date):
        return s
    return dt.date.fromisoformat(str(s)[:10])


def parse_dt(s: str | dt.datetime) -> dt.datetime:
    if isinstance(s, dt.datetime):
        return s
    s = str(s)
    if DATE_RE.match(s):
        return dt.datetime.fromisoformat(s + "T00:00:00")
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def date_of(s: str) -> str:
    """The calendar date part of an ISO date or datetime string."""
    return str(s)[:10]


def end_of_day(date: str) -> str:
    return f"{date_of(date)}T23:59:59"


def add_days(date: str, n: int) -> str:
    return (parse_date(date) + dt.timedelta(days=n)).isoformat()


def is_business_day(date: str) -> bool:
    return parse_date(date).weekday() < 5


def next_business_day(date: str) -> str:
    d = parse_date(date) + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def business_days_between(a: str, b: str) -> int:
    """Signed number of business days from a to b (0 when same day)."""
    da, db = parse_date(a), parse_date(b)
    sign = 1
    if db < da:
        da, db, sign = db, da, -1
    n = 0
    d = da
    while d < db:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return sign * n


def date_range(start: str, end: str) -> list[str]:
    d, e = parse_date(start), parse_date(end)
    out = []
    while d <= e:
        out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def text_variants(date: str) -> list[str]:
    """Common ways a date may be written in prose, lowercased. Used by heuristic graders."""
    d = parse_date(date)
    m = MONTHS[d.month - 1]
    mon = m[:3]
    day = d.day
    return sorted(
        {
            d.isoformat(),
            f"{m} {day}",
            f"{mon} {day}",
            f"{day} {m}",
            f"{day} {mon}",
            f"{m} {day}{_ord(day)}",
            f"{mon} {day}{_ord(day)}",
            f"{day}{_ord(day)} {m}",
            f"{day}{_ord(day)} {mon}",
            f"{d.month}/{day}",
            f"{d.month:02d}/{day:02d}",
        }
    )


def _ord(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def normalize_date_text(s: str, *, default_year: int | None = None) -> str | None:
    """Best-effort parse of a free-text date into 'YYYY-MM-DD'. Returns None on failure."""
    if s is None:
        return None
    s = str(s).strip().lower()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return None
    year = default_year
    ym = re.search(r"\b(20\d{2})\b", s)
    if ym:
        year = int(ym[1])
        s = s.replace(ym[1], " ")
    if year is None:
        return None
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", s)
    if m:
        try:
            return dt.date(year, int(m[1]), int(m[2])).isoformat()
        except ValueError:
            return None
    for i, name in enumerate(MONTHS, 1):
        for token in (name, name[:3]):
            m = re.search(rf"\b{token}\b\.?\s*(\d{{1,2}})(st|nd|rd|th)?\b", s) or re.search(
                rf"\b(\d{{1,2}})(st|nd|rd|th)?\s+(of\s+)?{token}\b", s
            )
            if m:
                try:
                    return dt.date(year, i, int(m[1])).isoformat()
                except ValueError:
                    return None
    return None
