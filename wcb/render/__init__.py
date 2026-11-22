"""Artifact renderers: turn simulated communications into inbox files (docs/generator.md).

`render_world(plan, sim, world_dir, seed=...)` writes every communication of a simulation as
one or more files under `world_dir/inbox/<date>/` and returns their `artifact.emit` events
(docs/formats.md §1.2). Channels:

| Communication kind | Artifact | Module |
|---|---|---|
| `email` | `em-NNNN.eml` | `wcb.render.email` |
| `chat_dm`, `chat_channel` | `ch-NNNN.json` | `wcb.render.chat` |
| `meeting` | `mt-NNNN.vtt` and/or `mn-NNNN.md` (or a voice debrief `nt-NNNN.md`) | `wcb.render.transcript`, `wcb.render.notes` |
| `note`, `voice_memo` | `nt-NNNN.md` | `wcb.render.notes` |
| `calendar_*` | `ca-NNNN.ics` | `wcb.render.calendar` |
| `document` | `dc-NNNN.{docx,xlsx,pdf,md}` | `wcb.render.documents` |

After writing, `verify_artifacts` re-reads every file the way `wcb world check` does and raises
`RenderError` if a planted secret is missing from its file, or if an artifact that reveals a
commitment or decision does not contain all of its keywords.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wcb.render import calendar as cal_r
from wcb.render import chat as chat_r
from wcb.render import documents as doc_r
from wcb.render import email as email_r
from wcb.render import notes as notes_r
from wcb.render import transcript as mt_r
from wcb.render.context import RenderContext, Rendered
from wcb.render.phrases import missing_keywords
from wcb.world.comms import PREFIX_CHANNEL, Communication


class RenderError(RuntimeError):
    """A rendered artifact does not carry what it claims to reveal."""


def render_comm(ctx: RenderContext, comm: Communication) -> list[Rendered]:
    """Render one communication into its artifacts (in `comm.artifacts` order)."""
    if comm.kind == "email":
        return email_r.render(ctx, comm)
    if comm.kind in ("chat_dm", "chat_channel"):
        return chat_r.render(ctx, comm)
    if comm.kind.startswith("calendar_"):
        return cal_r.render(ctx, comm)
    if comm.kind == "document":
        return doc_r.render(ctx, comm)
    if comm.kind in ("note", "voice_memo"):
        return [notes_r.render_note(ctx, comm, comm.artifacts[0])]
    if comm.kind == "meeting":
        out = []
        for aid in comm.artifacts:
            if aid.startswith("mt-"):
                out.append(mt_r.render(ctx, comm, aid))
            elif aid.startswith("mn-"):
                out.append(notes_r.render_meeting_notes(ctx, comm, aid))
            else:
                out.append(notes_r.render_note(ctx, comm, aid))
        return out
    raise RenderError(f"{comm.id}: no renderer for kind {comm.kind!r}")


def choose_injection(ctx: RenderContext) -> str | None:
    """The one noise email per world that carries an instruction-like footer."""
    episode = set(ctx.plan["calendar"]["episode"]["days"])
    for c in ctx.sim.comms:
        if c.kind == "email" and c.noise and c.date in episode and \
                (c.extra.get("noise_kind") in ("service_desk", "newsletter", "status", "marketing")):
            return c.artifacts[0]
    return next((c.artifacts[0] for c in ctx.sim.comms if c.kind == "email" and c.noise), None)


def render_world(plan: dict, sim: Any, world_dir: Path, *, seed: int, rewriter: Any = None,
                 first_event: int | None = None) -> tuple[list[dict], RenderContext]:
    """Write all artifacts of `sim` under `world_dir/inbox/` and return their `artifact.emit` events.

    Adds document attachments to the simulation first (`documents.plan_attachments`). Event IDs
    continue after the last world event unless `first_event` says otherwise."""
    world_dir = Path(world_dir)
    doc_r.plan_attachments(plan, sim, seed)
    ctx = RenderContext(plan, sim, seed=seed, rewriter=rewriter)
    ctx.injection_artifact = choose_injection(ctx)
    n = first_event if first_event is not None else len(sim.events)
    first_art = {c.id: c.artifacts[0] for c in sim.comms if c.artifacts}
    emits: list[dict] = []
    for comm in sim.comms:
        rendered = render_comm(ctx, comm)
        if [r.artifact for r in rendered] != list(comm.artifacts):
            raise RenderError(f"{comm.id}: rendered {[r.artifact for r in rendered]}, expected {comm.artifacts}")
        for k, r in enumerate(rendered):
            rel = f"inbox/{comm.date}/{r.artifact}{r.ext}"
            path = world_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if r.writer is not None:
                r.writer(path)
            elif isinstance(r.content, bytes):
                path.write_bytes(r.content)
            else:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(r.content or "")
            secrets = [s for s in comm.secrets if r.content and isinstance(r.content, str) and s in r.content]
            n += 1
            emits.append({
                "id": f"e-{n:04d}",
                "t": comm.received_at,
                "type": "artifact.emit",
                "artifact": r.artifact,
                "channel": PREFIX_CHANNEL[r.artifact[:2]],
                "path": rel,
                "received_at": comm.received_at,
                "reveals": list(r.reveals if r.reveals is not None else comm.reveals()),
                "noise": bool(comm.noise),
                "challenges": list(dict.fromkeys([*comm.challenges, *r.challenges])),
                "secrets": secrets,
                "title": (r.title or r.artifact).strip()[:160],
                "parent": first_art.get(comm.parent) if comm.parent else None,
            })
            if k == 0:
                missing = [s for s in comm.secrets if s not in secrets]
                if missing and len(rendered) == 1:
                    raise RenderError(f"{r.artifact}: secrets {missing} were not written into the file")
    if plan["generator"]["version"] >= 2:
        emits.extend(notes_r.write_contact_updates(ctx, world_dir, emits, n))
    verify_artifacts(world_dir, sim.events, emits)
    return emits, ctx


def artifact_text(path: Path) -> str | None:
    """Searchable text of an artifact, as `wcb world check` reads it (PDFs via the office module)."""
    from wcb.render.office import extract_text
    from wcb.world.check import artifact_text as check_text

    if path.suffix.lower() == ".pdf":
        return extract_text(path)
    return check_text(path)


def verify_artifacts(world_dir: Path, events: list[dict], emits: list[dict]) -> None:
    """Fail loudly when an artifact misses a secret it declares or a keyword of what it reveals.

    - every `secrets` string occurs literally in its file;
    - every artifact revealing a `commitment.create` or `decision.make` contains all of its
      keywords (case-insensitively, as graders match them), and so does at least one artifact
      revealing it.
    """
    from wcb.world.check import raw_text

    ev = {e["id"]: e for e in events}
    problems: list[str] = []
    for a in emits:
        path = Path(world_dir) / a["path"]
        raw = raw_text(path)
        if a["secrets"] and raw is not None:
            for s in a["secrets"]:
                if s not in raw:
                    problems.append(f"{a['artifact']}: secret {s!r} not in file")
        creates = [ev[r] for r in a["reveals"] if ev.get(r, {}).get("type") in ("commitment.create", "decision.make")]
        if not creates:
            continue
        text = artifact_text(path) or ""
        for e in creates:
            miss = missing_keywords(text, list(e.get("keywords") or []))
            if miss:
                problems.append(f"{a['artifact']}: reveals {e['id']} ({e.get('commitment') or e.get('decision')}) "
                                f"but lacks keywords {miss}")
    if problems:
        head = "\n  ".join(problems[:20])
        raise RenderError(f"{len(problems)} rendering problem(s):\n  {head}")


__all__ = ["RenderContext", "RenderError", "Rendered", "choose_injection", "render_comm", "render_world",
           "verify_artifacts"]
