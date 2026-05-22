#!/bin/bash
PROJECT_DIR="/home/bth/NursingPractice/BTH-Nursing-practice-PA1475"
DB_CONTAINER="bth-nursing-practice-pa1475-db-1"
LATEST_BACKUP=$(ls -t "$PROJECT_DIR/backups/"*.sql | head -1)

cd "$PROJECT_DIR"

echo "Rensar och bygger om från noll..."
docker compose down -v
docker compose -f docker-compose.prod.yml up --build

echo "Väntar på Postgres..."
sleep 15

echo "Återställer data från $LATEST_BACKUP..."
cat "$LATEST_BACKUP" | docker exec -i "$DB_CONTAINER" psql -U qtrain -d qtrain

echo "Klart! All historik är tillbaka."
