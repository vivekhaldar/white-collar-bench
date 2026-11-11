"""Date helpers. Benchmark dates are ISO strings: 'YYYY-MM-DD' or full ISO datetimes."""

from __future__ import annotations

import datetime as dt
import re

from wcb.util.text import (
    CLAUSE_BREAKS,
    CURRENT_MARKERS,
    HISTORY_MARKERS,
    framing,
    marked_tokens,
    normalize_marked,
)

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


#: Month names and abbreviations as a regex alternation, longest first.
_MONTH_ALT = "|".join(sorted({*MONTHS, *(m[:3] for m in MONTHS), "sept"}, key=len, reverse=True))
_MONTH_NUM = {
    **{m: i for i, m in enumerate(MONTHS, 1)},
    **{m[:3]: i for i, m in enumerate(MONTHS, 1)},
    "sept": 9,
}
_ORD = r"(?:st|nd|rd|th)?"
_YEAR_TAIL = r"(?:,?\s*(\d{4})\b(?![/-][0-9]))?"
#: Date mentions in normalized text: (kind, pattern). Groups give year/month/day by kind.
_DATE_PATTERNS = (
    ("iso", re.compile(r"(?<![0-9])(\d{4})-(\d{1,2})-(\d{1,2})(?![0-9])")),
    ("md", re.compile(r"(?<![0-9/])(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![0-9/])")),
    ("month_day", re.compile(rf"\b({_MONTH_ALT})\b\.?\s*(\d{{1,2}}){_ORD}\b{_YEAR_TAIL}")),
    ("day_month", re.compile(rf"\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?({_MONTH_ALT})\b\.?{_YEAR_TAIL}")),
)
_LONE_YEAR = re.compile(r"(?<![0-9/-])\b(20\d{2})\b(?![/-][0-9])")
#: A date without a year takes the year that puts it this many days before to
#: `365 - YEARLESS_BEFORE_DAYS` days after the reference date.
YEARLESS_BEFORE_DAYS = 91


def date_mentions(norm: str) -> list[tuple[int, int, int | None, int, int]]:
    """Date mentions in normalized text: (start, end, year or None, month, day), by position.

    Recognizes ISO dates (`2027-02-05`), `m/d` and `m/d/y`, and month names or abbreviations
    before or after the day (`Feb 5th`, `5 February 2027`, `the 5th of Feb`). Overlapping
    matches keep the earliest, then the longest. Impossible dates are still returned (their
    validity is checked by the caller).
    """
    found = []
    for kind, pat in _DATE_PATTERNS:
        for m in pat.finditer(norm):
            if kind == "iso":
                y, mo, d = int(m[1]), int(m[2]), int(m[3])
            elif kind == "md":
                mo, d = int(m[1]), int(m[2])
                y = None if m[3] is None else int(m[3]) + (2000 if len(m[3]) == 2 else 0)
            elif kind == "month_day":
                mo, d, y = _MONTH_NUM[m[1]], int(m[2]), int(m[3]) if m[3] else None
            else:
                d, mo, y = int(m[1]), _MONTH_NUM[m[2]], int(m[3]) if m[3] else None
            found.append((m.start(), m.end(), y, mo, d))
    out, taken_until = [], -1
    for f in sorted(found, key=lambda f: (f[0], -(f[1] - f[0]))):
        if f[0] >= taken_until:
            out.append(f)
            taken_until = f[1]
    return out


def _year_for(month: int, day: int, *, today: str | None, default_year: int | None) -> int | None:
    """The year of a year-less date: nearest-window around `today`, else `default_year`."""
    if today:
        ref = parse_date(today)
        lo = ref - dt.timedelta(days=YEARLESS_BEFORE_DAYS)
        for y in (ref.year - 1, ref.year, ref.year + 1):
            try:
                d = dt.date(y, month, day)
            except ValueError:
                continue
            if lo <= d < lo + dt.timedelta(days=365):
                return y
        return ref.year
    return default_year


def normalize_date_text(
    s: str, *, default_year: int | None = None, today: str | None = None
) -> str | None:
    """Parse the one current date in a free-text answer into 'YYYY-MM-DD'; None on failure.

    Every date mention is found (see `date_mentions`). A mention framed as past or rejected
    ("moved from 29 Jan", "was 29 Jan", "not 29 Jan"; `wcb.util.text.framing`) is ignored. If
    the remaining mentions name one date, that is the answer. If they name several, the one
    framed as current ("to 5 Feb", "now 5 Feb", "29 Jan -> 5 Feb") wins when there is exactly
    one; otherwise the text is ambiguous and the result is None.

    A mention without a year takes the only standalone year in the text, if there is exactly
    one; otherwise, with `today` (an ISO date), the year that puts it between
    `YEARLESS_BEFORE_DAYS` (91) days before and about nine months after `today`, so
    "December 30" in early January is the previous December; otherwise `default_year`. With
    no year available the mention is skipped. Impossible dates (`Feb 30`) are skipped.
    """
    if s is None:
        return None
    norm = normalize_marked(str(s))
    current: list[str] = []
    marked: list[str] = []
    for _, _, iso, role in _resolved_mentions(norm, today=today, default_year=default_year):
        if iso is None or role == "history":
            continue
        current.append(iso)
        if role == "current":
            marked.append(iso)
    if len(set(current)) == 1:
        return current[0]
    if len(set(marked)) == 1:
        return marked[0]
    return None


def _resolved_mentions(
    norm: str, *, today: str | None, default_year: int | None
) -> list[tuple[int, int, str | None, str]]:
    """`date_mentions` of normalized text as (start, end, ISO date or None, framing).

    The year rules are those of `normalize_date_text`. The date is None when the mention has
    no year available or is impossible. The framing is that of `wcb.util.text.framing`,
    looked at from the end of the previous mention.
    """
    mentions = date_mentions(norm)
    taken = [(a, b) for a, b, *_ in mentions]
    lone = {
        int(m[1])
        for m in _LONE_YEAR.finditer(norm)
        if not any(a <= m.start() < b for a, b in taken)
    }
    text_year = next(iter(lone)) if len(lone) == 1 else None
    out: list[tuple[int, int, str | None, str]] = []
    prev_end = 0
    for start, end, y, mo, d in mentions:
        role = framing(norm[prev_end:end], start - prev_end)
        prev_end = end
        if y is None:
            y = text_year or _year_for(mo, d, today=today, default_year=default_year)
        iso = None
        if y is not None:
            try:
                iso = dt.date(y, mo, d).isoformat()
            except ValueError:
                iso = None
        out.append((start, end, iso, role))
    return out


_WEEKDAYS = (
    "monday tuesday wednesday thursday friday saturday sunday "
    "mon tue tues wed weds thu thur thurs fri sat sun"
).split()
#: What may come before the date a value leads with: "by" or "due", then a weekday.
_LEAD_PREFIX = re.compile(
    rf"^\s*(?:(?:due|by)\s+)?(?:(?:{'|'.join(sorted(_WEEKDAYS, key=len, reverse=True))})"
    r"\b\.?,?\s*)?$"
)
#: What may follow the date a value leads with: the end, or punctuation that sets off the rest
#: ("2027-02-05 (moved from 29 Jan)", "Fri 5 Feb - Cora confirmed", "5 Feb; ...").
_LEAD_END = re.compile(r"\s*(?:$|[(\[;:,.!?]|-(?!>))")
#: Dashes that set off the rest of a value; `normalize` would drop them.
_DASHES = ("—", "–", "―", "‒")
#: Markers that restate a date as the current one, unlike a bare "to" ("sent it to Jalen on").
_RESTATED_CURRENT = frozenset({"now", "currently", "new", "->", "=>"})


def leading_date(
    s: str | None, *, default_year: int | None = None, today: str | None = None
) -> str | None:
    """The date a free-text value leads with, as 'YYYY-MM-DD'; None if it leads with none.

    A value leads with a date when it starts with one (in any form `date_mentions` knows,
    optionally after "by" or "due" and a weekday: "2027-02-05", "Fri 5 Feb 2027", "By Tue 9
    November") and the date is the whole value or is set off from the rest by punctuation
    or a dash: "2027-02-05 (moved from 29 Jan on 12 Jan)". That date is the answer and the
    rest is context, so other dates in the rest (an assignment or completion date, a
    superseded target) do not make the value ambiguous. Year rules are those of
    `normalize_date_text`.

    There is no leading date, so the caller should read the whole text instead, when:

    * the leading date is followed straight away by a different one, as in a list
      ("Jan 29, Feb 5");
    * the rest gives a different date as the current one with "now", "currently", "new" or
      an arrow ("29 Jan (now 5 Feb)");
    * the leading date is impossible or has no year available.

    Hedge words are not checked here; see `wcb.grade.answers.grade_point`.
    """
    if s is None:
        return None
    text = str(s)
    for dash in _DASHES:
        text = text.replace(dash, " - ")
    norm = normalize_marked(text)
    mentions = _resolved_mentions(norm, today=today, default_year=default_year)
    if not mentions:
        return None
    start, end, lead, _ = mentions[0]
    if lead is None or not _LEAD_PREFIX.match(norm[:start]) or not _LEAD_END.match(norm, end):
        return None
    if len(mentions) > 1:
        nxt_start, _, nxt, _ = mentions[1]
        if nxt != lead and re.fullmatch(r"[\s(\[;:,.!?-]*", norm[end:nxt_start]):
            return None  # "Jan 29, Feb 5": a list of dates
    for m_start, _, iso, _ in mentions[1:]:
        if iso not in (None, lead) and _restated_as_current(norm, m_start):
            return None
    return lead


def _restated_as_current(norm: str, start: int) -> bool:
    """True if the nearest marker before `start`, in its clause, is in `_RESTATED_CURRENT`."""
    for tok, _, _ in reversed(marked_tokens(norm[:start])):
        if tok in CLAUSE_BREAKS:
            return False
        if tok in HISTORY_MARKERS or tok in CURRENT_MARKERS:
            return tok in _RESTATED_CURRENT
    return False
