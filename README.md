# Real Estate Portfolio Analyst

A small FastAPI and React application for asking questions about real-estate portfolio records. The rule-based assistant reads actual data from PostgreSQL, scopes portfolio answers to one selected user, supports a limited set of property changes, and labels deterministic hypothetical calculations.

## Architecture

```mermaid
flowchart TD
    Browser[React chat and operations UI] --> API[FastAPI routes]
    API --> Chat[Chat orchestration and request validation]
    Chat -->|OPENROUTER_API_KEY set| LLM[Optional LangChain OpenRouter tool selection]
    Chat -->|Key missing or request unavailable| Rules[Existing rule-based chat]
    LLM --> Tools[Allowlisted backend tools]
    API --> Tools[Database tools]
    Rules --> Tools
    Tools --> DB[(PostgreSQL)]
    Chat --> Conversation[Conversation history]
    Conversation --> DB
    Tools --> Activity[Tool activity log]
    Activity --> DB
```

Database queries and deterministic calculations belong to backend tools. When `OPENROUTER_API_KEY` is configured, LangChain's OpenAI-compatible chat model endpoint at OpenRouter selects from an allowlist of tools. Without the key, on an OpenRouter error, or when the model does not return one approved tool call, the existing rule-based chat remains available. The API key is optional and is never required for backend startup.

## Stack

- Python, FastAPI, Pydantic, SQLAlchemy
- PostgreSQL via psycopg2
- React and Vite
- Pytest and in-memory SQLite fixtures for isolated tests

## Setup

Requirements: Python 3.10+ and Node.js 18+.

### PostgreSQL

Use the existing `real_estate` database and dataset. Set a local `DATABASE_URL` in `backend/.env`, for example:

```dotenv
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/real_estate
```

OpenRouter is optional. To enable model-assisted tool selection, set `OPENROUTER_API_KEY` in the local `backend/.env`. The default model is `openai/gpt-4o-mini`; set `OPENROUTER_MODEL` there to choose a different model supported by OpenRouter. Do not commit `.env` or put credentials in source code. No OpenRouter key is needed to start the backend or use rule-based chat.

Do not commit `.env`. The checked-in `.gitignore` excludes `.env` and related files. Never run `DROP`, `TRUNCATE`, or destructive data cleanup commands against the existing database.

The admin APIs require `conversations.flagged_for_attention` and `tool_activity`. Before using them against PostgreSQL, back up the database and review `backend/migrations/001_admin_activity.sql`. It only adds a defaulted column and creates a new table; it has not been applied automatically.

### Backend

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; interactive API docs are at `/docs`.

### Frontend

```sh
cd frontend
npm install
npm run dev
```

The frontend defaults to `http://localhost:8000`. Set `VITE_API_BASE_URL` in a local frontend environment file if the backend uses a different URL.

## API Endpoints

User IDs are supplied by the caller in this assignment build. Portfolio and property reads under `/users/{user_id}` and chat operations are scoped to that ID. A production deployment needs real authentication and must derive the user identity from a verified credential.

- `GET /health/db`: database connectivity and row counts.
- `GET /users/{user_id}` and `GET /users/{user_id}/properties`: user profile and properties.
- `GET /users/{user_id}/properties/{property_id}`: owned property detail.
- `GET /users/{user_id}/portfolio/summary`, `/by-location`, `/rent`: user-scoped analytics.
- `POST /properties`: validate and add a property; returns the created property and generated ID.
- `PUT /users/{user_id}/properties/{property_id}`: update only supplied supported fields.
- `POST /chat` and `GET /conversations/{user_id}`: optional OpenRouter-assisted tool selection with rule-based fallback, and recent history.
- `GET /admin/users`, `GET /admin/conversations`, `GET /admin/conversations/{id}`: basic business inspection.
- `PATCH /admin/conversations/{id}/flag`: set or clear an attention flag.
- `GET /admin/tool-activity`: inspect recent chat tool activity.

The pre-existing global portfolio routes now require `user_id` and return user-scoped results. `/properties` likewise requires `user_id`. The old `/properties/{property_id}` route requires `user_id` and hides missing and non-owned properties behind the same not-found response.

## Actual And Hypothetical Data

Actual analytics query the selected user's saved property rows. Supported hypothetical value-change, rent, purchase, and sale questions perform in-memory arithmetic only, explicitly label the result, and do not change PostgreSQL. The hypothetical purchase total assumes the entered amount is added to current estimated portfolio value; it does not model costs, financing, or income. Missing purchase price remains unavailable; appreciation is not estimated without required inputs.

## Tests

From `backend/` after installing requirements:

```sh
pytest -q
```

Tests create a temporary in-memory SQLite database and do not connect to or modify the existing PostgreSQL database.

## AI Architecture

The optional LangChain/OpenRouter adapter interprets each request and selects at most one approved tool. Tool schemas do not accept a user ID; the backend injects the request's user ID for every read or write. Model-proposed add and update fields are validated before the existing database tools run. The model cannot run SQL or write directly to PostgreSQL. The backend formats responses from tool results, so portfolio facts and hypothetical calculations are not generated by the LLM. The rule-based chat remains the fallback when no key is set or the model is unavailable. No RAG, vector database, or multi-agent system is used.

## Engineering Decisions

- Keep SQL and deterministic calculations in `backend/app/tools.py`.
- Use Pydantic request models and field whitelisting for property writes.
- Return a not-found response for both absent and non-owned properties to avoid exposing ownership.
- Keep the existing dataset untouched; the admin schema requirement is an additive, manually reviewed migration.
- Keep user-supplied IDs for this assignment; they are not a substitute for authentication.
- Keep the initial property-add chat parser intentionally limited. It asks for missing fields rather than inventing them.

## Limitations And Security

- User IDs are not authenticated. User-scoped filtering reduces accidental cross-user data exposure but cannot stop a caller from choosing another ID. Add authentication before deployment.
- Admin APIs have no authentication/authorization and must remain private until secured.
- Rule-based natural-language parsing covers a small set of explicit English phrases and is not a general conversational model.
- Admin routes depend on the additive migration being applied manually.
- Property IDs use the existing `P###` style and are allocated by checking existing values; concurrent property creation should use a database sequence/constraint strategy in a production system.
- There is no production observability, rate limiting, or deployment-specific secret manager configuration.

## Deployment

Build the UI with `cd frontend && npm run build`. Deploy the static frontend and FastAPI service behind HTTPS. Configure `DATABASE_URL` through the hosting provider's secret store, restrict database network access, apply the reviewed additive migration after a backup, and add authentication/authorization before making user or admin routes public. Do not deploy `.env` or expose the admin endpoints on an untrusted network.