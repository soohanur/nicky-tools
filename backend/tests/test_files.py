from __future__ import annotations

from types import SimpleNamespace

from httpx import AsyncClient

from app.domains.files.services import next_display_name, split_name

JOBS = "/api/v1/jobs"
FILES = "/api/v1/files"


def _job(name: str) -> SimpleNamespace:
    return SimpleNamespace(display_filename=name)


def test_split_name() -> None:
    assert split_name("report.xlsx") == ("report", "xlsx")
    assert split_name("report") == ("report", "")


def test_next_display_name_dedupes() -> None:
    assert next_display_name("a.csv", []) == "a.csv"
    assert next_display_name("a.csv", [_job("a.csv")]) == "a (2).csv"
    assert next_display_name("a.csv", [_job("a.csv"), _job("a (2).csv")]) == "a (3).csv"
    assert next_display_name("a.csv", [_job("another.csv")]) == "a.csv"


async def test_upload_csv_and_headers(client: AsyncClient, auth_headers: dict, tmp_path) -> None:
    resp = await client.post(
        JOBS,
        headers=auth_headers,
        json={"tool_type": "scraply", "name": "Scraply - leads.csv", "config": {}},
    )
    job_uuid = resp.json()["job_uuid"]

    csv_bytes = b"Bedrijfsnaam,Straat,Huisnr,Plaats\nJansen Bouw,Kalverstraat,114,Amsterdam\n"
    resp = await client.post(
        f"{FILES}/upload",
        headers=auth_headers,
        params={"job_uuid": job_uuid},
        files={"file": ("leads.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    stored = resp.json()["filename"]
    assert stored.endswith("_leads.csv")

    resp = await client.get(f"{FILES}/csv-headers/{stored}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["headers"][:4] == ["Bedrijfsnaam", "Straat", "Huisnr", "Plaats"]

    resp = await client.get(f"{FILES}/inputs", headers=auth_headers)
    assert resp.status_code == 200
    names = [f["display_name"] for f in resp.json()["files"]]
    assert "leads.csv" in names

    resp = await client.delete(
        f"{FILES}/{stored}", headers=auth_headers, params={"file_type": "input"}
    )
    assert resp.status_code == 204


async def test_upload_rejects_bad_extension(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        JOBS, headers=auth_headers, json={"tool_type": "scraply", "name": "x", "config": {}}
    )
    job_uuid = resp.json()["job_uuid"]
    resp = await client.post(
        f"{FILES}/upload",
        headers=auth_headers,
        params={"job_uuid": job_uuid},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
