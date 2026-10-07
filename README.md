# Tenable SI SERM & Reputation Engine

FastAPI backend for collecting customer reviews and recording review sentiment as part of Tenable's SI SERM and reputation platform.

## Project structure

```text
.
├── app/
│   ├── app/
│   │   ├── routers/
│   │   │   └── reviews.py
│   │   ├── schemas/
│   │   │   ├── reviews.py
│   │   │   └── app/
│   │   │       └── services/llm.py
│   │   └── services/
│   │       └── llm.py
│   └── database.py
├── .env.example
├── main.py
├── requirements.txt
└── resiliency.py
```

## Local development

Create and activate a virtual environment, install dependencies, then create a local `.env` from the example:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the connection and API values in `.env`, then run the backend:

```powershell
python -m uvicorn main:app --reload --port 8000
```

The API is available at `http://127.0.0.1:8000`; interactive documentation is at `http://127.0.0.1:8000/docs`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy async database connection URL |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase API key used by the backend |
| `OPENAI_API_KEY` | API key for the review-response service |
| `OPENAI_MODEL` | Optional response model; defaults to `gpt-4o-mini` |

Keep real credentials in `.env`; it is excluded from Git.

## API

- `GET /health` — service health check
- `POST /api/v1/reviews/webhook` — validate and save a review
