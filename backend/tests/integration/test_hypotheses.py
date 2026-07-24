"""
Integration tests for hypothesis and experiment endpoints.
Each test creates its own auth.users row + project.
"""
import sys, os, time, uuid
from contextlib import asynccontextmanager

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.config import settings
from app.main import app

_SECRET = settings.supabase_jwt_secret
_DB_URL = settings.database_url

_engine = create_async_engine(_DB_URL, echo=False, poolclass=NullPool)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
async def _db():
    async with _Session() as s:
        yield s


def _token(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "iss": "supabase-demo", "role": "authenticated",
         "exp": int(time.time()) + 3600, "iat": int(time.time())},
        _SECRET, algorithm="HS256",
    )


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def user_with_project(client):
    """Create auth user + project; yield (user_id, project_id, token)."""
    user_id = str(uuid.uuid4())
    async with _db() as db:
        await db.execute(
            text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
            {"id": user_id, "email": f"t-{user_id[:8]}@e.com"},
        )
        await db.commit()

    token = _token(user_id)
    r = await client.post(
        "/api/projects",
        json={"product_name": "Test Co", "product_url": "https://test.co",
              "target_audience": "Developers", "primary_cta": "Check link in bio",
              "account_public": True, "manual_publish": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    project_id = r.json()["id"]

    yield user_id, project_id, token

    async with _db() as db:
        # Disable triggers for test teardown; ai_runs is append-only by design
        await db.execute(text("SET session_replication_role = replica"))
        await db.execute(text("DELETE FROM projects WHERE user_id = :uid"), {"uid": user_id})
        await db.execute(text("DELETE FROM auth.users WHERE id = :uid"), {"uid": user_id})
        await db.execute(text("SET session_replication_role = DEFAULT"))
        await db.commit()


async def test_generate_hypotheses(client, user_with_project):
    _, _, token = user_with_project
    r = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert len(data) == 5
    assert all(h["status"] == "generated" for h in data)
    assert all("title" in h for h in data)


async def test_generate_twice_returns_409(client, user_with_project):
    _, _, token = user_with_project
    r1 = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 201
    r2 = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 409


async def test_list_hypotheses(client, user_with_project):
    _, _, token = user_with_project
    await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    r = await client.get("/api/hypotheses", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 5


async def test_list_with_status_filter(client, user_with_project):
    _, _, token = user_with_project
    await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    r = await client.get("/api/hypotheses?status=generated", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert all(h["status"] == "generated" for h in r.json())


async def test_get_hypothesis(client, user_with_project):
    _, _, token = user_with_project
    gen = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    hid = gen.json()[0]["id"]
    r = await client.get(f"/api/hypotheses/{hid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == hid


async def test_patch_hypothesis_transitions_to_draft(client, user_with_project):
    _, _, token = user_with_project
    gen = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    hid = gen.json()[0]["id"]
    r = await client.patch(
        f"/api/hypotheses/{hid}",
        json={"title": "Updated Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Updated Title"
    assert r.json()["status"] == "draft"


async def test_reject_hypothesis(client, user_with_project):
    _, _, token = user_with_project
    gen = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    hid = gen.json()[0]["id"]
    r = await client.post(
        f"/api/hypotheses/{hid}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["rejected_at"] is not None


async def test_approve_and_generate_experiment(client, user_with_project):
    _, _, token = user_with_project
    gen = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    hid = gen.json()[0]["id"]

    r = await client.post(
        f"/api/hypotheses/{hid}/approve-and-generate-experiment",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    exp = r.json()
    assert exp["status"] == "ready"
    assert len(exp["variants"]) == 3
    positions = {v["position"] for v in exp["variants"]}
    assert positions == {"A", "B", "C"}
    statuses = {v["position"]: v["status"] for v in exp["variants"]}
    assert statuses["A"] == "ready_to_review"
    assert statuses["B"] == "queued"
    assert statuses["C"] == "queued"

    # Hypothesis is now approved
    hr = await client.get(f"/api/hypotheses/{hid}", headers={"Authorization": f"Bearer {token}"})
    assert hr.json()["status"] == "approved"
    assert hr.json()["approved_at"] is not None


async def test_approve_twice_returns_409(client, user_with_project):
    _, _, token = user_with_project
    gen = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    hid = gen.json()[0]["id"]
    r1 = await client.post(
        f"/api/hypotheses/{hid}/approve-and-generate-experiment",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/hypotheses/{hid}/approve-and-generate-experiment",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409


async def test_get_active_experiment(client, user_with_project):
    _, _, token = user_with_project
    gen = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    hid = gen.json()[0]["id"]
    await client.post(
        f"/api/hypotheses/{hid}/approve-and-generate-experiment",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await client.get("/api/experiments/active", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    exp = r.json()
    assert exp["status"] == "ready"
    assert len(exp["variants"]) == 3
    # Verify hypothesis_design_snapshot has schemaVersion
    snap = exp["hypothesis_design_snapshot"]
    assert snap["schemaVersion"] == 1
    assert "statement" in snap


async def test_no_active_experiment_returns_404(client, user_with_project):
    _, _, token = user_with_project
    r = await client.get("/api/experiments/active", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


async def test_ai_runs_recorded(client, user_with_project):
    _, project_id, token = user_with_project
    await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    async with _db() as db:
        result = await db.execute(
            text("SELECT COUNT(1) FROM ai_runs WHERE project_id = :pid AND operation = 'generateHypotheses'"),
            {"pid": project_id}
        )
        count = result.scalar()
    assert count == 1  # one per provider invocation, not per hypothesis
