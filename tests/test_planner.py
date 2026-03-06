"""Tests for planner endpoints."""

from unittest.mock import patch

import pytest


MOCK_PLAN_RESULT = {
    "plan": "Step 1: do thing\nStep 2: do other thing",
    "tree": {"content": "root", "type": "root", "score": 0, "visits": 0, "sources": [], "children": []},
    "sources": ["/tmp/test-source/doc.md"],
    "exploration_log": [],
    "user_patterns": [],
    "iterations": 3,
}


@pytest.mark.asyncio
async def test_plan_returns_result(client):
    with patch("app.plugins.planner.router.run_planner", return_value=MOCK_PLAN_RESULT):
        resp = await client.post("/api/planner/plan", json={"request": "Build a login page"})
    assert resp.status_code == 200
    data = resp.json()
    assert "plan" in data
    assert "tree" in data
    assert "sources" in data


@pytest.mark.asyncio
async def test_plan_empty_request_rejected(client):
    resp = await client.post("/api/planner/plan", json={"request": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_plan_llm_failure_returns_502(client):
    with patch("app.plugins.planner.router.run_planner", side_effect=RuntimeError("LLM offline")):
        resp = await client.post("/api/planner/plan", json={"request": "test"})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_plan_stream_returns_sse(client):
    def fake_stream(*args, **kwargs):
        yield 'event: status\ndata: {"phase": "research", "message": "Searching..."}\n\n'
        yield 'event: plan\ndata: {"plan": "the plan"}\n\n'
        yield 'event: done\ndata: {}\n\n'

    with patch("app.plugins.planner.router.stream_planner", side_effect=fake_stream):
        resp = await client.post("/api/planner/plan/stream", json={"request": "test"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "event: status" in body
    assert "event: plan" in body
    assert "event: done" in body


@pytest.mark.asyncio
async def test_list_skills(client):
    mock_skills = [
        {"name": "security-auditor", "description": "Reviews for vulnerabilities", "source": "builtin"},
    ]
    with patch("app.plugins.planner.router.list_skills", return_value=mock_skills):
        resp = await client.get("/api/planner/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert "skills" in data
    assert len(data["skills"]) == 1
    assert data["skills"][0]["name"] == "security-auditor"


@pytest.mark.asyncio
async def test_plan_with_skills(client):
    result_with_reviews = {
        **MOCK_PLAN_RESULT,
        "reviews": [
            {"skill_name": "security-auditor", "review": "Looks good", "issues": [], "approvals": ["LGTM"]},
        ],
        "refined_plan": "Refined step 1\nRefined step 2",
    }
    with patch("app.plugins.planner.router.run_planner", return_value=result_with_reviews):
        resp = await client.post(
            "/api/planner/plan",
            json={"request": "Build a login page", "skill_names": ["security-auditor"]},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "reviews" in data
    assert "refined_plan" in data
    assert data["reviews"][0]["skill_name"] == "security-auditor"
