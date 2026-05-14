# Job Tracker SaaS — Project Notes

## What This Project Is
- A web app that automatically tracks your job applications by reading your Gmail
- Started as a local single-user tool, converted into a multi-user SaaS product
- Users sign in with Google, grant Gmail access, and the app scans their inbox for job-related emails

---

## Tech Stack

| Layer | Tool | What It Does |
|---|---|---|
| Backend | Flask (Python) | Handles routes, login, API endpoints |
| Auth | Authlib + Flask-Login | Google Sign-In, session management |
| Database | PostgreSQL (Supabase) | Stores users, applications, sync logs |
| ORM | SQLAlchemy | Python talks to PostgreSQL |
| Gmail API | google-api-python-client | Reads Gmail inbox |
| Frontend | HTML + Tailwind CSS + Vanilla JS | Dashboard UI |
| Hosting | Railway | Runs the Flask app in the cloud |
| Secrets | python-dotenv (.env file) | Keeps API keys out of code |

---

## How Google Sign-In Works (Step by Step)

1. User clicks "Continue with Google" on `/login`
2. Flask redirects to Google's login page via `/auth/google`
3. User logs in and clicks "Allow" on Google's consent screen
4. Google redirects back to `/auth/callback` with an access token
5. Flask saves the user's info into the `users` table in PostgreSQL
6. Flask saves the Gmail OAuth token as JSON in `users.gmail_token` column
7. Flask-Login creates a session — user is now "logged in"
8. User is redirected to the dashboard

**Key concept:** Other users don't need their own API credentials. Your app's Google OAuth client handles it. They just click "Allow."

---

## How Multi-User Data Isolation Works

- Every table has a `user_id` column (foreign key to `users` table)
- Every database query filters by `current_user.id`
- Example: `SELECT * FROM applications WHERE user_id = 5`
- User A can never see User B's data — it's filtered at the Python level
- We chose NOT to use Supabase RLS (Row Level Security) because Flask connects as a superuser which bypasses RLS anyway

---

## How Gmail Sync Works

1. User clicks "Sync" on the dashboard
2. Flask loads the user's Gmail token from PostgreSQL
3. Builds a Gmail API service using that token
4. Searches Gmail for job-related email subjects (application confirmations, rejections, interview invites)
5. Parses each email to extract company name, job title, status
6. Saves/updates records in the `applications` table
7. If the token expired, it auto-refreshes using the refresh token and saves the new token back to DB

**Key concept:** Old local app used `token.pickle` file. SaaS version stores token as JSON string in PostgreSQL so it works in the cloud with multiple users.

---

## Database Tables

| Table | Purpose |
|---|---|
| `users` | Stores Google account info + Gmail token |
| `applications` | Job applications per user |
| `sync_log` | Tracks last sync time per user |
| `user_config` | Per-user settings (sync days, resume folder) |

---

## Important Files

| File | What It Does |
|---|---|
| `app.py` | Main Flask app — all routes, auth, API endpoints |
| `database.py` | All database functions (PostgreSQL via SQLAlchemy) |
| `gmail_service.py` | Connects to Gmail API, fetches job emails |
| `email_parser.py` | Parses raw email data into structured fields |
| `templates/login.html` | Google Sign-In page |
| `templates/index.html` | Main dashboard UI |
| `static/js/dashboard.js` | Frontend logic (fetch API, render jobs) |
| `.env` | Secret keys — NEVER commit to GitHub |
| `requirements.txt` | Python dependencies |
| `Procfile` | Tells Railway how to run the app (`gunicorn app:app`) |

---

## Secrets (.env file)

```
DATABASE_URL        = Supabase PostgreSQL connection string
GOOGLE_CLIENT_ID    = From Google Cloud Console
GOOGLE_CLIENT_SECRET = From Google Cloud Console
SECRET_KEY          = Random string for Flask session encryption
```

**Rule:** `.env` is in `.gitignore` — it never goes to GitHub. On Railway, you set these as environment variables manually.

---

## Google OAuth — Important Settings

- **OAuth Client Type:** Web Application (not Desktop)
- **Authorized Redirect URI:** must include your Railway URL + `/auth/callback`
  - Local: `http://localhost:5000/auth/callback`
  - Production: `https://your-app.railway.app/auth/callback`
- **Publishing Status:** Production (so any Google user can sign in)
- **Scopes:** `gmail.readonly` requires Google verification (1-7 days)
- Until verified: users see "This app isn't verified" warning but can still proceed

---

## Day 2 — Deploy to Railway (Completed)

**Goal:** Get the app live on a real public URL

**What we did:**
- Created `Procfile` — tells Railway to start the app with `gunicorn app:app --bind 0.0.0.0:$PORT`
- Updated `requirements.txt` — added all missing packages: `gunicorn`, `flask-login`, `authlib`, `sqlalchemy`, `psycopg2-binary`, `python-dotenv`
- Updated `.gitignore` — added `.env` and `client_secret.json` so secrets never go to GitHub
- Set environment variables on Railway — `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SECRET_KEY`
- Fixed Supabase connection — switched from direct connection (port 5432, IPv6, broken on Railway) to **Session pooler** (IPv4, works)
- Added `ProxyFix` middleware — Railway handles HTTPS externally but Flask only sees HTTP internally; ProxyFix tells Flask to trust Railway's headers so `url_for()` generates `https://` correctly
- Added Railway URL to Google OAuth authorized redirect URIs
- App is live at `https://web-production-55ace.up.railway.app`

**Errors we fixed:**
- `Could not parse SQLAlchemy URL` — DATABASE_URL had placeholder text instead of real value
- `Network is unreachable` — Supabase direct connection uses IPv6, Railway couldn't reach it; fixed with Session pooler
- `database "postgres\n" does not exist` — newline character at end of DATABASE_URL when pasting; fixed by clean paste
- `redirect_uri_mismatch` — Flask generating `http://` instead of `https://`; fixed with ProxyFix
- `Application failed to respond` — gunicorn not bound to Railway's `$PORT`; fixed Procfile

---

## 4-Day Build Plan

| Day | Goal | Status |
|---|---|---|
| Day 1 | Google Sign-In + PostgreSQL + per-user data | Done (reverted) |
| Day 2 | Deploy to Railway (live public URL) | Done (reverted) |
| Day 3 | Email parsing accuracy + Gemini AI + bug fixes | Done ✅ |
| Day 4 | Reverted to local SQLite version | Done ✅ |

---

## How Gmail Access Works for Other Users

- When a user clicks "Sign in with Google", Google shows a consent screen:
  - "Job Tracker wants to: See your basic profile info + Read your Gmail messages"
- When they click **Allow** — your app gets permission to read their Gmail
- You never need their API credentials. Your `client_id` and `client_secret` are the identity of your app

```
Your Google Cloud Project
        │
        │  has ONE OAuth app
        │
        ├── User A signs in → grants Gmail access → their token saved in DB
        ├── User B signs in → grants Gmail access → their token saved in DB
        └── User C signs in → grants Gmail access → their token saved in DB
```

- **`client_id` / `client_secret`** = identity of your app (like a username/password for the app itself)
- **Each user's token** = their personal permission slip: "Job Tracker can read my Gmail"
- **Tokens are saved per-user** in the `users` table (`gmail_token` column) in Supabase
- If a token expires, it auto-refreshes using the `refresh_token` and saves the new token back to DB

---

## Day 3 — Email Parsing Accuracy + Bug Fixes (Completed)

**Goal:** Make email parsing more accurate, fix production bugs

**What we did:**

- **Fixed analytics bar chart** — dates were returned as "Sat, 07 Mar 2026 00:00:00 GMT"; fixed by using PostgreSQL `TO_CHAR(DATE(applied_at::timestamp), 'YYYY-MM-DD')` to return clean ISO strings
- **Fixed "Today" count** — was always 0 because `CURRENT_DATE` used DB timezone; fixed with Python string prefix comparison `applied_at LIKE '2026-04-02%'`
- **Fixed Gmail token error after Railway deploy** — token was saved with `null` client_id/secret; fixed so `gmail_service.py` always reads credentials from env vars, never from DB
- **Fixed infinite redirect loop on sign-in** — Google requires `prompt='consent'` passed directly to `authorize_redirect()`, not just in OAuth config; if no refresh_token received, show error on login page instead of looping
- **Added Gemini 1.5 Flash AI fallback** — when regex parser returns "Unknown Position", the app calls Gemini API (free tier, 15 req/min) to extract title from email subject + body
- **Highlighted Unknown Position in orange** — dashboard shows orange ✏️ icon on any entry still unresolved, prompting user to edit manually
- **Added reauth_required flag** — if Gmail token is expired/invalid, sync returns this flag; frontend auto-shows toast and redirects to logout
- **Fixed NVIDIA req number titles** — `JR2014497 AI Compiler Engineer` → `AI Compiler Engineer`; regex strips `^[A-Z]{0,5}\d{5,}\s+` from start of title
- **Fixed Apple req number titles** — `Data Scientist 200650082` → `Data Scientist`; added `\s+[A-Z]{0,5}\d{5,}$` to also strip from END of title
- **upsert improved** — Full Resync now detects and replaces existing titles that have req number patterns (both leading and trailing)

**Key concepts learned:**
- **Gemini 1.5 Flash** — Google's free AI model, called via REST API with `GEMINI_API_KEY`. Used as a fallback when regex can't extract the job title
- **Regex anchors** — `^` means start of string, `$` means end. `^[A-Z]{0,5}\d{5,}` strips req numbers at start; `\s+\d{5,}$` strips at end
- **upsert logic** — on Full Resync, don't overwrite good data. Only update DB if existing title is junk OR has a req number prefix/suffix

**Errors we fixed:**
- `credentials do not contain necessary fields` — client_id/secret were null in DB token; fixed by always reading from env vars
- `analytics empty bars` — wrong date format from PostgreSQL; fixed with TO_CHAR
- `Today count 0` — timezone mismatch; fixed with string prefix comparison
- `Apple "Data Scientist 200650082"` — req number at end not stripped; fixed regex to also strip trailing

---

## Day 4 — Reverted to Local Version (Completed)

**What happened:**
- Tried to launch as a public SaaS on Railway + Supabase
- Hit a hard wall: `gmail.readonly` scope requires a $15,000 Google security audit for public use
- Without it, strangers see "This app isn't verified" and 95% leave
- Decision: revert to local-only personal tool

**What was reverted:**
- Removed PostgreSQL (Supabase) → back to SQLite (`jobs.db`)
- Removed Google OAuth sign-in → dashboard opens directly
- Removed Flask-Login, Authlib, SQLAlchemy, psycopg2, gunicorn
- Removed Railway deployment (Procfile no longer needed)

**What was kept (Day 3 improvements stay):**
- Gemini 1.5 Flash AI fallback for Unknown Position
- Req number stripping (leading + trailing) — NVIDIA, Apple fixes
- PwC email pattern
- Unknown Position orange highlight in dashboard
- Analytics bar chart + heatmap
- Rejection auto-detection

**Key lesson learned:**
- Gmail API `gmail.readonly` scope = fine for personal use, blocked for public SaaS without expensive audit
- Building a SaaS on top of Gmail is technically possible but commercially blocked by Google policy
- The app works perfectly as a personal tool — that is its real value

**How to run:**
```bash
python app.py
# open http://localhost:5000
```

---

## Current Tech Stack (Local Version)

| Layer | Tool | What It Does |
|---|---|---|
| Backend | Flask (Python) | Handles routes, API endpoints |
| Database | SQLite (`jobs.db`) | Local database file on your PC |
| Gmail API | google-api-python-client | Reads Gmail inbox |
| Auth | token.pickle + credentials.json | Local Gmail OAuth token |
| AI Parsing | Google Gemini 1.5 Flash (free) | Fallback for hard-to-parse emails |
| Frontend | HTML + Tailwind CSS + Vanilla JS | Dashboard UI |
| Secrets | python-dotenv (.env) | GEMINI_API_KEY |

---

## Common Beginner Confusions (Cleared Up)

- **Commit message is NOT an email** — it's a short note shown in GitHub history describing what changed
- **Git private repo** — code is on GitHub but only you can see it
- **Supabase RLS** — a database security feature we intentionally skipped (handled in Python instead)
- **Authlib vs google-auth** — Authlib handles the web OAuth flow; google-auth handles the Gmail API calls after login
- **`@login_required`** — a Flask decorator that automatically redirects to login page if user is not signed in
- **`current_user`** — Flask-Login's object that gives you the currently logged-in user's info anywhere in your code
