"""Tests for the validator's privacy patterns: catch leaks, keep false positives low."""

from pathlib import Path

import pytest

from wcb.contract.validate import (
    credential_value,
    find_secrets,
    is_placeholder,
    looks_random,
    privacy_findings,
)
from wcb.paths import contract_dir
from wcb.store.parse import load_store

LEAKS = [
    ("Join: https://meet.vidlink.example/j/88812345", "privacy.join-link"),
    ("join at meet.vidlink.example/j/88812345 today", "privacy.join-link"),
    ("https://video.example/j/1234567890?pwd=AbCdEf123", "privacy.join-link"),
    ("https://acme.zoom.example/my/ada.quist", "privacy.join-link"),
    ("https://teams.microsoft.example/l/meetup-join/19%3ameeting_abc", "privacy.join-link"),
    ("meet.google.example/abc-defg-hij", "privacy.join-link"),
    ("https://conf.example/meet/j.php?MTID=m1234abcd", "privacy.join-link"),
    ("Meeting ID: 881 2345 6789", "privacy.join-link"),
    ("Passcode: 514227", "privacy.passcode"),
    ("passcode 514 227", "privacy.passcode"),
    ("password: hunter2", "privacy.passcode"),
    ("Password = Tr!cky-Pass", "privacy.passcode"),
    ("pwd=abc123", "privacy.passcode"),
    ("PIN: 4821", "privacy.passcode"),
    ("PIN code 4821", "privacy.passcode"),
    ("access code 123 4567#", "privacy.passcode"),
    ("the one-time code is 908172", "privacy.passcode"),
    ("Dial-in: +1 415 555 0100", "privacy.dial-in"),
    ("dial in +44 20 7946 0958", "privacy.dial-in"),
    ("+1 415 555 0100,,88812345#", "privacy.dial-in"),
    ("key sk-ant-api03-AbCdEf0123456789XyZabc", "privacy.api-key"),
    ("sk-proj-a1B2c3D4e5F6g7H8i9J0", "privacy.api-key"),
    ("AKIAIOSFODNN7EXAMPLE", "privacy.api-key"),
    ("api_key: 9f8e7d6c5b4a39281706", "privacy.api-key"),
    ("Authorization: Bearer abc123def456ghi789", "privacy.api-key"),
    ("token 3f2a9c8e1b7d4f6a0e5c2b9d8a7f6e5d", "privacy.api-key"),
    ("token: Zm9vYmFyQmF6UXV4MTIzNDU2Nzg5MEFiQ2RFZkdo", "privacy.api-key"),
    ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9P", "privacy.api-key"),
    ("-----BEGIN RSA PRIVATE KEY-----", "privacy.api-key"),
]

NOT_LEAKS = [
    "password reset ticket",
    "Passwords must rotate every 90 days",
    "the passcode expired yesterday",
    "a password-protected PDF",
    "Join: [redacted] Passcode: [redacted]",
    "password: [redacted]",
    "PIN [redacted]",
    "PIN: ***",
    "pin the agenda to the channel",
    "dial-in details to follow",
    "The dial-in on 2027-01-12 was cancelled",
    "We had a call in 2027-01-12 10:30",
    "call Ben on +1 415 555 0100",
    "Ben Okoro | +1 (415) 555-0100",
    "123e4567-e89b-12d3-a456-426614174000",
    "loops/send-the-revised-capacity-model-for-the-north-corridor",
    "SendTheRevisedCapacityModelForNorthCorridor2027",
    "Q3-2027-Revenue-Forecast-v2-FINAL-Draft-Larchmont",
    "https://larchmont.example/wiki/quillon-2027-q1",
    "https://docs.larchmont.example/Shared/Quillon/Vendor-Scorecards/2027/Tessellate_v3.xlsx",
    "meet.vidlink.example",
    "As of 2027-01-07: Quillon is in vendor evaluation [src: em-0001, mt-0001]",
    "pwd/notes2027",
    "access code review",
    "the API key rotation for project-2027-q1-north",
    "the bearer of bad news",
    "Message-ID: <em-0001@tessellate.example>",
]


@pytest.mark.parametrize("text, code", LEAKS)
def test_leaks_are_found(text, code):
    found = privacy_findings(text)
    assert [f[2] for f in found] == [code], found


@pytest.mark.parametrize("text", NOT_LEAKS)
def test_ordinary_text_is_not_flagged(text):
    assert privacy_findings(text) == []


def test_benchmark_docs_are_not_flagged():
    """The contract itself talks about passwords and join links without containing any."""
    root = contract_dir().parent
    for rel in ("contract/CONTRACT.md", "docs/formats.md", "docs/scoring.md", "docs/design.md"):
        p = root / rel
        if p.exists():
            assert privacy_findings(p.read_text()) == [], rel


def test_sample_store_text_is_not_flagged(sample_store_dir):
    assert privacy_findings(load_store(sample_store_dir).all_text()) == []


def test_mini_world_inbox_only_flags_the_planted_invite(mini_world_dir):
    secrets = ["https://meet.vidlink.example/j/88812345", "514227"]
    flagged = {
        p.name
        for p in sorted(Path(mini_world_dir, "inbox").rglob("*"))
        if p.is_file() and privacy_findings(p.read_text(), secrets)
    }
    assert flagged == {"ca-0001.ics"}


def test_find_secrets_word_boundaries_and_url_forms():
    text = "ids 88514227 and 514227x are fine; 514227 is not. See meet.vidlink.example/j/88812345."
    found = find_secrets(text, ["514227", "https://meet.vidlink.example/j/88812345", "ab", ""])
    hits = sorted(text[s:e] for s, e, _, _ in found)
    assert hits == ["514227", "meet.vidlink.example/j/88812345"]


def test_secret_is_case_insensitive_and_masked():
    found = privacy_findings("token XYZ-SECRET-77 here", ["xyz-secret-77"])
    assert [f[2] for f in found] == ["privacy.secret"]
    assert "SECRET-77" not in found[0][3] and "secret-77" not in found[0][3]


def test_overlapping_findings_reported_once():
    text = "Join https://meet.vidlink.example/j/88812345?pwd=Abc123 now"
    found = privacy_findings(text, ["https://meet.vidlink.example/j/88812345"])
    assert [f[2] for f in found] == ["privacy.secret"]


@pytest.mark.parametrize(
    "value, sep, flagged",
    [
        ("514227", ": ", True),
        ("hunter2", " ", True),
        ("Tr!ckyPass", ": ", True),
        ("Swordfish", ": ", False),
        ("reset", " ", False),
        ("[redacted", ": ", False),
        ("2027-01-12", ": ", False),
        ("abc1", "", False),
        ("12", ": ", False),
    ],
)
def test_credential_value(value, sep, flagged):
    assert credential_value(value, sep) is flagged


@pytest.mark.parametrize("value", ["[redacted]", "REDACTED", "***", "xxxx", "n/a", "<hidden>"])
def test_placeholders(value):
    assert is_placeholder(value)


def test_looks_random():
    assert looks_random("Zm9vYmFyQmF6UXV4MTIzNDU2Nzg5MEFiQ2RFZkdo")
    assert not looks_random("SendTheRevisedCapacityModelForNorthCorridor2027")
    assert not looks_random("send-the-revised-capacity-model-for-the-north-corridor")
