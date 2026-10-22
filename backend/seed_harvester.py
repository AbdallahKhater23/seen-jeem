"""حاصد البيانات الخارجية: RestCountries + Wikidata.

أمثلة:
  python seed_harvester.py                  # حصاد (يستخدم الكاش إن كان صالحًا)
  python seed_harvester.py --force          # تجاهل الكاش
  python seed_harvester.py --database /tmp/test.db
  python seed_harvester.py --sync           # نفس الحصاد عبر مسار المزامنة المسجّل

الفشل الشبكي ليس خطأً قاتلًا: البيانات الحالية تبقى سليمة، والتقرير يبيّن
المصدر الذي لم يتوفر. لا أسرار ولا رموز تُطبع في السجلات.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import replace
from pathlib import Path

from app.config import load_settings
from app.services.harvester import run_harvest
from app.services.seed import seed_database
from app.services.sync import run_sync_job, start_sync_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("seenjeem.harvester")


async def _run(args: argparse.Namespace) -> dict:
    settings = load_settings()
    if args.database:
        settings = replace(settings, database_path=Path(args.database).expanduser().resolve())
    if args.seed:
        await seed_database(settings)
    if args.sync:
        job = await start_sync_job(settings, source="restcountries")
        if not job["accepted"]:
            return {"accepted": False, "job": job}
        return await run_sync_job(settings, int(job["job_id"]), force=args.force)
    return await run_harvest(settings, force=args.force)


def main() -> None:
    parser = argparse.ArgumentParser(description="حصاد وقائع كرة القدم والدول.")
    parser.add_argument("--database", help="مسار قاعدة بيانات بديل.")
    parser.add_argument("--force", action="store_true", help="تجاهل كاش المصادر.")
    parser.add_argument("--seed", action="store_true", help="زرع البنك المحلي قبل الحصاد.")
    parser.add_argument("--sync", action="store_true", help="تشغيل عبر سجل مهام المزامنة.")
    args = parser.parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info("harvest_status=%s", report.get("status", "unknown"))


if __name__ == "__main__":
    main()
