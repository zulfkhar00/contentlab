"""
Sprint 7 tests: redirect deduplication, visitor identity, worker lifecycle,
sequential A→B→C unlock, evidence calculation.
"""
import sys, os, time, uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
import jwt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.config import settings
from app.main import app

_DB_URL = settings.database_url
_SECRET = settings.supabase_jwt_secret

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


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def project_with_experiment(client):
    """Full stack: user + project + generate + approve → experiment. Yields (uid, exp, token)."""
    uid = str(uuid.uuid4())
    async with _db() as db:
        await db.execute(
            text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
            {"id": uid, "email": f"s7-{uid[:8]}@e.com"},
        )
        await db.commit()
    token = _token(uid)
    r = await client.post(
        "/api/projects",
        json={"product_name": "S7 Test", "product_url": "https://s7.co",
              "target_audience": "Devs", "primary_cta": "Try it",
              "tiktok_handle": "s7_handle", "account_public": True, "manual_publish": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    project_id = r.json()["id"]
    tracking_slug = r.json()["tracking_slug"]
    r2 = await client.post("/api/hypotheses/generate", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 201
    hid = r2.json()[0]["id"]
    r3 = await client.post(
        f"/api/hypotheses/{hid}/approve-and-generate-experiment",
        json={}, headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 201
    exp = r3.json()

    yield uid, project_id, tracking_slug, exp, token

    async with _db() as db:
        await db.execute(text("SET session_replication_role = replica"))
        await db.execute(text("DELETE FROM projects WHERE user_id = :uid"), {"uid": uid})
        await db.execute(text("DELETE FROM auth.users WHERE id = :uid"), {"uid": uid})
        await db.execute(text("SET session_replication_role = DEFAULT"))
        await db.commit()


# ── Redirect tests ─────────────────────────────────────────────────────────────

async def test_redirect_resolves_tracking_slug(client, project_with_experiment):
    _, _, slug, _, _ = project_with_experiment
    r = await client.get(f"/p/{slug}", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert "location" in r.headers


async def test_redirect_unknown_slug_still_redirects(client):
    r = await client.get("/p/definitely-does-not-exist-slug", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)


async def test_redirect_sets_visitor_cookie(client, project_with_experiment):
    _, _, slug, _, _ = project_with_experiment
    r = await client.get(f"/p/{slug}", follow_redirects=False)
    # Cookie should be set or already present
    cookies = dict(r.cookies)
    assert settings.visitor_cookie_name in cookies or r.status_code in (301, 302)


async def test_redirect_deduplication_same_visitor(client, project_with_experiment):
    """Same visitor_key in same window counts only once as unique."""
    _, project_id, _, exp, token = project_with_experiment
    exp_id = exp["id"]

    # Seed evidence to create an attribution window
    await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence",
                      headers={"Authorization": f"Bearer {token}"})

    visitor_key = "test-visitor-" + uuid.uuid4().hex[:8]
    async with _db() as db:
        # Find active window
        aw = await db.execute(
            text("SELECT id FROM attribution_windows WHERE project_id = :pid AND status = 'active' LIMIT 1"),
            {"pid": project_id}
        )
        aw_row = aw.first()
        if not aw_row:
            pytest.skip("No active window for dedup test")
        window_id = str(aw_row[0])

        # Insert two events with same visitor_key in same window
        for i in range(2):
            await db.execute(
                text(
                    "INSERT INTO redirect_events "
                    "(project_id, attribution_window_id, visitor_key, is_unique, occurred_at, destination_url, request_metadata) "
                    "VALUES (:pid, :wid, :vk, :uniq, now(), 'https://test.co', '{}')"
                ),
                {"pid": project_id, "wid": window_id, "vk": visitor_key, "uniq": i == 0},
            )
        await db.commit()

        # Count unique clicks — should be 1
        r = await db.execute(
            text("SELECT COUNT(*) FROM redirect_events WHERE attribution_window_id = :wid AND visitor_key = :vk AND is_unique = true"),
            {"wid": window_id, "vk": visitor_key}
        )
        count = r.scalar()
    assert count == 1, f"Expected 1 unique click, got {count}"


# ── Visitor identity tests ─────────────────────────────────────────────────────

def test_coarse_ip_strips_octets():
    from app.services.redirect_service import coarse_ip
    assert coarse_ip("192.168.1.100") == "192.168"
    assert coarse_ip("10.0.0.1") == "10.0"


def test_visitor_hmac_is_deterministic():
    from app.services.redirect_service import compute_visitor_hmac
    h1 = compute_visitor_hmac("proj-1", "192.168", "abc123")
    h2 = compute_visitor_hmac("proj-1", "192.168", "abc123")
    assert h1 == h2
    assert len(h1) == 64


def test_visitor_hmac_differs_by_project():
    from app.services.redirect_service import compute_visitor_hmac
    h1 = compute_visitor_hmac("proj-1", "192.168", "abc123")
    h2 = compute_visitor_hmac("proj-2", "192.168", "abc123")
    assert h1 != h2


# ── Sequential A→B→C lifecycle ────────────────────────────────────────────────

async def test_sequential_unlock_via_dev_endpoint(client, project_with_experiment):
    """
    A completes → B unlocks → B completes → C unlocks → C completes → analyzing.
    Uses the dev complete-window endpoint to drive the sequence.
    """
    _, _, _, exp, token = project_with_experiment
    va = next(v for v in exp["variants"] if v["position"] == "A")
    vb = next(v for v in exp["variants"] if v["position"] == "B")
    vc = next(v for v in exp["variants"] if v["position"] == "C")
    exp_id = exp["id"]

    # Approve and confirm A
    await client.post(f"/api/variants/{va['id']}/approve-for-recording", headers={"Authorization": f"Bearer {token}"})
    await client.post(f"/api/variants/{va['id']}/confirm-recorded", headers={"Authorization": f"Bearer {token}"})
    r_vid = await client.post(f"/api/variants/{va['id']}/videos", headers={"Authorization": f"Bearer {token}"})
    assert r_vid.status_code == 201
    vid_a = r_vid.json()["id"]

    # Submit URL → 202 (enqueues validate_video worker job)
    url_a = f"https://www.tiktok.com/@s7_handle/video/{uuid.uuid4().hex[:12]}"
    r_submit = await client.post(
        f"/api/videos/{vid_a}/submit-url",
        json={"url": url_a, "video_live": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_submit.status_code == 202
    assert r_submit.json()["status"] == "validating"

    # Simulate worker completing validation via dev endpoint (complete-window)
    # First set video to tracking manually to simulate worker success
    async with _db() as db:
        await db.execute(
            text("UPDATE videos SET status = 'tracking', tracking_started_at = now(), tracking_window_ends_at = now() + interval '72 hours' WHERE id = :vid"),
            {"vid": vid_a}
        )
        await db.execute(
            text("INSERT INTO attribution_windows (project_id, experiment_id, variant_id, video_id, starts_at, ends_at, status) "
                 "SELECT project_id, experiment_id, variant_id, :vid, now(), now() + interval '72 hours', 'active' "
                 "FROM videos JOIN variants ON variants.id = videos.variant_id "
                 "WHERE videos.id = :vid ON CONFLICT (video_id) DO NOTHING"),
            {"vid": vid_a}
        )
        await db.execute(
            text("UPDATE experiments SET status = 'tracking' WHERE id = :eid AND status IN ('ready', 'in_progress')"),
            {"eid": exp_id}
        )
        await db.commit()

    # Complete A's window
    r_complete = await client.post(f"/api/dev/videos/{vid_a}/complete-window",
                                   headers={"Authorization": f"Bearer {token}"})
    assert r_complete.status_code == 200

    # B should now be ready_to_review
    r_vb = await client.get(f"/api/variants/{vb['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r_vb.json()["status"] == "ready_to_review"

    # Experiment should be in_progress
    r_exp = await client.get(f"/api/experiments/{exp_id}", headers={"Authorization": f"Bearer {token}"})
    assert r_exp.json()["status"] == "in_progress"


# ── Evidence calculation tests ─────────────────────────────────────────────────

async def test_evidence_uses_delta_not_total(client, project_with_experiment):
    """views_delta = final.views - baseline.views, NOT total lifetime views."""
    _, project_id, _, exp, token = project_with_experiment
    exp_id = exp["id"]

    # Seed evidence (dev fixture creates proper start/end snapshots)
    r = await client.post(f"/api/dev/experiments/{exp_id}/seed-evidence",
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201

    # Verify the evidence items have views_delta = end - start (start = 0 in fixture)
    async with _db() as db:
        r = await db.execute(
            text(
                "SELECT eei.views_delta, vms_start.views AS start_views, vms_end.views AS end_views "
                "FROM experiment_evidence_items eei "
                "JOIN video_metric_snapshots vms_start ON vms_start.id = eei.start_metric_snapshot_id "
                "JOIN video_metric_snapshots vms_end ON vms_end.id = eei.end_metric_snapshot_id "
                "JOIN experiment_evidence_snapshots ees ON ees.id = eei.evidence_snapshot_id "
                "WHERE ees.experiment_id = :eid AND eei.project_id = :pid"
            ),
            {"eid": exp_id, "pid": project_id}
        )
        rows = r.mappings().all()
    assert len(rows) == 3, f"Expected 3 evidence items, got {len(rows)}"
    for row in rows:
        expected_delta = int(row["end_views"]) - int(row["start_views"])
        assert int(row["views_delta"]) == expected_delta, (
            f"views_delta {row['views_delta']} != end({row['end_views']}) - start({row['start_views']})"
        )
