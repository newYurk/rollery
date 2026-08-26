#!/bin/bash
# Лаборатория скрутки — открыть стенд в браузере.
#   ./lab.sh          запустить
#   Ctrl+C            остановить
cd "$(dirname "$0")"
source ../.venv/bin/activate
PORT="${LAB_PORT:-8770}"
( sleep 1.2; open "http://127.0.0.1:$PORT" 2>/dev/null ) &
LAB_PORT="$PORT" python serve.py
