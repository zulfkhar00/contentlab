"""
Integration tests for POST/GET/PATCH /api/projects.
Runs against the live local Supabase database.
Each test creates real rows and cleans them up on teardown.
"""
import time
import uuid
from contextlib import asynccontextmanager

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.config import settings
from app.main import app

_SECRET = settings.supabase_jwt_secret
_DB_URL = settings.database_url

# Separate engine for test setup/teardown (bypasses RLS as postgres superuser)
_engine = create_async_engine(_DB_URL, echo=False, poolclass=NullPool)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
async def _db_conn():
    """Fresh session per operation — avoids concurrent-operation conflicts."""
    async with _Session() as session:
        yield session


def _token(user_id: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "iss": "supabase-demo",
            "role": "authenticated",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        },
        _SECRET,
        algorithm="HS256",
    )


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_user():
    """Insert a real auth.users row; delete the user and their project on teardown."""
    user_id = str(uuid.uuid4())
    async with _db_conn() as db:
        await db.execute(
            text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
            {"id": user_id, "email": f"test-{user_id[:8]}@example.com"},
        )
        await db.commit()

    yield user_id

    async with _db_conn() as db:
        await db.execute(text("SET session_replication_role = replica"))
        await db.execute(
            text("DELETE FROM projects WHERE user_id = :uid"), {"uid": user_id}
        )
        await db.execute(
            text("DELETE FROM auth.users WHERE id = :uid"), {"uid": user_id}
        )
        await db.execute(text("SET session_replication_role = DEFAULT"))
        await db.commit()


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_create_project(client, auth_user):
    token = _token(auth_user)
    body = {
        "product_name": "Test Product",
        "product_type": "SaaS",
        "product_description": "A test product.",
        "product_url": "https://example.com",
        "target_audience": "Developers",
        "problem_solved": "Testing",
        "why_it_matters": "For CI",
        "current_alternatives": "None",
        "desired_action": "Sign up",
        "primary_cta": "Try free",
        "tiktok_handle": "@test_handle",
        "account_public": True,
        "manual_publish": True,
        "onboarded": True,
    }
    r = await client.post("/api/projects", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["product_name"] == "Test Product"
    assert data["tracking_slug"].startswith("test-product")
    assert data["tiktok_handle"] == "test_handle"  # @ stripped
    assert data["tracking_url"].startswith("https://contentlab.app/p/")
    assert data["onboarded_at"] is not None
    assert "context_version" in data


async def test_create_project_duplicate(client, auth_user):
    token = _token(auth_user)
    body = {"product_name": "Dup", "product_url": "https://dup.com", "account_public": True, "manual_publish": True}
    r1 = await client.post("/api/projects", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 201
    r2 = await client.post("/api/projects", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 409


async def test_get_current_project_no_project(client, auth_user):
    token = _token(auth_user)
    r = await client.get("/api/projects/current", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


async def test_get_current_project_after_create(client, auth_user):
    token = _token(auth_user)
    await client.post(
        "/api/projects",
        json={"product_name": "My App", "product_url": "https://myapp.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    r = await client.get("/api/projects/current", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["product_name"] == "My App"


async def test_update_project(client, auth_user):
    token = _token(auth_user)
    r_create = await client.post(
        "/api/projects",
        json={"product_name": "Before", "product_url": "https://before.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_create.status_code == 201
    project_id = r_create.json()["id"]
    old_slug = r_create.json()["tracking_slug"]

    r_update = await client.patch(
        f"/api/projects/{project_id}",
        json={"product_name": "After", "tiktok_handle": "@new_handle"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_update.status_code == 200, r_update.text
    data = r_update.json()
    assert data["product_name"] == "After"
    assert data["tiktok_handle"] == "new_handle"
    # tracking_slug must not change
    assert data["tracking_slug"] == old_slug


async def test_update_ignores_context_version(client, auth_user):
    token = _token(auth_user)
    r = await client.post(
        "/api/projects",
        json={"product_name": "CV Test", "product_url": "https://cv.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    project_id = r.json()["id"]
    original_cv = r.json()["context_version"]

    # context_version: 999 in body must be silently ignored
    r2 = await client.patch(
        f"/api/projects/{project_id}",
        json={"context_version": 999, "product_name": "CV Test Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    new_cv = r2.json()["context_version"]
    assert new_cv == original_cv + 1  # DB trigger fires for product_name change
    assert new_cv != 999


async def test_no_auth_returns_401(client):
    r = await client.get("/api/projects/current")
    assert r.status_code == 401


async def test_wrong_project_id_returns_403(client, auth_user):
    token = _token(auth_user)
    await client.post(
        "/api/projects",
        json={"product_name": "Auth Test", "product_url": "https://auth.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    wrong_id = str(uuid.uuid4())
    r = await client.patch(
        f"/api/projects/{wrong_id}",
        json={"product_name": "Hacked"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


async def test_invalid_product_type_rejected(client, auth_user):
    token = _token(auth_user)
    r = await client.post(
        "/api/projects",
        json={"product_name": "X", "product_type": "Blockchain"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
