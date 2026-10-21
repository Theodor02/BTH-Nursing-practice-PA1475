#!/bin/bash

URL="http://localhost:8080"
PROJECT_DIR="/home/bth/NursingPractice/BTH-Nursing-practice-PA1475"
RESTORE_SCRIPT="$PROJECT_DIR/scripts/restore.sh"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/health_log_$(date +"%Y-%m-%d_%H-%M-%S").txt"
LOG_RETENTION_DAYS=30

# Ta bort health logs äldre än 30 dagar
find "$LOG_DIR" -maxdepth 1 -type f -name "health_log_*.txt" -mtime +"$LOG_RETENTION_DAYS" -delete

# Hämta HTTP-statuskoden
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$STATUS_CODE" != "200" ]; then
	echo "$(date +"%Y-%m-%d %H:%M:%S") - Fel uppstod: HTTP-statuskod $STATUS_CODE" >> "$LOG_FILE"
	echo "Kör återställningsscriptet..." >> "$LOG_FILE"

	bash "$RESTORE_SCRIPT" >> "$LOG_FILE" 2>&1

	echo "Återställning klar $(date +"%Y-%m-%d %H:%M:%S")" >> "$LOG_FILE"
else
	exit 0
fi