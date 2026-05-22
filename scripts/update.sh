#!/bin/bash

# Konfiguration
PROJECT_DIR="/home/bth/NursingPractice/BTH-Nursing-practice-PA1475"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_DIR="$PROJECT_DIR/logs/update_logs"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Databas variabler
DB_USER="qtrain"
DB_NAME="qtrain"
DB_CONTAINER="bth-nursing-practice-pa1475-db-1"

# Skapa mappar ifall de inte finns
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/update_log_$DATE.txt"

# Echoa output till både terminalen och loggfilen
exec > >(tee -a "$LOG_FILE") 2>&1


cd "$PROJECT_DIR" || exit

echo "--- Uppdatering startar: $DATE ---"

echo "Säkerhetskopierar databasen..."
docker exec $DB_CONTAINER pg_dump -U "$DB_USER" --clean --if-exists "$DB_NAME" > "$BACKUP_DIR/db_backup_$DATE.sql"

echo "Behåller 5 senaste databassäkerhetskopiorna och rensar 14 dagar gamla databassäkerhetskopior..."
ls -1t "$BACKUP_DIR"/*.sql 2>/dev/null | tail -n +6 | xargs -d '\n' -I {} find "{}" -mtime +14 -delete

echo "Hämtar senaste ändringarna från Git..."
git pull

echo "Bygger om containrar..."
docker compose -f docker-compose.prod.yml up -d --build

echo "Startar om nginx för att uppdatera DNS..."
docker compose -f docker-compose.prod.yml restart nginx

echo "Rensar gamla images..."
docker image prune -f

echo "--- Uppdatering klar: $DATE ---"

echo "Tar bort loggfiler äldre än 1 vecka..."

find "$LOG_DIR" -type f -name "update_log_*.txt" -mtime +7 -exec rm {} \;

echo "Rensning av gamla loggfiler klar."
