#!/bin/bash

URL="http://localhost:8080"
PROJECT_DIR="/home/fokuspi/fokuslokus"
RESTORE_SCRIPT="$PROJECT_DIR/scripts/restore.sh"
LOG_FILE="$PROJECT_DIR/logs/health_log_$(date +"%Y-%m-%d_%H-%M-%S").txt"

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
