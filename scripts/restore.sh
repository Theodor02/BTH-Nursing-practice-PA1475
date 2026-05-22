#!/bin/bash
PROJECT_DIR="/home/fokuspi/fokuslokus"
DB_CONTAINER="fokuslokus-db-1"
LATEST_BACKUP=$(ls -t "$PROJECT_DIR/backups/"*.sql | head -1)

cd "$PROJECT_DIR"

echo "Rensar och bygger om från noll..."
docker compose down -v
docker compose up -d --build

echo "Väntar på Postgres..."
sleep 15

echo "Återställer data från $LATEST_BACKUP..."
cat "$LATEST_BACKUP" | docker exec -i "$DB_CONTAINER" psql -U qtrain -d qtrain

echo "Klart! All historik är tillbaka."