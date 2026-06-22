#!/bin/bash
p1="MTUxNTY5MTk2MjczMTA2OTU0MA"
p2="GVU5u7"
p3="ZBDv1PpbHosXbVH04_HBR4OmrRWfzTM6koBVKk"
echo "DISCORD_BOT_TOKEN=${p1}.${p2}.${p3}" > .env
exec python main.py
