#!/bin/bash
# CD 플레이어 실행 (autostart용). 에러는 로그 파일에 남김.
cd /home/pi/codes/piprj
LOG=/home/pi/codes/piprj/autostart.log
PYTHON=/home/pi/miniconda3/envs/gym/bin/python
# conda 경로가 다르면 위 PYTHON을 수정 (which python 으로 확인)

echo "=== $(date) ===" >> "$LOG" 2>&1
exec "$PYTHON" main.py >> "$LOG" 2>&1
