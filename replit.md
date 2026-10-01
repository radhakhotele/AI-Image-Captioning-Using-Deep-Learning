# AI-Powered Image Captioning

A Streamlit and Flask application that generates, saves, and manages image
captions using Hugging Face's pretrained ViT-GPT2 model.

## Run & Operate

- `streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port 8501` — local Streamlit UI
- `python -m backend.app` — local Flask API (port 8000)
- `python -m pytest -q` — mocked API and frontend-client test suite
- Replit workflows: `Caption Studio` (port 5000) and `Caption API` (port 8000)
- Install development/test dependencies: `python -m pip install -r requirements-dev.txt`
- Install all runtime/model dependencies: `python -m pip install -r backend/requirements.txt -r frontend/requirements.txt`
- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Backend settings: `APP_ENV`, `PORT`, `DATABASE_URL`, `UPLOAD_DIR`, `MODEL_ID`, `CORS_ORIGINS`
- Frontend setting: `BACKEND_URL` (defaults to `http://127.0.0.1:8000` locally)
- Local data: `instance/captions.sqlite3` and `backend/uploads/` (both ignored by Git)

## Stack

- App: Python 3.11+, Streamlit, Flask, Flask-CORS, Requests
- AI: PyTorch and Hugging Face Transformers (`nlpconnect/vit-gpt2-image-captioning`)
- Images: Pillow; local SQLite or PostgreSQL through SQLAlchemy
- Production API server: Gunicorn
- The original pnpm/TypeScript monorepo services and shared libraries remain alongside the Python app.

## Where things live

- `backend/app.py` — Flask application factory and REST routes
- `backend/caption_generator.py` — lazy, process-wide model loading and inference
- `backend/config.py`, `backend/extensions.py`, `backend/models.py` — settings, SQLAlchemy, and persistence model
- `frontend/streamlit_app.py` — Home, caption generation, history, and About pages
- `frontend/api_client.py` — HTTP requests and user-safe API errors
- `tests/` — Flask route/storage tests and frontend client error tests
- `README.md` — local setup, API reference, GitHub instructions, and external deployment guide
- `artifacts/`, `lib/`, and `scripts/` — the pre-existing pnpm workspace scaffold

## Architecture decisions

- Inference runs only in Flask; Streamlit sends multipart requests and displays the API's actual caption.
- The pretrained model loads on the first request and is reused; inference is serialized to protect memory.
- SQLite and local image files are for development. Hosted deployments need PostgreSQL and durable image storage.
- No authentication is included; a public deployment shares one gallery and permits public upload, read, and delete operations.

## Product

Users can upload validated JPG/JPEG/PNG images, generate and copy captions, browse saved image-caption records, view original images, and delete records.

## User preferences

- Keep the app beginner-friendly and modular, use the specified Flask/Streamlit architecture, and use real pretrained inference rather than fabricated captions.
- Avoid paid AI APIs and unnecessary authentication or account-management features.

## Gotchas

- The first real caption request may download about 2 GB of checkpoint files (two ~982 MB weight formats were fetched here) and can take longer; the host needs outbound Hugging Face access and sufficient memory and disk.
- The Replit Flask workflow is for development preview; use Gunicorn for hosted production.
- Replit or other ephemeral filesystems do not preserve SQLite data or uploaded images across redeploys.
- Tests stub model inference; a successful test run does not replace a real model or live-storage check.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
- See `README.md` for provider-specific deployment steps and configuration values
