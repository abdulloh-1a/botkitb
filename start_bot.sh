#!/usr/bin/env bash
# Botni avtomatik qayta ishga tushurish bilan ishga tushiradi.
set -u
cd "$(dirname "$0")"

while true; do
    echo "[$(date '+%F %T')] Bot ishga tushurilyapti..."
    .venv/bin/python bot.py
    code=$?
    echo "[$(date '+%F %T')] Bot to'xtadi (exit=$code), 5 soniyadan keyin qayta ishga tushuriladi."
    sleep 5
done
