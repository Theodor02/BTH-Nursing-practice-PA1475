# QTrain

A quiz-based study platform for STEM courses. Students select courses and categories, answer parametrised (randomised-variable) physics and maths questions, receive instant grading with feedback, and track their mastery over time. Admins manage the question bank and monitor platform-wide statistics through a control panel.

**Authentication** is handled via Microsoft Entra ID (Azure AD) — no local passwords.

---

## Features

- Parametrised question generation — each attempt uses freshly randomised variable values
- Three answer types: numeric (with tolerance), time-of-day (HH:MM), duration (e.g. `1h 20min`)
- Per-question hints and a built-in calculator
- Instant grading with correct-answer feedback
- Session history, mastery scores, and activity heatmap
- Admin control panel: CRUD for courses, categories, questions, and units
- Role-based access: `Student` / `Admin` / `SuperAdmin`

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, TypeScript 5, Vite 7, React Router 7 |
| **Auth (client)** | MSAL Browser (`@azure/msal-browser`) |
| **UI** | Lucide React icons, canvas-confetti |
| **Backend** | Python 3.12, Flask 3.1, SQLAlchemy 2, Alembic |
| **Auth (server)** | PyJWT — validates Entra ID bearer tokens |
| **Sessions** | Flask-Session backed by Redis 7 |
| **Rate limiting** | Flask-Limiter (Redis storage) |
| **Database** | PostgreSQL 16 |
| **WSGI (prod)** | Gunicorn (`gthread` workers) |
| **Proxy** | Nginx — rate-limit zones, security headers, upstream routing |
| **Containers** | Docker Compose (dev + prod-style profiles) |

---

## Prerequisites

- [Docker Engine ≥ 24](https://docs.docker.com/engine/install/) or Docker Desktop
- Docker Compose plugin (`docker compose`)
- Git

Optional quick check:

```bash
bash scripts/check-prereqs.sh
```

Manual check:

```bash
docker --version
docker compose version
git --version
```

> **Running outside Docker** requires Node 20+ (frontend) and Python 3.12+ (backend).

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url>
cd fokuslokus
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in all required values (see [Environment Variables](#environment-variables) below).

### 3. Start the development stack

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| App (via Nginx) | http://localhost:8080 |
| Frontend (direct) | http://localhost:5173 |
| Backend (direct) | http://localhost:5000 |
| Postgres | localhost:5432 |

On first startup with an empty database, the app automatically seeds default courses, categories, and question templates from `backend/logic/default/`.

### 4. Stop services

```bash
docker compose down            # stop containers
docker compose down -v         # stop + delete volumes (wipes database)
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values. **Never commit `.env` with real secrets.**

### Backend

| Variable | Required | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | Yes | Session encryption key — generate with `openssl rand -hex 32` |
| `AZURE_TENANT_ID` | Yes | Entra tenant ID used for token validation |
| `AZURE_FRONTEND_CLIENT_ID` | Yes | Frontend app registration client ID |
| `AZURE_API_CLIENT_ID` | Yes | Backend API app registration client ID |
| `AZURE_API_REQUIRED_SCOPE` | Yes | Required scope asserted on incoming tokens |
| `ALLOWED_EMAIL_DOMAINS` | Yes | Comma-separated allowed email domains (e.g. `student.bth.se,bth.se`) |
| `SUPER_ADMIN_EMAILS` | Yes | Comma-separated emails bootstrapped as SuperAdmin on first login |
| `ADMIN_DEBUG_ALL` | No | Set `true` to bypass admin auth checks — **dev only, never prod** |

### Frontend (Vite `VITE_` prefix)

| Variable | Required | Description |
|---|---|---|
| `VITE_AZURE_TENANT_ID` | Yes | Entra tenant ID for MSAL |
| `VITE_AZURE_CLIENT_ID` | Yes | Frontend client ID for MSAL |
| `VITE_AZURE_API_SCOPE` | Yes | API scope requested by MSAL on sign-in |
| `VITE_AZURE_REDIRECT_URI` | No | OAuth redirect URI (defaults to `window.location.origin`) |
| `VITE_API_BASE_URL` | No | Override the backend base URL used by the API client |

---

## Project Structure

```
fokuslokus/
├── backend/
│   ├── app.py                   # Flask app factory, blueprint registration, CSRF middleware
│   ├── config.py                # All configuration constants and env-var reads
│   ├── extensions.py            # Shared Flask extensions (db, limiter, session)
│   ├── gunicorn.conf.py         # Gunicorn tuning (reads env vars)
│   ├── routes/
│   │   ├── admin_routes.py      # CRUD for courses, categories, questions, units
│   │   ├── auth_routes.py       # Login, logout, user management, role promotion
│   │   ├── cat_routes.py        # Category & unit retrieval (Redis-cached, 5 min TTL)
│   │   ├── question_routes.py   # Question generation, grading, attempt submission
│   │   ├── session_routes.py    # Session / attempt history
│   │   └── stats_routes.py      # User and admin statistics
│   ├── logic/
│   │   ├── auth.py              # Session/auth helpers
│   │   ├── grader.py            # Answer grading (numeric, time_of_day, duration)
│   │   ├── question_gen/        # Parametrised question generation engine
│   │   └── database/
│   │       ├── init/            # SQLAlchemy models, schema initialisation
│   │       ├── operations/      # Query helpers per entity type
│   │       └── seeding/         # Default data seeding from JSON files
│   └── tests/                   # pytest unit tests
├── frontend/ReactApp/
│   ├── src/
│   │   ├── pages/               # Route-level views (Login, Home, Questions, History, ControlPanel…)
│   │   ├── components/          # Reusable UI (Button, Header, Modal, Calculator, ResultOverlay…)
│   │   ├── services/
│   │   │   ├── apt.ts           # All backend API calls — single source of truth
│   │   │   └── entraAuth.ts     # MSAL auth flow + backend session sync
│   │   ├── context/
│   │   │   ├── DarkModeContext  # Dark mode toggle (persisted to localStorage)
│   │   │   └── LeaveGuardContext# Blocks accidental navigation during an active attempt
│   │   └── themes/              # Styling themes
│   └── vite.config.ts           # Dev proxy to backend, backend URL env-var driven
├── nginx/
│   └── dev.conf                 # Rate-limit zones (10 req/s), security headers, upstream routing
├── docker-compose.yml           # Dev stack: Flask debug + Vite HMR + bind mounts
├── docker-compose.prod.yml      # Prod-style stack: Gunicorn, immutable images
├── .env.example                 # Environment variable template
└── scripts/
    └── check-prereqs.sh         # Verify Docker & Git are installed
```

---

## API Overview

All endpoints are served through Nginx on port `8080` in development. API calls from the frontend go through the Vite dev proxy to Flask on port `5000`.

Session cookie auth is required for all routes except the health probes and `/api/auth/login`. `/api/admin/*` routes additionally require `Admin` or `SuperAdmin` role.

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/ping` | Liveness probe — no DB or Redis touch |
| GET | `/health` | Readiness probe — checks DB and Redis connectivity |

### Auth & Users

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | — | Verify Entra bearer token, create backend session |
| GET | `/api/auth/me` | User | Return current user's role and metadata |
| DELETE | `/api/auth/me` | User | Deactivate own account locally and remove saved sessions |
| POST | `/api/auth/logout` | — | Invalidate backend session |
| GET | `/api/admin/user-counts` | Admin | Count users by role |
| GET | `/api/admin/users` | SuperAdmin | Paginated user list |
| PATCH | `/api/admin/users/<id>/role` | SuperAdmin | Promote or demote a user's role |
| DELETE | `/api/admin/users/<id>` | SuperAdmin | Deactivate another user's account locally |
| PATCH | `/api/admin/users/<id>/activate` | SuperAdmin | Reactivate a locally deactivated account |

### Categories & Units

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/categories` | User | All active categories with question counts (Redis-cached) |
| GET | `/api/units` | User | All active units with aliases |

### Questions & Attempts

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/questions` | User | Generate a question set — pass a course/category/count map |
| POST | `/api/questions/grade` | User | Grade a single answer within an active attempt |
| POST | `/api/attempts/submit` | User | Submit all answers; persist and score the session |

### Session History

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/sessions` | User | All completed sessions for the authenticated user |
| GET | `/api/sessions/<id>` | User | Single session with per-question answer snapshots |

### User Statistics

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/stats/overview` | User | Performance summary (`?days=N`) |
| GET | `/api/stats/mastery` | User | Mastery by course and category (`?days=N`) |
| GET | `/api/stats/activity` | User | Daily session heatmap (`?weeks=N`) |

### Admin — Entity Management

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/admin/courses` | Admin | All courses |
| POST | `/api/admin/courses` | Admin | Create a course |
| PATCH | `/api/admin/courses/<id>` | Admin | Update a course |
| POST | `/api/admin/courses/<id>/archive` | Admin | Archive or restore a course |
| GET | `/api/admin/categories` | Admin | All categories with linked courses |
| POST | `/api/admin/categories` | Admin | Create a category |
| PATCH | `/api/admin/categories/<id>` | Admin | Update a category |
| POST | `/api/admin/categories/<id>/archive` | Admin | Archive or restore a category |
| GET | `/api/admin/questions` | Admin | Paginated question list |
| GET | `/api/admin/questions/<id>` | Admin | Single question template |
| POST | `/api/admin/questions` | Admin | Create a question template |
| PATCH | `/api/admin/questions/<id>` | Admin | Update a question template |
| POST | `/api/admin/questions/<id>/archive` | Admin | Archive or restore a question |
| GET | `/api/admin/units` | Admin | All units with aliases |
| POST | `/api/admin/units` | Admin | Create a unit |
| PATCH | `/api/admin/units/<id>` | Admin | Update a unit |
| POST | `/api/admin/units/<id>/archive` | Admin | Archive or restore a unit |
| POST | `/api/admin/unit-aliases` | Admin | Create a unit alias |
| PATCH | `/api/admin/unit-aliases/<id>` | Admin | Update a unit alias |
| DELETE | `/api/admin/unit-aliases/<id>` | Admin | Delete a unit alias |
| POST | `/api/admin/mutate` | Admin | Batch create/edit/archive operations (legacy) |

### Admin — Platform Statistics

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/admin/stats/overview` | Admin | Platform-wide aggregate stats (`?from_date`, `?to_date`) |
| GET | `/api/admin/stats/courses` | Admin | Per-course stats |
| GET | `/api/admin/stats/categories` | Admin | Per-category stats |
| GET | `/api/admin/stats/questions` | Admin | Per-question difficulty and attempt counts |

> For full request/response schemas see [`API.md`](API.md) (to be generated).

---

## Available Scripts

### Docker Compose (run from repo root)

| Command | Purpose |
|---|---|
| `docker compose up --build` | Start full development stack |
| `docker compose -f docker-compose.prod.yml up --build` | Start production-style stack (Gunicorn) |
| `docker compose up db backend` | Start database and backend only |
| `docker compose down` | Stop and remove containers |
| `docker compose down -v` | Stop containers and delete all volumes (wipes DB data) |

### Backend (run from `backend/`)

| Command | Purpose |
|---|---|
| `pytest` | Run all unit tests |
| `pytest -vv` | Run tests with verbose output |
| `alembic upgrade head` | Apply pending database migrations (required in production) |

### Frontend (run from `frontend/ReactApp/`)

| Command | Purpose |
|---|---|
| `npm run dev` | Start Vite dev server standalone (port 5173) |
| `npm run build` | TypeScript check + production bundle |
| `npm run lint` | ESLint check |
| `npm run preview` | Serve the production build locally |

### Utility

| Command | Purpose |
|---|---|
| `bash scripts/check-prereqs.sh` | Verify Docker and Git are installed |

---

## Production Stack

Start the production-style stack with Gunicorn:

```bash
docker compose -f docker-compose.prod.yml up --build
```

### Gunicorn Tuning

The backend reads these optional environment variables (defaults are tuned for a 4-core machine such as a Raspberry Pi 4):

| Variable | Default | Description |
|---|---|---|
| `WEB_CONCURRENCY` | `3` | Number of worker processes |
| `GUNICORN_WORKER_CLASS` | `gthread` | Worker type |
| `GUNICORN_THREADS` | `2` | Threads per worker |
| `GUNICORN_TIMEOUT` | `60` | Worker timeout (seconds) |
| `GUNICORN_GRACEFUL_TIMEOUT` | `30` | Graceful shutdown timeout |
| `GUNICORN_KEEPALIVE` | `5` | Keep-alive duration |
| `GUNICORN_MAX_REQUESTS` | `1000` | Requests before worker recycle |
| `GUNICORN_MAX_REQUESTS_JITTER` | `100` | Jitter added to max requests |
| `GUNICORN_PRELOAD_APP` | `true` | Load app before forking (copy-on-write) |
| `GUNICORN_WORKER_TMP_DIR` | `/dev/shm` | Worker heartbeat temp directory |
| `GUNICORN_LOG_LEVEL` | `info` | Gunicorn log verbosity |

---

## User Roles & Admin Access

Users authenticate through Entra ID. Local authorisation is stored in `users.role`:

| Role | Permissions |
|---|---|
| `Student` | Answer questions, view own history and statistics |
| `Admin` | Everything above + access control panel, manage courses/categories/questions |
| `SuperAdmin` | Everything above + manage other users (list, promote/demote, delete) |

`SUPER_ADMIN_EMAILS` bootstraps SuperAdmin access — any listed email is granted SuperAdmin role on their first login.

---

## Development Notes

- Backend source is bind-mounted in dev mode — Flask reloads automatically on file changes.
- Frontend uses Vite HMR — changes reflect immediately in the browser.
- The seeding script drops and recreates the schema only when **all three** conditions are met: `ENV=dev`, `CONFIRM_DROP_SCHEMA=true`, and `POSTGRES_HOST` is a local address or the Compose service name `db`.
- Add or update tests in `backend/tests/` whenever backend behaviour changes, and run `pytest` before finalising any backend change.
- All API calls in the frontend must go through [`services/apt.ts`](frontend/ReactApp/src/services/apt.ts) — do not fetch directly in components.
- New Flask blueprints must be registered in [`backend/app.py`](backend/app.py).
- All `/api/admin/*` routes must call the admin auth check (see `admin_routes.py` for the pattern).
