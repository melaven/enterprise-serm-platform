# Laurent Nexus SERM Engine

A full-stack review intelligence platform that combines a FastAPI backend, a React + Vite frontend, and a reusable embeddable review widget built with Shadow DOM isolation.

The project is designed to collect and analyze customer reviews, surface sentiment and quality signals, and render a widget that can be inserted into external websites without breaking the host site's CSS or layout.

## Project overview

### Backend
- FastAPI application with modular routers
- Clean Architecture-inspired structure
- Review ingestion endpoints and widget data endpoints
- SQLite fallback for local development
- CORS-ready for frontend integration

### Frontend
- React + TypeScript + Vite
- Dark-mode dashboard and settings UI
- Review analytics and widget builder interface
- Embedded script generation for customer-facing widgets

### Widget delivery
- Universal script injection approach
- Shadow DOM isolation for CSS safety
- API-based widget payload generation
- Support for tenant-specific embedding via `data-tenant-id`

## Repository structure

```text
Laurent Nexus Operation backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── reviews.py
│   │       │   ├── widgets.py
│   │       │   └── tenants.py
│   │       └── router.py
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   │   └── review.py
│   ├── schemas/
│   │   ├── reviews.py
│   │   └── widget.py
│   ├── services/
│   │   └── review_service.py
│   ├── app/
│   │   └── routers/
│   └── __init__.py
├── frontend/
│   ├── src/
│   └── package.json
├── static/
│   └── widget.js
├── .env
├── .gitignore
├── main.py
├── README.md
├── resiliency.py
└── index.html
```

## Tech stack

- Python 3.11+
- FastAPI
- SQLAlchemy
- Pydantic v2
- Uvicorn
- React
- Vite
- TypeScript
- Tailwind CSS
- Shadow DOM

## Local development

### 1. Backend

From the project root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

The backend is available at:
- http://127.0.0.1:8000
- Swagger docs: http://127.0.0.1:8000/docs

### 2. Frontend

From the frontend folder:

```bash
npm install
npm run dev -- --host 0.0.0.0
```

The frontend is available at:
- http://localhost:5173

## Widget embed example

```html
<script src="http://localhost:8000/api/v1/widgets/script.js" data-tenant-id="DEMO_TENANT" async></script>
<div id="nexus-widget"></div>
```

The widget script loads review data from the backend, renders a Shadow DOM component, and keeps the host page's styles isolated.

## API highlights

### Reviews
- `GET /api/v1/reviews`
- `POST /api/v1/reviews/webhook`

### Widgets
- `GET /api/v1/widgets/preview`
- `GET /api/v1/widgets/script.js`
- `GET /api/v1/widgets/embed-data?tenant_id=...`

## Goals

This project is intended to demonstrate a production-minded architecture for an AI-powered SERM and review automation platform:
- clean separation of concerns
- embeddable review widgets
- monitoring-friendly backend services
- modern frontend builder workflow
- secure local development configuration

## License

This project is for internal product and prototype use unless explicitly assigned a different license by the project owner.
