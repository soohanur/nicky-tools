from __future__ import annotations

from httpx import AsyncClient

JOBS = "/api/v1/jobs"


async def _create(client: AsyncClient, headers: dict, name: str = "Scraply - test.csv") -> dict:
    resp = await client.post(
        JOBS,
        headers=headers,
        json={"tool_type": "scraply", "name": name, "priority": "normal", "config": {}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_and_list(client: AsyncClient, auth_headers: dict) -> None:
    job = await _create(client, auth_headers)
    assert job["status"] == "pending"
    assert job["tool_type"] == "scraply"

    resp = await client.get(JOBS, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["jobs"][0]["job_uuid"] == job["job_uuid"]

    resp = await client.get(JOBS, headers=auth_headers, params={"status_filter": "completed"})
    assert resp.json()["total"] == 0


async def test_update_config(client: AsyncClient, auth_headers: dict) -> None:
    job = await _create(client, auth_headers)
    mapping = {
        "col_company": "Bedrijfsnaam",
        "col_street": "Straat",
        "col_house_number": "Huisnr",
        "col_city": "Plaats",
    }
    resp = await client.patch(
        f"{JOBS}/{job['job_uuid']}", headers=auth_headers, json={"config": mapping}
    )
    assert resp.status_code == 200
    resp = await client.get(f"{JOBS}/{job['job_uuid']}", headers=auth_headers)
    assert resp.status_code == 200


async def test_start_without_file_rejected(client: AsyncClient, auth_headers: dict) -> None:
    job = await _create(client, auth_headers)
    resp = await client.post(f"{JOBS}/{job['job_uuid']}/start", headers=auth_headers)
    assert resp.status_code == 400
    assert "No input file" in resp.json()["detail"]


async def test_cancel_pending_rejected(client: AsyncClient, auth_headers: dict) -> None:
    job = await _create(client, auth_headers)
    resp = await client.post(f"{JOBS}/{job['job_uuid']}/cancel", headers=auth_headers)
    assert resp.status_code == 400


async def test_delete(client: AsyncClient, auth_headers: dict) -> None:
    job = await _create(client, auth_headers)
    resp = await client.delete(f"{JOBS}/{job['job_uuid']}", headers=auth_headers)
    assert resp.status_code == 204
    resp = await client.get(f"{JOBS}/{job['job_uuid']}", headers=auth_headers)
    assert resp.status_code == 404


async def test_jobs_require_auth(client: AsyncClient) -> None:
    resp = await client.get(JOBS)
    assert resp.status_code in (401, 403)
