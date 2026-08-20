import json
from pathlib import Path
from unittest.mock import patch

import pytest
from bernstein.core.models import Task

from bernstein.core.agents.spawner_core import AgentSpawner


class DummySpawner:
    """Minimal stand-in for AgentSpawner to test _render_mailbox_section."""

    def __init__(self, workdir: Path):
        self._workdir = workdir


def _create_task(task_id: str = "T-1") -> Task:
    return Task(
        id=task_id,
        title="Test Task",
        description="Test description",
        role="backend",
    )


def _write_message(journal: Path, task_id: str = "T-1", seq: int = 0) -> None:
    """Write a single valid mailbox message to the journal."""
    journal.parent.mkdir(parents=True, exist_ok=True)
    msg = {
        "seq": seq,
        "task_id": task_id,
        "sender": "test-sender",
        "sender_card_fingerprint": "unregistered",
        "kind": "finding",
        "body": "test body",
        "body_hash": "sha256:dummy",
        "redaction_count": 0,
        "timestamp": 1234567890.0,
        "prev_entry_hash": "genesis",
        "entry_hash": "hmac-sha256:dummy",
        "signer_public_key_pem": "",
        "signature": "",
        "schema_version": 1,
    }
    with journal.open("w", encoding="utf-8") as f:
        f.write(json.dumps(msg) + "\n")


def test_a_delivered_message_produces_a_consumption_chain_entry(tmp_path: Path) -> None:
    from bernstein.core.security.audit_chain import AuditChainStore

    workdir = tmp_path
    journal = workdir / ".sdd" / "runtime" / "mailbox.jsonl"
    _write_message(journal)

    spawner = DummySpawner(workdir)
    tasks = [_create_task()]

    AgentSpawner._render_mailbox_section(spawner, tasks)

    chain = AuditChainStore(workdir / ".sdd" / "audit")
    events = chain.query(event_type="task.mailbox_consumed")
    assert len(events) == 1
    assert events[0].details["seq"] == 0
    assert events[0].details["entry_hash"] == "hmac-sha256:dummy"


def test_missing_journal_produces_a_visible_record_not_silent_empty_string(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    spawner = DummySpawner(tmp_path)
    tasks = [_create_task()]

    with caplog.at_level("INFO"):
        result = AgentSpawner._render_mailbox_section(spawner, tasks)

    assert result == ""
    assert any("Mailbox journal missing" in rec.message for rec in caplog.records), (
        "Expected INFO log for missing journal"
    )


def test_an_exception_during_render_is_visible_at_default_log_level(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Create the journal file so the code tries to instantiate TaskMailbox
    journal = tmp_path / ".sdd" / "runtime" / "mailbox.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.touch()

    spawner = DummySpawner(tmp_path)
    tasks = [_create_task()]

    # Mock TaskMailbox to raise an exception to test the except block
    with patch("bernstein.core.communication.task_mailbox.TaskMailbox", side_effect=ValueError("Test exception")):
        with caplog.at_level("DEBUG"):
            result = AgentSpawner._render_mailbox_section(spawner, tasks)

    assert result == ""
    assert any("Mailbox section rendering skipped" in rec.message and rec.levelno >= 30 for rec in caplog.records), (
        "Expected WARNING log for render exception"
    )


def test_a_consumed_message_is_not_rerendered_on_a_later_resume(tmp_path: Path) -> None:
    workdir = tmp_path
    journal = workdir / ".sdd" / "runtime" / "mailbox.jsonl"
    _write_message(journal, task_id="T-1", seq=0)

    spawner = DummySpawner(workdir)
    tasks = [_create_task(task_id="T-1")]

    # First spawn: renders and records consumption
    result1 = AgentSpawner._render_mailbox_section(spawner, tasks)
    assert "[seq 0]" in result1

    # Resume: should not re-render the consumed message
    result2 = AgentSpawner._render_mailbox_section(spawner, tasks)
    assert result2 == ""


def test_a_message_posted_after_the_cursor_is_still_rendered(tmp_path: Path) -> None:
    workdir = tmp_path
    journal = workdir / ".sdd" / "runtime" / "mailbox.jsonl"
    _write_message(journal, task_id="T-1", seq=0)

    spawner = DummySpawner(workdir)
    tasks = [_create_task(task_id="T-1")]

    # First spawn: consumes message 0
    AgentSpawner._render_mailbox_section(spawner, tasks)

    # Append a new message (seq=1)
    _write_message(journal, task_id="T-1", seq=1)

    # Second spawn: should render message 1 but NOT message 0
    result = AgentSpawner._render_mailbox_section(spawner, tasks)
    assert "[seq 0]" not in result
    assert "[seq 1]" in result


def test_cursor_is_derived_from_the_chain_not_local_state(tmp_path: Path) -> None:
    workdir = tmp_path
    journal = workdir / ".sdd" / "runtime" / "mailbox.jsonl"
    _write_message(journal, task_id="T-1", seq=0)

    # Two independent spawner instances pointing at the same workdir
    spawner1 = DummySpawner(workdir)
    spawner2 = DummySpawner(workdir)
    tasks = [_create_task(task_id="T-1")]

    # First projection records consumption
    AgentSpawner._render_mailbox_section(spawner1, tasks)

    # Second projection should derive the same cursor from the chain and not re-render
    result2 = AgentSpawner._render_mailbox_section(spawner2, tasks)
    assert result2 == ""
