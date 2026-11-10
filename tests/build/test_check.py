"""Tests for `wcb world check` (wcb/world/check.py)."""

from __future__ import annotations

import pytest

from wcb.world.check import artifact_text, check_world


def test_mini_world_has_no_errors(mini_world_dir):
    issues = check_world(mini_world_dir)
    assert [i.format() for i in issues if i.severity == "error"] == []


def test_mini_world_has_no_warnings(mini_world_dir):
    assert [i for i in check_world(mini_world_dir) if i.severity == "warning"] == []


def test_stale_summary_warns(editor):
    # Without the same-time summary rewrite (e-0024), Quillon's summary still says 29 January
    # after the target date moves on 11 Jan.
    events = [e for e in editor.events() if e.get("id") != "e-0024"]
    for e in events:
        if e.get("artifact") == "nt-0002":
            e["reveals"] = [r for r in e["reveals"] if r != "e-0024"]
    editor.save(events)
    warnings = [i for i in check_world(editor.root) if i.severity == "warning"]
    assert any(i.code == "summary.stale" and i.path == "e-0020" for i in warnings)


# ---------------------------------------------------------------- targeted breakage
def _move_reveal(ed, eid, src_event, dst_event):
    src, dst = ed.get(src_event), ed.get(dst_event)
    ed.edit(src_event, reveals=[r for r in src["reveals"] if r != eid])
    ed.edit(dst_event, reveals=dst["reveals"] + [eid])


def _move_artifact_to(ed, event_id, new_date):
    a = ed.get(event_id)
    old = ed.root / a["path"]
    new_path = f"inbox/{new_date}/{old.name}"
    (ed.root / new_path).parent.mkdir(parents=True, exist_ok=True)
    old.rename(ed.root / new_path)
    ed.edit(
        event_id,
        path=new_path,
        received_at=f"{new_date}T10:00:00-08:00",
        t=f"{new_date}T10:00:00-08:00",
    )


def _set_meta(ed, **changes):
    meta = ed.meta()
    for k, v in changes.items():
        if v is ...:
            meta.pop(k, None)
        else:
            meta[k] = v
    ed.save_meta(meta)


def _write_stray_file(ed):
    (ed.root / "inbox" / "2027-01-11" / "stray.txt").write_text("not declared\n", encoding="utf-8")


BREAKERS = {
    # world.yaml
    "meta.missing": lambda ed: _set_meta(ed, worker=...),
    "meta.checkpoint": lambda ed: _set_meta(ed, checkpoints=[{"id": "cp1", "date": "2027-01-10"}]),
    "meta.episode": lambda ed: _set_meta(ed, episode={"days": ["2027-01-12", "2027-01-11"]}),
    "meta.worker": lambda ed: _set_meta(ed, worker="p-nobody"),
    # events
    "event.duplicate": lambda ed: ed.edit("e-0016", id="e-0011"),
    "event.type": lambda ed: ed.edit("e-0016", type="fact.change"),
    "event.summary": lambda ed: ed.edit("e-0012", summary=...),
    "event.field": lambda ed: ed.edit("e-0011", debtor=...),
    "entity.prefix": lambda ed: ed.edit("e-0003", kind="person"),
    "object.duplicate": lambda ed: ed.edit("e-0017", commitment="c-002"),
    # references
    "ref.missing": lambda ed: ed.edit("e-0014", debtor="p-nobody"),
    "ref.order": lambda ed: ed.edit("e-0022", t="2027-01-07T11:00:00-08:00"),
    "ref.unknowable": lambda ed: _move_reveal(ed, "e-0006", "e-9005", "e-9008"),
    # knowability
    "reveal.missing": lambda ed: ed.edit(
        "e-9002", reveals=["e-0003", "e-0005", "e-0011", "e-9999"]
    ),
    "reveal.future": lambda ed: ed.edit("e-9002", reveals=["e-0003", "e-0005", "e-0011", "e-0020"]),
    "reveal.before_create": lambda ed: _move_reveal(ed, "e-0014", "e-9005", "e-9011"),
    # artifacts
    "artifact.prefix": lambda ed: ed.edit("e-9003", channel="email"),
    "artifact.missing_file": lambda ed: (ed.root / "inbox/2027-01-06/em-0002.eml").unlink(),
    "artifact.date": lambda ed: ed.edit("e-9004", received_at="2027-01-07T08:00:00-08:00"),
    "artifact.schedule": lambda ed: _move_artifact_to(ed, "e-9006", "2027-01-09"),
    "artifact.path": lambda ed: ed.edit("e-9004", path="inbox/2027-01-06/em-9999.eml"),
    "inbox.undeclared": _write_stray_file,
    "secret.missing": lambda ed: ed.edit("e-9010", secrets=["514227", "not-in-the-file"]),
    # questions
    "question.checkpoint": lambda ed: ed.save_questions(
        [
            {
                "id": "q-1",
                "checkpoint": "cp9",
                "template": "i_owe",
                "params": {"person": "p-cora-velez"},
            }
        ]
    ),
    "question.duplicate": lambda ed: ed.save_questions(
        [{"id": "q-1", "checkpoint": "cp1", "template": "i_owe", "params": {}}] * 2
    ),
    "question.param": lambda ed: ed.save_questions(
        [
            {
                "id": "q-1",
                "checkpoint": "cp1",
                "template": "loop_owner",
                "params": {"commitment": "c-999"},
            }
        ]
    ),
}


@pytest.mark.parametrize("code", sorted(BREAKERS))
def test_broken_copy_reports_error(editor, code):
    assert not editor.codes()  # the copy starts clean
    BREAKERS[code](editor)
    assert code in editor.codes("error")


def test_update_before_create_message_names_dates(editor):
    _move_reveal(editor, "e-0014", "e-9005", "e-9011")
    issue = next(i for i in check_world(editor.root) if i.code == "reveal.before_create")
    assert (
        issue.path == "e-0022" and "2027-01-11" in issue.message and "2027-01-12" in issue.message
    )


def test_invalid_contract_enum_in_attrs(editor):
    e = editor.get("e-0005")
    editor.edit("e-0005", attrs={**e["attrs"], "relationship": "friend"})
    assert "event.field" in editor.codes()


def test_keyword_warnings(editor):
    editor.edit("e-0014", keywords=["volume pricing", "unicorn budget"])
    editor.edit("e-0012", keywords=["reconciliation report"])
    warnings = {(i.code, i.path) for i in check_world(editor.root) if i.severity == "warning"}
    assert ("keyword.absent", "c-004") in warnings
    assert ("keyword.count", "c-002") in warnings
    assert not editor.codes("error")


def test_missing_world_files(tmp_path):
    assert {i.code for i in check_world(tmp_path)} == {"meta.file"}


# ---------------------------------------------------------------- artifact text
def test_artifact_text_decodes_text_formats(mini_world_dir):
    chat = artifact_text(mini_world_dir / "inbox/2027-01-05/ch-0001.json")
    assert "approve my access request" in chat
    ics = artifact_text(mini_world_dir / "inbox/2027-01-11/ca-0001.ics")
    assert "514227" in ics


def test_artifact_text_reads_office_xml_and_skips_binary_pdf(tmp_path):
    import zipfile

    docx = tmp_path / "dc-0001.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr(
            "word/document.xml",
            "<w:document><w:body><w:p><w:r><w:t>Capacity </w:t></w:r><w:r><w:t>model v2</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Owner &amp; reviewer</w:t></w:r></w:p></w:body></w:document>",
        )
    text = artifact_text(docx)
    assert "Capacity model v2" in text and "Owner & reviewer" in text
    pdf = tmp_path / "dc-0002.pdf"
    pdf.write_bytes(b"%PDF-1.4 binary")
    assert artifact_text(pdf) is None
    plain = tmp_path / "dc-0003.pdf"
    plain.write_text("plain text posing as a pdf", encoding="utf-8")
    assert "posing" in artifact_text(plain)


def test_change_question_text_that_includes_the_since_day_warns(editor):
    def since_warnings(text: str, since: str) -> list[str]:
        spec = {"id": "q-1", "checkpoint": "cp2", "template": "project_changes", "text": text,
                "params": {"project": "pr-quillon", "since": since}}  # fmt: skip
        editor.save_questions([spec])
        return [i.code for i in check_world(editor.root) if i.code == "question.since"]

    # Gold lists changes after `since`: "since Friday" with since on that Friday drops Friday.
    assert since_warnings("What changed on Quillon since Friday?", "2027-01-08")
    assert not since_warnings("What changed on Quillon since Friday?", "2027-01-07")
    # cp2 is Tuesday 12 January; "this week" needs since on or before Sunday 10 January.
    assert since_warnings("What changed on Quillon this week?", "2027-01-11")
    assert not since_warnings("What changed on Quillon this week?", "2027-01-10")
