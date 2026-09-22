from __future__ import annotations

from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


async def test_register_requires_admin_key(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER,
        json={"email": "x@y.z", "username": "xyz", "password": "password123", "admin_key": "wrong"},
    )
    assert resp.status_code == 403


async def test_register_login_me(client: AsyncClient) -> None:
    resp = await client.post(
        REGISTER,
        json={
            "email": "nicky@example.com",
            "username": "nicky",
            "password": "password123",
            "admin_key": "test-admin-key",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["username"] == "nicky"

    # login by username and by email
    for identity in ("nicky", "nicky@example.com"):
        resp = await client.post(LOGIN, data={"username": identity, "password": "password123"})
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]

    resp = await client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "nicky@example.com"


async def test_duplicate_username_rejected(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        REGISTER,
        json={
            "email": "other@example.com",
            "username": "tester",
            "password": "password123",
            "admin_key": "test-admin-key",
        },
    )
    assert resp.status_code == 400
    assert "Username" in resp.json()["detail"]


async def test_bad_password(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(LOGIN, data={"username": "tester", "password": "nope"})
    assert resp.status_code == 401


async def test_me_without_token(client: AsyncClient) -> None:
    resp = await client.get(ME)
    assert resp.status_code in (401, 403)
