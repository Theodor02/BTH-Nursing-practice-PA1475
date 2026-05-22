# Database Migration Guide

This guide covers two migration scenarios for the QTrain Postgres 16 and Redis 7 databases:

- **[Old machine → New machine](#self-hosted-old-machine--new-machine)** — moving to new hardware while keeping the self-hosted setup
- **[Self-hosted → Cloud](#raspberry-pi--cloud)** — migrating to managed cloud services

---

## Self-hosted: Old Machine → New Machine

This covers migrating to new hardware while keeping the self-hosted setup (Docker + Cloudflare Tunnel). Redis holds only sessions and rate-limit counters — no business data — so only Postgres needs to be transferred.

The machine you are moving **from** is called `old`, the one you are moving **to** is called `new`.

### Prerequisites on the new machine

Install Docker and Docker Compose, then clone the repo:

```bash
git clone https://github.com/Theodor02/fokuslokus.git
cd fokuslokus
```

Copy the `.env` file from the old machine so all secrets and env vars are identical:

```bash
# Run this on the old machine
scp .env user@<new-ip>:~/fokuslokus/.env
```

### Step 1 — Dump Postgres on the old machine

```bash
pg_dump \
  --host=localhost \
  --port=5432 \
  --username=qtrain \
  --dbname=qtrain \
  --format=custom \
  --no-acl \
  --no-owner \
  --file=qtrain_$(date +%Y%m%d_%H%M%S).dump
```

### Step 2 — Transfer the dump to the new machine

```bash
# Run this on the old machine
scp ~/qtrain_*.dump user@<new-ip>:~/
```

### Step 3 — Start only the DB container on the new machine

```bash
docker compose -f docker-compose.prod.yml up -d db
docker compose -f docker-compose.prod.yml ps
# db should show "(healthy)" before continuing
```

### Step 4 — Restore the dump

```bash
docker cp ~/qtrain_<timestamp>.dump fokuslokus-db-1:/tmp/qtrain.dump

docker compose -f docker-compose.prod.yml exec db \
  pg_restore \
    --host=localhost \
    --username=qtrain \
    --dbname=qtrain \
    --no-acl \
    --no-owner \
    --verbose \
    /tmp/qtrain.dump
```

### Step 5 — Handle Alembic migrations

```bash
# Check the revision recorded in the restored DB
docker compose -f docker-compose.prod.yml exec backend alembic current
```

| Situation | Command |
|---|---|
| Shows `(head)` — schema is current | No action needed |
| New migrations exist in the code that the old DB never ran | `alembic upgrade head` |
| No revision recorded (DB predates Alembic adoption) | `alembic stamp head` |

> `upgrade head` applies unapplied migrations. `stamp head` only records the revision without touching the schema — use it only when the schema already matches HEAD (e.g. after a `pg_restore` of an up-to-date dump).

### Step 6 — Start the full stack

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Step 7 — Update the Cloudflare Tunnel

1. Log into the [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com)
2. Navigate to **Access → Tunnels**
3. Edit the existing tunnel — update the target address from the old machine's local IP to the new machine's local IP
4. No DNS change is needed; the public hostname stays the same

### Step 8 — Verify

```bash
curl https://<your-domain>/ping          # liveness
curl https://<your-domain>/health        # DB + Redis connectivity

docker compose -f docker-compose.prod.yml exec backend alembic current
# Expected: 0001_baseline (head)
```

### Step 9 — Decommission the old machine

Once the new machine has been running without issues for at least 24 hours:

```bash
# On the old machine
docker compose -f docker-compose.prod.yml down
sudo cloudflared service uninstall        # remove the tunnel connector
docker volume rm fokuslokus_db_data       # optional: wipe the old DB volume
```

---

## Raspberry Pi → Cloud

This guide covers migrating the QTrain Postgres 16 and Redis 7 databases from the current self-hosted Raspberry Pi (exposed via Cloudflare Tunnel) to managed cloud services.

---

## Provider Options

### Postgres

| Provider | Free tier | Notes |
|---|---|---|
| **Neon** | 0.5 GB storage, 1 project | Serverless, auto-suspend, great DX, recommended for small apps |
| **Supabase** | 500 MB, pauses after 1 week idle | Full Postgres, includes dashboard and REST API |
| **Railway** | $5 credit/month | Simple deploy, good for co-locating app + DB |
| **Render** | 1 GB, 90-day expiry on free plan | Pairs well if the app is also on Render |
| **AWS RDS (Free Tier)** | 12 months free, db.t3.micro | More ops overhead; good if you're already in AWS |

**Recommendation: Neon** — generous free tier, no idle pausing on the free plan, supports Postgres 16, and connection pooling (PgBouncer) is built in.

### Redis

| Provider | Free tier | Notes |
|---|---|---|
| **Upstash** | 10k commands/day, 256 MB | Serverless, pay-per-use, easiest setup |
| **Redis Cloud** | 30 MB | Reliable, slightly more setup |
| **Railway** | Included in $5 credit | Convenient if Postgres is also on Railway |

**Recommendation: Upstash** — the free tier is sufficient for sessions and rate limiting; no persistent business data lives in Redis.

---

## Pre-migration Checklist

Before touching anything:

- [ ] Confirm the current Alembic revision on the Pi matches `0001_baseline`:
  ```bash
  # SSH into Pi, activate venv
  cd /path/to/fokuslokus/backend
  alembic current
  # Expected: 0001_baseline (head)
  ```
- [ ] Note all active environment variables (check the `.env` file on the Pi or wherever the production compose file reads from)
- [ ] Take a manual Postgres backup (see step 1 below) and store it somewhere safe before starting
- [ ] Schedule a maintenance window — the cutover itself takes ~5 minutes if the dump is small

---

## Step 1 — Dump the Raspberry Pi Database

SSH into the Pi and run:

```bash
pg_dump \
  --host=localhost \
  --port=5432 \
  --username=qtrain \
  --dbname=qtrain \
  --format=custom \
  --no-acl \
  --no-owner \
  --file=qtrain_$(date +%Y%m%d_%H%M%S).dump
```

`--format=custom` produces a compressed binary dump that `pg_restore` can parallelise. If you prefer plain SQL (easier to inspect), replace `--format=custom` with `--format=plain` and change the filename to `.sql`.

Copy the dump off the Pi:

```bash
# From your local machine
scp pi@<pi-ip>:~/qtrain_*.dump ./
```

---

## Step 2 — Provision Cloud Postgres

### Neon (recommended)

1. Create a free account at [neon.tech](https://neon.tech)
2. Create a new project — choose a region close to where the app is hosted
3. Neon creates a default database. Rename it to `qtrain` or note the auto-generated name
4. Copy the connection string from the dashboard. It looks like:
   ```
   postgresql://qtrain:<password>@<host>.neon.tech/qtrain?sslmode=require
   ```
5. Also note the individual components — you will need them for `docker-compose.prod.yml`:
   - `POSTGRES_HOST` = `<host>.neon.tech`
   - `POSTGRES_PORT` = `5432`
   - `POSTGRES_USER` = `qtrain` (or the Neon-generated user)
   - `POSTGRES_PASSWORD` = `<password>`
   - `POSTGRES_DB` = `qtrain`

### Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Settings → Database** to find the connection string
3. Use the **direct connection** string (not the pooler) for the initial restore
4. After data is loaded, switch to the **pooler (Transaction mode)** URL for the app's `POSTGRES_HOST`

---

## Step 3 — Restore the Dump to Cloud Postgres

Ensure `pg_restore` / `psql` 16 is installed locally (`psql --version`).

**Custom-format dump:**
```bash
pg_restore \
  --host=<cloud-host> \
  --port=5432 \
  --username=<cloud-user> \
  --dbname=<cloud-db> \
  --no-acl \
  --no-owner \
  --verbose \
  qtrain_<timestamp>.dump
```

**Plain SQL dump:**
```bash
psql \
  "postgresql://<cloud-user>:<password>@<cloud-host>:5432/<cloud-db>?sslmode=require" \
  -f qtrain_<timestamp>.sql
```

After restoring, stamp Alembic so it knows the schema is already at HEAD (do **not** run `upgrade head` — the schema already exists):

```bash
cd backend
ALEMBIC_DATABASE_URL="postgresql://<cloud-user>:<password>@<cloud-host>:5432/<cloud-db>?sslmode=require" \
  alembic stamp head
```

> If you are starting with a **blank** cloud database instead of restoring a dump, run `alembic upgrade head` instead of `alembic stamp head`.

---

## Step 4 — Provision Cloud Redis (Upstash)

Redis holds only sessions and rate-limit counters — no business data needs migrating. Existing sessions will expire on their own TTL.

1. Create a free account at [upstash.com](https://upstash.com)
2. Create a Redis database — pick the same region as your Postgres
3. Copy the **Redis URL** from the dashboard:
   ```
   rediss://:password@<host>.upstash.io:6379
   ```
   Note the `rediss://` (TLS). This is the value for `REDIS_URL`.

---

## Step 5 — Update Environment Variables

Edit `docker-compose.prod.yml` (or the `.env` file it reads from) to point at the cloud services:

```yaml
# docker-compose.prod.yml — backend service environment block
environment:
  # --- Postgres (change these four) ---
  POSTGRES_HOST: <cloud-host>.neon.tech        # was: db
  POSTGRES_PORT: 5432
  POSTGRES_USER: <cloud-user>
  POSTGRES_PASSWORD: <cloud-password>
  POSTGRES_DB: qtrain

  # --- Redis (change this one) ---
  REDIS_URL: rediss://:<upstash-password>@<host>.upstash.io:6379   # was: redis://redis:6379/0

  # --- Remove or comment out the db and redis service sections ---
  # (they are no longer needed locally)
```

> **Seeding safety note:** The seeding logic in `backend/logic/database/init/` checks that `POSTGRES_HOST` is `localhost` or `db` before allowing a schema drop. A cloud hostname like `<x>.neon.tech` will never match that check, so destructive seeding commands are automatically blocked in production — no extra action needed.

**Sensitive values** (passwords, `FLASK_SECRET_KEY`) should be moved out of the compose file into a secrets manager or CI/CD secret store. At minimum, keep them in `.env` and ensure `.env` is in `.gitignore`.

---

## Step 6 — Remove the Cloudflare Tunnel (Database Tunnel)

Once the app is pointed at the cloud database and verified (step 7), shut down the Cloudflare Tunnel that was exposing the Pi's Postgres port:

1. Log into [Cloudflare Zero Trust dashboard](https://one.dash.cloudflare.com)
2. Navigate to **Access → Tunnels**
3. Find the tunnel used for Postgres access and either **disable** or **delete** it
4. If the Pi is still hosting the application itself, leave any tunnel routes for the app unaffected — only remove the database-specific route

---

## Step 7 — Verification

After updating the env vars and restarting the stack:

```bash
# 1. Liveness check
curl https://<your-domain>/ping
# Expected: {"status":"ok"} or similar

# 2. Readiness check (tests DB + Redis connectivity)
curl https://<your-domain>/health
# Expected: HTTP 200 with both db and redis showing healthy

# 3. Confirm Alembic revision on the cloud DB
cd backend
ALEMBIC_DATABASE_URL="postgresql://..." alembic current
# Expected: 0001_baseline (head)

# 4. Run the test suite against the new connection
POSTGRES_HOST=<cloud-host> \
POSTGRES_USER=<cloud-user> \
POSTGRES_PASSWORD=<cloud-password> \
POSTGRES_DB=qtrain \
pytest -vv
```

---

## Step 8 — Rollback Plan

If anything goes wrong after cutover:

1. **Revert env vars** in `docker-compose.prod.yml` to point back at `db` (local) or the Pi's Cloudflare hostname
2. Re-enable the Cloudflare Tunnel on the Pi if it was disabled
3. Restart the stack — the Pi database will have remained unchanged (it was never written to during the cloud test period)

Keep the Pi's Postgres running in read-only mode for at least 48 hours after a successful cutover so rollback is always available:

```sql
-- On the Pi, connect as superuser and set the database to read-only
ALTER DATABASE qtrain SET default_transaction_read_only = on;
```

After 48 hours with no issues, you can stop the Postgres service on the Pi entirely.
