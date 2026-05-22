# QTrain API Reference

Base URL (via Nginx, development): `http://localhost:8080`  
Direct Flask (development): `http://localhost:5000`

---

## Authentication

All endpoints except health probes and `POST /api/auth/login` require a valid session cookie set by the backend. The cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` in production.

`/api/admin/*` routes additionally require the `Admin` or `SuperAdmin` role. Role-specific restrictions are noted per endpoint.

### Error Responses

All error responses share the same shape:

```json
{ "error": "Human-readable message" }
```

| HTTP Status | Meaning |
|---|---|
| 400 | Bad request — malformed body or invalid parameters |
| 401 | No valid session — re-authenticate |
| 403 | Authenticated but insufficient role |
| 404 | Resource not found |
| 409 | Conflict — duplicate name, email domain not allowed, etc. |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

## Health

### `GET /ping`

Liveness probe. No database or Redis contact.

**Response `200`**
```json
{ "status": "ok" }
```

---

### `GET /health`

Readiness probe. Checks database and Redis connectivity.

**Response `200`**
```json
{ "status": "ok", "db": "ok", "redis": "ok" }
```

**Response `503`** (either dependency is unreachable)
```json
{ "status": "degraded", "db": "ok", "redis": "error" }
```

---

## Auth & Users

### `POST /api/auth/login`

Verify a Microsoft Entra ID bearer token and create a backend session. Registers the user on first login.

**Rate limit:** 20 requests/minute

**Request headers**
```
Authorization: Bearer <entra-access-token>
```

**Response `200`** (existing user)
```json
{
  "user_id": 42,
  "created": false,
  "sso_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "email": "student@student.bth.se",
  "role": "Student"
}
```

**Response `201`** (new user — first login)
```json
{
  "user_id": 43,
  "created": true,
  "sso_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "email": "student@student.bth.se",
  "role": "Student"
}
```

**Response `403`** — email domain not in `ALLOWED_EMAIL_DOMAINS`

---

### `GET /api/auth/me`

Return the authenticated user's profile.

**Response `200`**
```json
{
  "user_id": 42,
  "email": "student@student.bth.se",
  "role": "Student",
  "can_access_control_panel": false,
  "can_manage_users": false
}
```

`role` is one of `"Student"`, `"Admin"`, `"SuperAdmin"`.  
`can_access_control_panel` is `true` for Admin and SuperAdmin.  
`can_manage_users` is `true` for SuperAdmin only.

---

### `DELETE /api/auth/me`

Deactivate the authenticated user's local account and delete completed sessions. Microsoft Entra is left unchanged.

**Rate limit:** 30 requests/minute

**Response `200`**
```json
{ "ok": true, "status": "deactivated" }
```

---

### `POST /api/auth/logout`

Invalidate the current backend session.

**Rate limit:** 60 requests/minute

**Response `200`**
```json
{ "message": "Logged out" }
```

---

### `GET /api/admin/user-counts`

Count users grouped by role.

**Required role:** Admin or SuperAdmin

**Response `200`**
```json
{
  "students": 120,
  "admins": 5,
  "super_admins": 2,
  "total_users": 127
}
```

---

### `GET /api/admin/users`

Paginated list of all users (students and admins). SuperAdmin accounts are excluded.

**Required role:** SuperAdmin

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Pagination offset |

**Response `200`**
```json
{
  "students": [
    {
      "id": 42,
      "email": "student@student.bth.se",
      "role": "Student",
      "is_deactivated": false
    }
  ],
  "admins": [],
  "limit": 50,
  "offset": 0
}
```

---

### `PATCH /api/admin/users/<user_id>/role`

Promote or demote a user between `Student` and `Admin`. Cannot target SuperAdmin accounts.

**Required role:** SuperAdmin

**Request body**
```json
{ "role": "Admin" }
```

`role` must be `"Student"` or `"Admin"`.

**Response `200`**
```json
{
  "user_id": 42,
  "email": "user@bth.se",
  "role": "Admin"
}
```

---

### `DELETE /api/admin/users/<user_id>`

Deactivate another user's local account and delete completed sessions. Cannot target SuperAdmin accounts.

**Required role:** SuperAdmin

**Response `200`**
```json
{ "ok": true, "status": "deactivated" }
```

---

### `PATCH /api/admin/users/<user_id>/activate`

Reactivate a locally deactivated user. Cannot target SuperAdmin accounts.

**Required role:** SuperAdmin

**Response `200`**
```json
{ "ok": true, "status": "activated" }
```

---

## Categories & Units

### `GET /api/categories`

All active categories with their active question templates, grouped by linked course. Response is cached in Redis for 5 minutes and invalidated on any admin mutation.

**Required auth:** User session

**Response `200`**
```json
{
  "courses": {
    "MEK": {
      "course_name": "Mekanik",
      "categories": {
        "Kinematik": {
          "category_id": 3,
          "question_count": 12
        }
      }
    }
  }
}
```

---

### `GET /api/units`

All active units with their accepted aliases.

**Required auth:** User session

**Response `200`**
```json
{
  "units": [
    {
      "id": 1,
      "name": "m/s",
      "aliases": ["meter per sekund", "m s^-1"]
    }
  ]
}
```

---

## Questions & Attempts

### `POST /api/questions`

Generate a question set for a new attempt. Variable values are randomised on the server. Returns an `attempt_id` that must be included in subsequent grade and submit calls.

**Required auth:** User session

**Limits**
- Max 10 courses per request
- Max 20 categories per course
- Max 50 questions per category
- Max 100 questions total

**Request body**
```json
{
  "questions_request": {
    "course": {
      "MEK": {
        "Kinematik": 3,
        "Dynamik": 2
      },
      "EL": {
        "Ohms lag": 5
      }
    }
  }
}
```

Each value is the number of questions to generate for that category.

**Response `200`**
```json
{
  "attempt_id": "550e8400-e29b-41d4-a716-446655440000",
  "questions": [
    {
      "id": "Kinematik_3_1",
      "template": "En bil accelererar från {v0} m/s till {v1} m/s på {t} sekunder. Hur stor är accelerationen?",
      "variables": {
        "v0": 10,
        "v1": 30,
        "t": 5
      },
      "formula": "(v1 - v0) / t",
      "unit": "m/s²",
      "tolerance": 0.05,
      "tolerance_percent": null,
      "answer_type": "numeric",
      "round_answer": false,
      "hints": ["Använd kinematikens grundformel a = Δv/Δt"],
      "link": "https://example.com/kinematik"
    }
  ]
}
```

**`answer_type` values**

| Value | Format expected on grading | Example |
|---|---|---|
| `numeric` | Decimal number, optionally with unit | `"4.0 m/s²"` |
| `time_of_day` | `HH:MM` | `"14:30"` |
| `duration` | Compound string | `"1h 20min 30s"`, `"90min"`, `"45s"` |

---

### `POST /api/questions/grade`

Grade a single answer within an active attempt. The attempt stays open — use `POST /api/attempts/submit` to finalise.

**Required auth:** User session

**Request body**
```json
{
  "attempt_id": "550e8400-e29b-41d4-a716-446655440000",
  "question_id": "Kinematik_3_1",
  "answer": "4.0 m/s²"
}
```

**Response `200`**
```json
{
  "correct": true,
  "correctValue": true,
  "correctAnswer": "4.0",
  "hasUnit": true,
  "correctUnit": true
}
```

| Field | Description |
|---|---|
| `correct` | Overall correctness (value AND unit both correct, or no unit required) |
| `correctValue` | Whether the numeric value is within tolerance |
| `correctAnswer` | The correct answer formatted for display |
| `hasUnit` | Whether this question requires a unit |
| `correctUnit` | Whether the submitted unit was accepted (always `null` if `hasUnit` is `false`) |

---

### `POST /api/attempts/submit`

Submit all answers for an attempt, persist the session to the database, and return the score.

**Required auth:** User session

**Request body**
```json
{
  "attempt_id": "550e8400-e29b-41d4-a716-446655440000",
  "answers": {
    "Kinematik_3_1": "4.0 m/s²",
    "Kinematik_3_2": "25 m",
    "Dynamik_1_1": "200 N"
  }
}
```

**Response `200`**
```json
{
  "session_id": 77,
  "score": 66.67,
  "correct_count": 2,
  "scored_count": 3,
  "answered_count": 3
}
```

| Field | Description |
|---|---|
| `score` | Percentage correct (0–100), rounded to 2 decimal places |
| `correct_count` | Number of correctly answered questions |
| `scored_count` | Number of questions that were graded (excludes unanswered) |
| `answered_count` | Total number of answers submitted |

---

## Session History

### `GET /api/sessions`

All completed sessions for the authenticated user, ordered newest first.

**Required auth:** User session

**Response `200`**
```json
{
  "sessions": [
    {
      "session_id": 77,
      "course_id": 1,
      "course_code": "MEK",
      "category_id": 3,
      "category_name": "Kinematik",
      "score": 66.67,
      "question_count": 3,
      "created_at": "2024-11-01T14:32:10"
    }
  ]
}
```

---

### `GET /api/sessions/<session_id>`

Single session with per-question answer snapshots.

**Required auth:** User session (can only access own sessions)

**Response `200`**
```json
{
  "session_id": 77,
  "course_code": "MEK",
  "category_name": "Kinematik",
  "score": 66.67,
  "created_at": "2024-11-01T14:32:10",
  "questions": [
    {
      "question_id": "Kinematik_3_1",
      "template": "En bil accelererar från 10 m/s till 30 m/s på 5 sekunder...",
      "variables": { "v0": 10, "v1": 30, "t": 5 },
      "user_answer": "4.0 m/s²",
      "correct_answer": "4.0",
      "correct": true,
      "correct_value": true,
      "has_unit": true,
      "correct_unit": true,
      "unit": "m/s²"
    }
  ]
}
```

---

## User Statistics

### `GET /api/stats/overview`

Performance summary for the authenticated user.

**Required auth:** User session

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | int | 30 | Look-back window in days |

**Response `200`**
```json
{
  "total_sessions": 24,
  "total_questions_answered": 156,
  "average_score": 71.4,
  "best_score": 100.0,
  "days": 30
}
```

---

### `GET /api/stats/mastery`

Mastery breakdown by course and category.

**Required auth:** User session

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | int | 30 | Look-back window in days |

**Response `200`**
```json
{
  "courses": {
    "MEK": {
      "course_name": "Mekanik",
      "average_score": 74.2,
      "session_count": 10,
      "categories": {
        "Kinematik": {
          "average_score": 80.0,
          "session_count": 6
        },
        "Dynamik": {
          "average_score": 65.0,
          "session_count": 4
        }
      }
    }
  },
  "days": 30
}
```

---

### `GET /api/stats/activity`

Daily session count heatmap for the activity calendar.

**Required auth:** User session

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `weeks` | int | 12 | Number of past weeks to include |

**Response `200`**
```json
{
  "activity": [
    { "date": "2024-10-28", "count": 3 },
    { "date": "2024-10-29", "count": 0 },
    { "date": "2024-10-30", "count": 1 }
  ],
  "weeks": 12
}
```

---

## Admin — Entity Management

All endpoints in this section require `Admin` or `SuperAdmin` role.

---

### `GET /api/admin/courses`

All courses including archived ones.

**Response `200`**
```json
{
  "courses": [
    {
      "id": 1,
      "course_code": "MEK",
      "name": "Mekanik",
      "active": true,
      "created_at": "2024-01-10T08:00:00",
      "last_updated": "2024-09-01T10:00:00"
    }
  ]
}
```

---

### `POST /api/admin/courses`

Create a new course.

**Request body**
```json
{
  "course_code": "EL",
  "name": "Ellära"
}
```

**Response `201`**
```json
{
  "id": 5,
  "course_code": "EL",
  "name": "Ellära",
  "active": true
}
```

---

### `PATCH /api/admin/courses/<course_id>`

Update a course's code or name.

**Request body** (all fields optional)
```json
{
  "course_code": "EL2",
  "name": "Ellära II"
}
```

**Response `200`** — Updated course object (same shape as GET)

---

### `POST /api/admin/courses/<course_id>/archive`

Toggle a course's archived state.

**Request body**
```json
{ "active": false }
```

**Response `200`** — Updated course object

---

### `GET /api/admin/categories`

All categories with their linked courses and question counts.

**Response `200`**
```json
{
  "categories": [
    {
      "id": 3,
      "name": "Kinematik",
      "active": true,
      "question_count": 12,
      "courses": ["MEK", "FYS"],
      "created_at": "2024-01-10T08:00:00"
    }
  ]
}
```

---

### `POST /api/admin/categories`

Create a new category and optionally link it to courses.

**Request body**
```json
{
  "name": "Elektromagnetism",
  "course_codes": ["EL", "FYS"]
}
```

**Response `201`** — Created category object

---

### `PATCH /api/admin/categories/<category_id>`

Update a category's name or course links.

**Request body** (all fields optional)
```json
{
  "name": "Elektromagnetism II",
  "course_codes": ["EL"]
}
```

**Response `200`** — Updated category object

---

### `POST /api/admin/categories/<category_id>/archive`

Toggle a category's archived state.

**Request body**
```json
{ "active": false }
```

**Response `200`** — Updated category object

---

### `GET /api/admin/questions`

Paginated question template list.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `limit` | int | Page size (default 50, max 100) |
| `offset` | int | Pagination offset (default 0) |
| `course_id` | int | Filter by course |
| `category_id` | int | Filter by category |

**Response `200`**
```json
{
  "questions": [
    {
      "id": 101,
      "category_id": 3,
      "category_name": "Kinematik",
      "question_number": 1,
      "template": "En bil accelererar från {v0} m/s...",
      "unit": "m/s²",
      "active": true
    }
  ],
  "total": 84,
  "limit": 50,
  "offset": 0
}
```

---

### `GET /api/admin/questions/<question_id>`

Full detail for a single question template including all grading configuration fields.

**Response `200`**
```json
{
  "id": 101,
  "category_id": 3,
  "question_number": 1,
  "template": "En bil accelererar från {v0} m/s till {v1} m/s på {t} sekunder. Beräkna accelerationen.",
  "variables": {
    "v0": { "min": 5, "max": 20, "step": 1 },
    "v1": { "min": 25, "max": 60, "step": 1 },
    "t":  { "min": 2, "max": 10, "step": 1 }
  },
  "formula": "(v1 - v0) / t",
  "unit": "m/s²",
  "tolerance": 0.05,
  "tolerance_percent": null,
  "answer_type": "numeric",
  "round_answer": false,
  "answer_min": null,
  "answer_max": null,
  "round_to_unit": null,
  "hints": ["Använd a = Δv/Δt"],
  "link": null,
  "active": true,
  "courses": ["MEK"]
}
```

---

### `POST /api/admin/questions`

Create a new question template.

**Request body**
```json
{
  "category_id": 3,
  "question_number": 15,
  "template": "...",
  "variables": { ... },
  "formula": "...",
  "unit": "m/s²",
  "tolerance": 0.05,
  "answer_type": "numeric",
  "hints": [],
  "course_codes": ["MEK"]
}
```

**Response `201`** — Created question object (same shape as GET detail)

---

### `PATCH /api/admin/questions/<question_id>`

Update any fields on a question template.

**Request body** — any subset of the create fields

**Response `200`** — Updated question object

---

### `POST /api/admin/questions/<question_id>/archive`

Toggle a question template's archived state.

**Request body**
```json
{ "active": false }
```

**Response `200`** — Updated question object

---

### `GET /api/admin/units`

All units with aliases.

**Response `200`**
```json
{
  "units": [
    {
      "id": 1,
      "name": "m/s",
      "active": true,
      "aliases": [
        { "id": 4, "alias": "meter per sekund" },
        { "id": 5, "alias": "m s^-1" }
      ]
    }
  ]
}
```

---

### `POST /api/admin/units`

Create a new unit.

**Request body**
```json
{ "name": "km/h" }
```

**Response `201`**
```json
{ "id": 12, "name": "km/h", "active": true, "aliases": [] }
```

---

### `PATCH /api/admin/units/<unit_id>`

Update a unit's name.

**Request body**
```json
{ "name": "km/h²" }
```

**Response `200`** — Updated unit object

---

### `POST /api/admin/units/<unit_id>/archive`

Toggle a unit's archived state.

**Request body**
```json
{ "active": false }
```

**Response `200`** — Updated unit object

---

### `POST /api/admin/unit-aliases`

Create a new alias for an existing unit.

**Request body**
```json
{
  "unit_id": 1,
  "alias": "m/s"
}
```

**Response `201`**
```json
{ "id": 9, "unit_id": 1, "alias": "m/s" }
```

---

### `PATCH /api/admin/unit-aliases/<alias_id>`

Update an alias string.

**Request body**
```json
{ "alias": "meter per second" }
```

**Response `200`**
```json
{ "id": 9, "unit_id": 1, "alias": "meter per second" }
```

---

### `DELETE /api/admin/unit-aliases/<alias_id>`

Delete a unit alias permanently.

**Response `200`**
```json
{ "message": "Alias deleted" }
```

---

### `GET /api/admin/entity/<entity_type>/<entity_id>`

Fetch a single entity by type and ID. Prefer the dedicated REST endpoints above; this is a legacy utility route.

**Entity type values**

| Value | Entity |
|---|---|
| `0` | Course |
| `1` | Category |
| `2` | Question |
| `3` | Unit |

**Response `200`** — Entity object (same shape as the dedicated GET endpoints)

---

### `POST /api/admin/mutate`

Batch create, edit, and archive operations in a single request. Prefer the individual REST endpoints above.

**Request body**
```json
[
  {
    "type": 0,
    "action": 0,
    "body": { "course_code": "EL", "name": "Ellära" }
  },
  {
    "type": 2,
    "action": 1,
    "body": { "id": 101, "active": false }
  }
]
```

**`type` values:** `0` = Course, `1` = Category, `2` = Question, `3` = Unit  
**`action` values:** `0` = CREATE, `1` = ARCHIVE, `2` = EDIT

**Response `200`**
```json
{ "results": [ { "ok": true }, { "ok": true } ] }
```

---

## Admin — Platform Statistics

All endpoints in this section require `Admin` or `SuperAdmin` role.

### `GET /api/admin/stats/overview`

Platform-wide aggregate statistics.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `from_date` | `YYYY-MM-DD` | Start of date range (inclusive) |
| `to_date` | `YYYY-MM-DD` | End of date range (inclusive) |

**Response `200`**
```json
{
  "total_sessions": 1430,
  "total_users": 127,
  "active_users": 94,
  "average_score": 68.3,
  "questions_answered": 9100
}
```

---

### `GET /api/admin/stats/courses`

Per-course session and score breakdown.

**Query parameters:** `from_date`, `to_date` (same as overview)

**Response `200`**
```json
{
  "courses": [
    {
      "course_code": "MEK",
      "course_name": "Mekanik",
      "session_count": 620,
      "average_score": 71.2,
      "unique_users": 85
    }
  ]
}
```

---

### `GET /api/admin/stats/categories`

Per-category breakdown.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `from_date` | `YYYY-MM-DD` | Start of date range |
| `to_date` | `YYYY-MM-DD` | End of date range |
| `course_id` | int | Filter to a single course |

**Response `200`**
```json
{
  "categories": [
    {
      "category_id": 3,
      "category_name": "Kinematik",
      "session_count": 240,
      "average_score": 74.5,
      "unique_users": 60
    }
  ]
}
```

---

### `GET /api/admin/stats/questions`

Per-question difficulty and attempt counts. Useful for identifying which questions students find hardest.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `from_date` | `YYYY-MM-DD` | Start of date range |
| `to_date` | `YYYY-MM-DD` | End of date range |
| `course_id` | int | Filter by course |
| `category_id` | int | Filter by category |
| `sort_by` | string | `"attempts"` or `"score"` (default `"attempts"`) |
| `limit` | int | Max results (default 50) |

**Response `200`**
```json
{
  "questions": [
    {
      "question_id": "Kinematik_3_1",
      "category_name": "Kinematik",
      "attempt_count": 340,
      "correct_count": 198,
      "success_rate": 58.2
    }
  ]
}
```
