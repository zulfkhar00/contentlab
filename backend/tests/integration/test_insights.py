"""
Sprint 4 integration tests: analyze → insight → candidates → acceptance.
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
async def experiment_ready(client):
    """Create user + project + hypotheses + approved experiment; yield (user_id, exp_id, token)."""
    user_id = str(uuid.uuid4())
    async with _db() as db:
        await db.execute(
            text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
            {"id": user_id, "email": f"t4-{user_id[:8]}@e.com"},
        )
        await db.commit()

    token = _token(user_id)
    r = await client.post(
        "/api/projects",
        json={"product_name": "Sprint4 Co", "product_url": "https://s4.co",
              "target_audience": "Devs", "primary_cta": "Try it", "account_public": True, "manual_publish": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    r2 = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 201
    hid = r2.json()[0]["id"]
    r3 = await client.post(
        f"/api/hypotheses/{hid}/approve-and-generate-experiment",
        json={}, headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 201
    exp_id = r3.json()["id"]

    yield user_id, exp_id, token

    async with _db() as db:
        await db.execute(text("SET session_replication_role = replica"))
        await db.execute(text("DELETE FROM projects WHERE user_id = :uid"), {"uid": user_id})
        await db.execute(text("DELETE FROM auth.users WHERE id = :uid"), {"uid": user_id})
        await db.execute(text("SET session_replication_role = DEFAULT"))
        await db.commit()


async def test_seed_evidence(client, experiment_ready):
    _, exp_id, token = experiment_ready
    r = await client.post(
        f"/api/dev/experiments/{exp_id}/seed-evidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert "snapshot_id" in data
    assert data["experiment_id"] == exp_id


async def test_seed_evidence_idempotent(client, experiment_ready):
    _, exp_id, token = experiment_ready
    r1 = await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 201
    r2 = await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 409


async def test_analyze_experiment(client, experiment_ready):
    _, exp_id, token = experiment_ready
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    r = await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    insight = r.json()
    assert insight["outcome_type"] == "directional_difference"
    assert len(insight["candidates"]) == 3
    slots = {c["slot"] for c in insight["candidates"]}
    assert slots == {"safest_next_step", "highest_learning", "highest_upside"}
    recommended = [c for c in insight["candidates"] if c["recommended"]]
    assert len(recommended) == 1
    assert recommended[0]["slot"] == "highest_learning"
    assert len(insight["evidence_items"]) == 3


async def test_analyze_wrong_status(client, experiment_ready):
    _, exp_id, token = experiment_ready
    r = await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 409


async def test_list_insights(client, experiment_ready):
    _, exp_id, token = experiment_ready
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    r = await client.get("/api/insights", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["outcome_type"] == "directional_difference"


async def test_get_insight(client, experiment_ready):
    _, exp_id, token = experiment_ready
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    r_analyze = await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    iid = r_analyze.json()["id"]
    r = await client.get(f"/api/insights/{iid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == iid
    assert len(data["candidates"]) == 3
    assert len(data["evidence_items"]) == 3
    assert data["evidence_basis"]["schemaVersion"] == 1


async def test_accept_candidate_creates_hypothesis(client, experiment_ready):
    _, exp_id, token = experiment_ready
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    r_analyze = await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    candidates = r_analyze.json()["candidates"]
    recommended = next(c for c in candidates if c["recommended"])

    r = await client.post(
        f"/api/follow-up-candidates/{recommended['id']}/accept",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    h = r.json()
    assert h["status"] == "generated"
    assert h["source_candidate_id"] == recommended["id"]
    assert h["relationship_type"] == "mechanism_isolation"
    assert h["parent_hypothesis_id"] is not None
    assert h["previous_learning"]
    assert h["remaining_unknown"]
    assert h["recommendation_reason"]


async def test_accept_already_accepted(client, experiment_ready):
    _, exp_id, token = experiment_ready
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    r_analyze = await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    cid = r_analyze.json()["candidates"][0]["id"]
    r1 = await client.post(f"/api/follow-up-candidates/{cid}/accept", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 201
    r2 = await client.post(f"/api/follow-up-candidates/{cid}/accept", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 409


async def test_dismiss_candidate(client, experiment_ready):
    _, exp_id, token = experiment_ready
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    r_analyze = await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    cid = r_analyze.json()["candidates"][0]["id"]
    r = await client.post(
        f"/api/follow-up-candidates/{cid}/dismiss",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"


async def test_experiment_completed_after_analyze(client, experiment_ready):
    _, exp_id, token = experiment_ready
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    r = await client.get(f"/api/experiments/{exp_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["status"] == "completed"


async def test_ai_runs_for_analyze(client, experiment_ready):
    _, exp_id, token = experiment_ready
    project_id = (await client.get("/api/projects/current", headers={"Authorization": f"Bearer {token}"})).json()["id"]
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/experiments/{exp_id}/analyze", headers={"Authorization": f"Bearer {token}"})
    async with _db() as db:
        r = await db.execute(
            text("SELECT operation FROM ai_runs WHERE project_id = :pid AND operation IN ('analyzeExperiment','generateCandidates')"),
            {"pid": project_id}
        )
        ops = {row[0] for row in r}
    assert ops == {"analyzeExperiment", "generateCandidates"}
