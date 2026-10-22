#!/bin/sh
set -eu

# الزرع الحتمي آمن لإعادة التشغيل، لكنه يُنفّذ فقط إذا كانت القاعدة فاضية حتى
# لا يمتلئ تاريخ الزرع بعمليات لا تضيف شيئًا عند كل إعادة تشغيل.
python seed_data.py --if-empty

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips='*'
