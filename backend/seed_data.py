"""زرع بنك الأسئلة المنسّق (بدون شبكة).

الاستخدام:
  python seed_data.py                    # الزرع المحلي الحتمي
  python seed_data.py --seed 12345       # ترتيب سحب حتمي للاختبارات
  python seed_data.py --database /tmp/test.db
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path

from app.config import load_settings
from app.db import connect, init_db
from app.services.seed import seed_database


async def _active_questions(settings) -> int:
    await init_db(settings)
    async with connect(settings) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) AS n FROM questions WHERE is_active = 1"
        )
        total = int((await cursor.fetchone())["n"])
        await cursor.close()
    return total


async def _run(args: argparse.Namespace) -> dict:
    settings = load_settings()
    if args.database:
        settings = replace(settings, database_path=Path(args.database).expanduser().resolve())
    if args.if_empty:
        existing = await _active_questions(settings)
        if existing:
            return {
                "skipped": True,
                "reason": "existing_questions",
                "total_active": existing,
                "database": str(settings.database_path),
            }
    return await seed_database(
        settings,
        seed_version=args.version,
        deterministic_seed=args.seed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="زرع بنك أسئلة Seen Jeem.")
    parser.add_argument("--database", help="مسار قاعدة بيانات بديل (للاختبار).")
    parser.add_argument("--version", default=None, help="إصدار بيانات الزرع.")
    parser.add_argument("--seed", type=int, default=None, help="بذرة RNG الحتمية.")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="ازرع فقط إذا ما في أسئلة نشطة (مناسب لبدء الحاوية).",
    )
    args = parser.parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
