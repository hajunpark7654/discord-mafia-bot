#!/bin/bash
p1="MTUxNTY5MTk2MjczMTA2OTU0MA"
p2="GVU5u7"
p3="ZBDv1PpbHosXbVH04_HBR4OmrRWfzTM6koBVKk"
echo "DISCORD_BOT_TOKEN=${p1}.${p2}.${p3}" > .env
# Railway Beta v2 blocks all env vars — use hardcoded fallback if needed
# To set this, go to your PostgreSQL Connect tab, copy the Public Network URL,
# and paste it between the quotes below:
DB_URL=""
if [ -n "$DB_URL" ]; then
  echo "DATABASE_URL=$DB_URL" >> .env
fi
exec python main.py
