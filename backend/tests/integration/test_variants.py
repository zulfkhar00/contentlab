"""
Sprint 5 integration tests: variant execution lifecycle.
Uses uuid-derived video IDs to avoid cross-test collisions.
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


def _token(uid: str) -> str:
    return jwt.encode(
        {"sub": uid, "iss": "supabase-demo", "role": "authenticated",
         "exp": int(time.time()) + 3600, "iat": int(time.time())},
        _SECRET, algorithm="HS256",
    )


def _unique_tiktok_url(handle: str) -> str:
    """Generate a unique TikTok URL for each test invocation."""
    vid_id = str(abs(hash(str(uuid.uuid4()))))[:12]
    return f"https://www.tiktok.com/@{handle}/video/{vid_id}"


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def variant_a(client):
    uid = str(uuid.uuid4())
    async with _db() as db:
        await db.execute(
            text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
            {"id": uid, "email": f"s5-{uid[:8]}@e.com"},
        )
        await db.commit()
    token = _token(uid)
    r = await client.post(
        "/api/projects",
        json={"product_name": "Sprint5", "product_url": "https://s5.co",
              "target_audience": "Devs", "primary_cta": "Try it",
              "tiktok_handle": "s5_handle",
              "account_public": True, "manual_publish": True},
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
    exp = r3.json()
    va = next(v for v in exp["variants"] if v["position"] == "A")
    yield uid, exp, va["id"], token

    async with _db() as db:
        await db.execute(text("SET session_replication_role = replica"))
        await db.execute(text("DELETE FROM projects WHERE user_id = :uid"), {"uid": uid})
        await db.execute(text("DELETE FROM auth.users WHERE id = :uid"), {"uid": uid})
        await db.execute(text("SET session_replication_role = DEFAULT"))
        await db.commit()


async def test_get_variant(client, variant_a):
    _, _, va_id, token = variant_a
    r = await client.get(f"/api/variants/{va_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["position"] == "A"
    assert r.json()["status"] == "ready_to_review"


async def test_approve_for_recording(client, variant_a):
    _, _, va_id, token = variant_a
    r = await client.post(f"/api/variants/{va_id}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved_for_recording"
    assert r.json()["approved_for_recording_at"] is not None


async def test_approve_wrong_status(client, variant_a):
    _, exp, _, token = variant_a
    vb = next(v for v in exp["variants"] if v["position"] == "B")
    r = await client.post(f"/api/variants/{vb['id']}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 409


async def test_confirm_recorded(client, variant_a):
    _, _, va_id, token = variant_a
    await client.post(f"/api/variants/{va_id}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    r = await client.post(f"/api/variants/{va_id}/confirm-recorded", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["status"] == "recorded"


async def test_update_brief(client, variant_a):
    _, _, va_id, token = variant_a
    r = await client.patch(
        f"/api/variants/{va_id}/brief",
        json={"hook": "Updated hook text."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["hook"] == "Updated hook text."


async def test_revise_brief(client, variant_a):
    _, _, va_id, token = variant_a
    r = await client.post(
        f"/api/variants/{va_id}/revise-brief",
        json={"instruction": "make it punchier"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "proposed_revision" in r.json()
    assert "hook" in r.json()["proposed_revision"]


async def test_create_video(client, variant_a):
    _, _, va_id, token = variant_a
    await client.post(f"/api/variants/{va_id}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/variants/{va_id}/confirm-recorded", headers={"Authorization": f"Bearer {token}"})
    r = await client.post(f"/api/variants/{va_id}/videos", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert r.json()["status"] == "needs_url"
    assert r.json()["attempt_number"] == 1


async def test_submit_url_valid(client, variant_a):
    _, _, va_id, token = variant_a
    await client.post(f"/api/variants/{va_id}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/variants/{va_id}/confirm-recorded", headers={"Authorization": f"Bearer {token}"})
    r_vid = await client.post(f"/api/variants/{va_id}/videos", headers={"Authorization": f"Bearer {token}"})
    vid_id = r_vid.json()["id"]
    url = _unique_tiktok_url("s5_handle")
    r = await client.post(
        f"/api/videos/{vid_id}/submit-url",
        json={"url": url, "video_live": True, "variable_delivered": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "tracking"
    assert data["tracking_started_at"] is not None
    assert data["tracking_window_ends_at"] is not None


async def test_submit_url_invalid(client, variant_a):
    _, _, va_id, token = variant_a
    await client.post(f"/api/variants/{va_id}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/variants/{va_id}/confirm-recorded", headers={"Authorization": f"Bearer {token}"})
    r_vid = await client.post(f"/api/variants/{va_id}/videos", headers={"Authorization": f"Bearer {token}"})
    vid_id = r_vid.json()["id"]
    r = await client.post(
        f"/api/videos/{vid_id}/submit-url",
        json={"url": "https://youtube.com/watch?v=abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


async def test_execution_observation(client, variant_a):
    _, _, va_id, token = variant_a
    await client.post(f"/api/variants/{va_id}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/variants/{va_id}/confirm-recorded", headers={"Authorization": f"Bearer {token}"})
    r_vid = await client.post(f"/api/variants/{va_id}/videos", headers={"Authorization": f"Bearer {token}"})
    vid_id = r_vid.json()["id"]
    url = _unique_tiktok_url("s5_handle")
    await client.post(
        f"/api/videos/{vid_id}/submit-url",
        json={"url": url, "video_live": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await client.put(
        f"/api/videos/{vid_id}/execution-observation",
        json={"delivered_variable": True, "notes": "Hook landed well.", "reason": "Delivered as written."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["delivered_variable"] is True
    r2 = await client.get(f"/api/videos/{vid_id}/execution-observation", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["delivered_variable"] is True


async def test_dev_complete_window_unlocks_b(client, variant_a):
    _, exp, va_id, token = variant_a
    await client.post(f"/api/variants/{va_id}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/variants/{va_id}/confirm-recorded", headers={"Authorization": f"Bearer {token}"})
    r_vid = await client.post(f"/api/variants/{va_id}/videos", headers={"Authorization": f"Bearer {token}"})
    vid_id = r_vid.json()["id"]
    url = _unique_tiktok_url("s5_handle")
    await client.post(
        f"/api/videos/{vid_id}/submit-url",
        json={"url": url},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await client.post(
        f"/api/dev/videos/{vid_id}/complete-window",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    vb = next(v for v in exp["variants"] if v["position"] == "B")
    r_vb = await client.get(f"/api/variants/{vb['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r_vb.json()["status"] == "ready_to_review"
    r_exp = await client.get(f"/api/experiments/{exp['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r_exp.json()["status"] == "in_progress"
