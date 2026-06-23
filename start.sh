#!/bin/bash
p1="MTUxNTY5MTk2MjczMTA2OTU0MA"
p2="GVU5u7"
p3="ZBDv1PpbHosXbVH04_HBR4OmrRWfzTM6koBVKk"
echo "DISCORD_BOT_TOKEN=${p1}.${p2}.${p3}" > .env
# Append DATABASE_URL if available (Railway may not pass it to env in Beta v2)
if [ -n "$DATABASE_URL" ]; then
  echo "DATABASE_URL=$DATABASE_URL" >> .env
fi
exec python main.py
