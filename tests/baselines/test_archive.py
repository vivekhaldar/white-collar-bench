import shutil

from wcb.baselines.archive import archive_inbox, redact, write_daily_log


def test_redact_secrets():
    s = "Join: https://meet.vidlink.example/j/88812345 Passcode: 514227 key sk-abcdefghijklmnop1234"
    out = redact(s)
    assert "88812345" not in out and "514227" not in out and "sk-abcdef" not in out
    assert "Join:" in out and "Passcode:" in out


def test_archive_copies_and_logs(tmp_path, mini_world_dir):
    ws = tmp_path / "ws"
    shutil.copytree(mini_world_dir / "inbox" / "2027-01-11", ws / "inbox" / "2027-01-11")
    entries = archive_inbox(ws, "2027-01-11")
    write_daily_log(ws, "2027-01-11", entries)
    archived = sorted(p.name for p in (ws / "sources" / "2027-01-11").iterdir())
    assert "ca-0001.ics" in archived and "nt-0002.md" in archived
    assert "514227" not in (ws / "sources" / "2027-01-11" / "ca-0001.ics").read_text()
    assert (ws / "logs" / "2027-01-11.md").read_text().startswith("---\nid: logs/2027-01-11")
