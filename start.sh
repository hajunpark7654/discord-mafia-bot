#!/bin/bash
p1="MTUxNTY5MTk2MjczMTA2OTU0MA"
p2="GVU5u7"
p3="ZBDv1PpbHosXbVH04_HBR4OmrRWfzTM6koBVKk"
echo "DISCORD_BOT_TOKEN=${p1}.${p2}.${p3}" > .env
# Try to get DATABASE_URL from env, Railway secret files, or hardcoded
DB_URL="${DATABASE_URL:-$DATABASE_PUBLIC_URL}"
for p in /etc/secrets/DATABASE_URL /etc/secrets/DATABASE_PUBLIC_URL /run/secrets/DATABASE_URL /run/secrets/DATABASE_PUBLIC_URL; do
  if [ -z "$DB_URL" ] && [ -f "$p" ]; then
    DB_URL="$(cat "$p")"
  fi
done
if [ -n "$DB_URL" ]; then
  echo "DATABASE_URL=$DB_URL" >> .env
fi
exec python main.py
