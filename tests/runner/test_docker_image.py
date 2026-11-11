"""The reference agent image ships pinned readers for every input format (docker/)."""

from __future__ import annotations

import re
import subprocess
import sys

from wcb.paths import repo_root

ROOT = repo_root()
READERS = {"pyyaml", "pypdf", "python-docx", "openpyxl", "python-pptx"}


def _pins() -> dict[str, str]:
    lines = (ROOT / "docker" / "requirements-tools.txt").read_text().splitlines()
    reqs = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
    pins = {}
    for r in reqs:
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9][0-9A-Za-z.]*)", r)
        assert m, f"not pinned to an exact version: {r}"
        pins[m.group(1).lower()] = m.group(2)
    return pins


def test_reader_versions_are_pinned():
    assert set(_pins()) == READERS


def test_dockerfile_installs_the_pinned_readers_at_build_time():
    text = (ROOT / "docker" / "Dockerfile.simple").read_text()
    assert "pip install --no-cache-dir -r requirements-tools.txt" in text
    assert "-c requirements-tools.txt ." in text  # wcb's own PyYAML is pinned too
    assert "poppler-utils" in text
    assert re.search(r"^FROM python:3\.12-slim-\w+", text, re.M)  # a fixed Debian release


def test_adapter_docs_list_the_tools():
    text = (ROOT / "docs" / "adapters.md").read_text()
    section = re.split(r"^## [0-9a-z.]* ?Tools your agent's runtime needs", text, maxsplit=1, flags=re.M)
    assert len(section) == 2
    section = section[1].split("\n## ", 1)[0]
    for name in ("PyYAML", "pypdf", "python-docx", "openpyxl", "python-pptx", "pdftotext"):
        assert name in section
    assert "smoke_tools.py" in section


def test_smoke_script_reports_each_reader(tmp_path):
    note = tmp_path / "nt-0001.md"
    note.write_text("---\nid: notes/sample\n---\nA synthetic note.\n")
    r = subprocess.run(
        [sys.executable, "-I", str(ROOT / "docker" / "smoke_tools.py"), str(tmp_path)],
        capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    # The host environment need not have every reader; the image does.
    assert r.returncode in (0, 1), r.stderr
    for label in ("YAML front matter", "PDF (pypdf)", "DOCX", "XLSX", "PPTX"):
        assert f"  {label}:" in r.stdout
    assert "ok    YAML front matter" in r.stdout
    assert f"ok    {note}" in r.stdout
