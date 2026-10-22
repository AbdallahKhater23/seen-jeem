"""مهام مزامنة بنك الأسئلة مع مصادر خارجية.

التنفيذ الحالي داخل عملية FastAPI عبر BackgroundTasks، وهو **ليس** نظام مهام
متينًا: المهمة لا تُستأنف إذا أُعيد تشغيل العملية. لذلك:
- تُسجَّل الحالة في `sync_jobs` (queued/running/succeeded/partial/failed).
- تُمنع المهام المتزامنة المكررة بفهرس فريد جزئي.
- عند الإقلاع تُعلَّم المهام العالقة `failed` بسبب انقطاع العملية.
- الفشل الخارجي لا يمسّ بيانات موجودة؛ الحصاد تراكمي فقط.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from ..config import Settings
from ..db import connect, transaction
from ..utils.errors import conflict
from .harvester import CACHE_DIR_NAME, run_harvest

ACTIVE_STATUSES = ("queued", "running")
STALE_AFTER = timedelta(minutes=30)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def start_sync_job(
    settings: Settings, *, source: str = "restcountries", category_slug: str | None = None
) -> dict:
    """يقبل المهمة فعلًا أو يرفضها بوضوح إن كانت هناك مهمة نشطة لنفس المصدر."""
    # مفتاح كل محاولة فريد، ومنع التكرار يعتمد على المصدر/الفئة + الحالة النشطة.
    job_key = f"{source}:{category_slug or 'all'}:{uuid.uuid4().hex[:10]}"
    async with transaction(settings) as db:
        cursor = await db.execute(
            "SELECT id, status FROM sync_jobs WHERE source_name = ?"
            " AND COALESCE(category_slug, '') = COALESCE(?, '')"
            " AND status IN ('queued', 'running') ORDER BY id DESC LIMIT 1",
            (source, category_slug),
        )
        active = await cursor.fetchone()
        await cursor.close()
        if active:
            return {
                "accepted": False,
                "status": active["status"],
                "job_id": int(active["id"]),
                "job_key": job_key,
                "message": "في مهمة مزامنة نشطة لنفس المصدر؛ ما نكررها.",
                "detail": {"deduplicated": True},
            }
        cursor = await db.execute(
            """
            INSERT INTO sync_jobs(job_key, source_name, category_slug, status)
            VALUES (?, ?, ?, 'queued')
            """,
            (job_key, source, category_slug),
        )
        job_id = int(cursor.lastrowid)
        await cursor.close()
    return {
        "accepted": True,
        "status": "queued",
        "job_id": job_id,
        "job_key": job_key,
        "message": "تم قبول طلب المزامنة؛ التنفيذ بالخلفية.",
        "detail": {"durable": False, "background": True},
    }


async def run_sync_job(settings: Settings, job_id: int, *, force: bool = True) -> dict:
    async with transaction(settings) as db:
        cursor = await db.execute(
            "SELECT status FROM sync_jobs WHERE id = ?", (job_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row or row["status"] != "queued":
            return {"job_id": job_id, "status": row["status"] if row else "missing"}
        await db.execute(
            "UPDATE sync_jobs SET status = 'running', started_at = ? WHERE id = ?",
            (_utc_now(), job_id),
        )
    try:
        result = await run_harvest(settings, force=force)
        status = result["status"]
    except Exception as exc:  # noqa: BLE001 - نسجّل الفشل ولا نُسقط العملية
        result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        status = "failed"
    async with transaction(settings) as db:
        await db.execute(
            """
            UPDATE sync_jobs
            SET status = ?, finished_at = ?, detail_json = ?, error = ?
            WHERE id = ?
            """,
            (
                status,
                _utc_now(),
                json.dumps(result, ensure_ascii=False),
                result.get("error"),
                job_id,
            ),
        )
    return {"job_id": job_id, **result}


async def list_sync_jobs(settings: Settings, *, limit: int = 20) -> dict:
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT * FROM sync_jobs ORDER BY id DESC LIMIT ?", (limit,)
        )
        jobs = []
        for row in await cursor.fetchall():
            jobs.append(
                {
                    "id": int(row["id"]),
                    "job_key": row["job_key"],
                    "source": row["source_name"],
                    "category_slug": row["category_slug"],
                    "status": row["status"],
                    "requested_at": row["requested_at"],
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                    "detail": json.loads(row["detail_json"] or "{}"),
                    "error": row["error"],
                }
            )
        await cursor.close()
        cursor = await db.execute("SELECT * FROM harvester_cursors ORDER BY source_name")
        cursors = [
            {
                "source": row["source_name"],
                "category_slug": row["category_slug"],
                "cursor": row["cursor"],
                "last_synced_at": row["last_synced_at"],
                "total_harvested": int(row["total_harvested"]),
            }
            for row in await cursor.fetchall()
        ]
        await cursor.close()
    return {
        "jobs": jobs,
        "cursors": cursors,
        "cache_dir": CACHE_DIR_NAME,
        "durable": False,
    }


async def recover_interrupted_jobs(settings: Settings) -> int:
    """يعلّم المهام العالقة من عملية سابقة بالفشل؛ لا يدّعي استئنافها."""
    cutoff = (datetime.now(timezone.utc) - STALE_AFTER).isoformat(timespec="seconds")
    async with transaction(settings) as db:
        cursor = await db.execute(
            """
            UPDATE sync_jobs
            SET status = 'failed', finished_at = ?,
                error = 'interrupted:process_restart'
            WHERE status IN ('queued', 'running')
              AND COALESCE(started_at, requested_at) < ?
            """,
            (_utc_now(), cutoff),
        )
        count = int(cursor.rowcount or 0)
        await cursor.close()
    return count
