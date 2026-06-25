# Academia Sales CRM

AI-powered B2B academia sales CRM prototype with a Flask backend and SQLite database.

## Run

```powershell
pip install -r requirements.txt
python server.py
```

Open:

```text
http://127.0.0.1:5000
```

The backend creates `crm.sqlite3` automatically and seeds sample institution leads on first run.

## AI Setup

Create a `.env` file in this folder:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

When `OPENAI_API_KEY` is present, the backend uses OpenAI to generate lead score, priority, next best action, outreach message, and follow-up suggestion.

When the key or OpenAI package is missing, the app still runs with local rule-based fallback intelligence.

## API

- `GET /api/leads` - list leads with AI score, priority, next action, and outreach message
- `POST /api/leads` - create a new institution lead
- `PATCH /api/leads/<id>` - update lead fields such as status
- `POST /api/leads/<id>/advance` - move a lead to the next pipeline stage
- `GET /api/tasks` - list follow-up tasks
- `POST /api/tasks` - create a follow-up task
- `POST /api/ai-review` - rebuild follow-up tasks by AI priority
