"""Preflight check: verify the database is reachable and pgvector is available.

CocoIndex creates the ``doc_embeddings`` table and the ``vector`` extension on
its first run, so this script does not define any schema. It exists to surface a
clear, early error if the database is unreachable or the Postgres image lacks
pgvector.
"""

import asyncio

import asyncpg

from mcp_coco import config


async def main() -> None:
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = await conn.fetchval(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        )
        print(f"OK: database reachable, pgvector {version} available.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
