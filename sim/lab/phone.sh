#!/bin/bash
# Лаборатория скрутки — открыть с телефона (тот же Wi-Fi).
#   ./phone.sh     запустить и показать адрес
#   Ctrl+C         остановить
cd "$(dirname "$0")"
source ../.venv/bin/activate
PORT="${LAB_PORT:-8770}"
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
echo
echo "  На телефоне открой:   http://$IP:$PORT"
echo "  (телефон и мак должны быть в одной сети Wi-Fi)"
echo
LAB_HOST=0.0.0.0 LAB_PORT="$PORT" python serve.py
