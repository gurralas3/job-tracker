# Job Tracker — Auto-sync job applications from Gmail

A free, local-first dashboard that automatically tracks your job applications by reading your Gmail. No manual entry. No Chrome extension. Just run it on your PC.

---

## Why I Built This

I was applying to 40-50 jobs per day. Every other tracker (Teal, Huntr, Simplify) required manual entry or a Chrome extension. I wanted something that just worked — run it, sync, done.

---

## How It Works

```
You apply to a job
        ↓
Company sends confirmation email to your Gmail
        ↓
App reads the email (subject + body)
        ↓
Regex + Gemini AI extracts company name + job title
        ↓
Application appears in your dashboard automatically
```

Zero manual entry. Works with any job board — LinkedIn, Indeed, Workday, Greenhouse, company websites.

---

## Features

- **Auto Gmail sync** — scans inbox for application confirmations, rejections, interview invites
- **AI-powered parsing** — regex extracts titles; Gemini 1.5 Flash as fallback for hard-to-parse emails
- **Analytics dashboard** — daily bar chart, heatmap, today/week/total counts
- **Status tracking** — Applied, Phone Screen, Interview, Offer, Rejected
- **Resume folder** — link local resume files/folders to each application
- **Auto-Assign Resumes** — matches company names to your resume folder automatically
- **Full Resync** — re-parse all emails to fix old entries with better accuracy
- **Manual edit** — edit any entry the parser got wrong
- **Unknown Position alerts** — orange highlight on entries that need attention

---

## Tech Stack

| Layer | Tool |
|---|---|
| Backend | Flask (Python) |
| Database | SQLite (local `jobs.db` file) |
| Gmail | Google Gmail API + token.pickle |
| AI Parsing | Google Gemini 1.5 Flash (free tier) |
| Frontend | Tailwind CSS + Vanilla JS |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/gurralas3/job-tracker.git
cd job-tracker
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Enable Gmail API

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project
2. Enable **Gmail API**
3. Go to **APIs & Services → Credentials → Create OAuth 2.0 Client ID**
4. Choose **Desktop Application**
5. Download JSON → rename to `credentials.json` → place in project folder

### 4. Get a free Gemini API key (optional but recommended)

1. Go to [aistudio.google.com](https://aistudio.google.com) → Get API key
2. Create `.env` file in project folder:
```
GEMINI_API_KEY=your_key_here
```

### 5. Run

```bash
python app.py
```

Open `http://localhost:5000` — no sign-in required, dashboard opens directly.

On first sync, a browser window opens to authenticate with Google. After that, syncing is fully automatic using the saved `token.pickle`.

---

## Project Structure

```
job-tracker/
├── app.py              # Flask app — all routes and API endpoints
├── database.py         # SQLite functions
├── email_parser.py     # Regex + Gemini AI email parsing
├── gmail_service.py    # Gmail API client
├── jobs.db             # SQLite database (auto-created on first run)
├── credentials.json    # Google OAuth credentials (you provide this)
├── token.pickle        # Gmail auth token (auto-created on first sync)
├── .env                # GEMINI_API_KEY (you create this)
├── requirements.txt
├── static/
│   └── js/dashboard.js
└── templates/
    └── index.html
```

---

## Privacy

- All data stays on your local machine
- `jobs.db` is a local SQLite file — no cloud database
- `credentials.json` and `token.pickle` are in `.gitignore` — never committed to GitHub
- Gemini API only receives email subject + body snippets for unknown titles

---

## License

MIT — free to use, modify, and share.
