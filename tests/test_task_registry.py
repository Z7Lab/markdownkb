"""Tests for the background task registry."""

import threading
import time

from app.services.task_registry import TaskRegistry, run_tracked


def test_create_and_list_newest_first():
    reg = TaskRegistry()
    a = reg.create(kind="foo", label="first")
    b = reg.create(kind="bar", label="second")

    items = reg.list()
    assert [r.id for r in items] == [b.id, a.id]


def test_kind_filter():
    reg = TaskRegistry()
    reg.create(kind="foo")
    b = reg.create(kind="bar")
    reg.create(kind="foo")

    bars = reg.list(kind="bar")
    assert len(bars) == 1
    assert bars[0].id == b.id


def test_capacity_bound():
    reg = TaskRegistry(capacity=3)
    ids = [reg.create(kind="x").id for _ in range(5)]
    records = reg.list(limit=100)
    # The two oldest were evicted.
    kept_ids = {r.id for r in records}
    assert kept_ids == set(ids[-3:])


def test_mark_succeeded_and_failed():
    reg = TaskRegistry()
    t1 = reg.create(kind="ok")
    reg.mark_running(t1.id)
    reg.mark_succeeded(t1.id)
    assert reg.get(t1.id).status == "succeeded"
    assert reg.get(t1.id).started_at is not None
    assert reg.get(t1.id).finished_at is not None

    t2 = reg.create(kind="boom")
    reg.mark_failed(t2.id, "kaboom")
    assert reg.get(t2.id).status == "failed"
    assert reg.get(t2.id).error == "kaboom"


def test_run_tracked_success():
    reg = TaskRegistry()
    done = threading.Event()

    def job():
        done.set()

    record = run_tracked(kind="unit", target=job, registry=reg, label="t")
    done.wait(timeout=2)
    # Give the wrapper a beat to call mark_succeeded.
    for _ in range(20):
        if reg.get(record.id).status == "succeeded":
            break
        time.sleep(0.05)
    assert reg.get(record.id).status == "succeeded"


def test_run_tracked_failure_captured():
    reg = TaskRegistry()

    def job():
        raise RuntimeError("boom")

    record = run_tracked(kind="unit", target=job, registry=reg)
    for _ in range(40):
        if reg.get(record.id).status == "failed":
            break
        time.sleep(0.05)
    assert reg.get(record.id).status == "failed"
    assert "boom" in (reg.get(record.id).error or "")
