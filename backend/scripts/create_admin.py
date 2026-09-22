"""Create (or report) a user directly in the DB, bypassing the admin key.

Usage:
    python scripts/create_admin.py --email a@b.c --username admin --password secret
Idempotent: re-running with an existing email or username is a no-op.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make `app` importable

from sqlalchemy import select  # noqa: E402

import app.domains.jobs.models  # noqa: E402, F401  (User.jobs relationship target)
from app.auth.jwt import get_password_hash  # noqa: E402
from app.auth.models import User  # noqa: E402
from app.core.db import AsyncSessionLocal, init_db  # noqa: E402


async def _run(email: str, username: str, password: str, superuser: bool) -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(User).where((User.email == email) | (User.username == username))
        )
        if existing:
            print(f"user {existing.username} <{existing.email}> already exists - nothing to do")
            return
        user = User(
            email=email,
            username=username,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=superuser,
        )
        session.add(user)
        await session.commit()
        print(f"created user {username} <{email}>")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--superuser", action="store_true")
    args = p.parse_args()
    asyncio.run(_run(args.email, args.username, args.password, args.superuser))


if __name__ == "__main__":
    main()
