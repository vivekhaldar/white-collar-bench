"""A uniform issue type for validators and world checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    code: str  # short machine-readable code, e.g. "link.missing"
    message: str
    path: str | None = None  # file or record ID the issue concerns

    def to_dict(self) -> dict:
        return asdict(self)

    def format(self) -> str:
        loc = f"{self.path}: " if self.path else ""
        return f"{self.severity.upper():7} {loc}[{self.code}] {self.message}"


def error(code: str, message: str, path: str | None = None) -> Issue:
    return Issue("error", code, message, path)


def warning(code: str, message: str, path: str | None = None) -> Issue:
    return Issue("warning", code, message, path)
