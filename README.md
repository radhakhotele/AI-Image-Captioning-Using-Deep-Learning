# AI-Powered Image Captioning

A Python image-captioning application with a Streamlit interface, a modular
Flask REST API, and real inference from Hugging Face's pretrained
`nlpconnect/vit-gpt2-image-captioning` model. Upload a JPG, JPEG, or PNG to
generate a caption, save it with the image, browse your history, and delete
records you no longer need.

## Features

- Generates captions through a pretrained Vision Transformer + GPT-2 model.
- Keeps model inference in the Flask backend; the frontend never invents captions.
- Validates image contents, file type, upload size, and image dimensions.
- Stores re-encoded images under unique names and saves metadata in SQLAlchemy.
- Uses SQLite for local development and supports PostgreSQL through `DATABASE_URL`.
- Provides history, image details, safe image retrieval, and deletion endpoints.
- Includes connection/timeout handling, API tests with mocked model inference, and
  deployment setup for Streamlit Community Cloud and Render-compatible hosts.

## Technology and architecture

```text
Browser
  └── Streamlit (frontend/streamlit_app.py)
        └── Requests → Flask REST API (backend/app.py)
                         ├── SQLAlchemy → SQLite or PostgreSQL
                         ├── Pillow → validates and normalizes image files
                         └── Transformers + PyTorch → ViT-GPT2 inference
```

The model is loaded lazily on the first caption request, then reused by the
backend process. Inference is serialized per process to avoid duplicate model
loads and overlapping memory-heavy work. CPU inference is supported; CUDA is
used automatically if available.

## Project structure

```text
.
├── backend/                 Flask API, model inference, database and uploads
├── frontend/                Streamlit interface and API client
├── tests/                   API and frontend-client tests
├── artifacts/
│   ├── api-server/           Replit-managed API workspace artifact
│   └── mockup-sandbox/       Canvas/component-preview source
├── lib/
│   ├── api-client-react/     Shared TypeScript client
│   ├── api-spec/             OpenAPI source and generator config
│   ├── api-zod/              Shared API schemas
│   └── db/                   Shared database package/schema
├── scripts/                  Workspace maintenance scripts
├── .streamlit/config.toml    Streamlit theme
├── .env.example              Safe configuration template
├── requirements.txt          Streamlit Community Cloud entry point
├── requirements-dev.txt      Lightweight test dependencies
├── package.json              Root Node workspace metadata
├── pnpm-lock.yaml            Node dependency lockfile
└── pnpm-workspace.yaml       Node workspace package list
```

The Python captioning application runs from `backend/` and `frontend/`. The
`artifacts/`, `lib/`, and Node workspace files are retained as tracked Replit
workspace source; they are not required to run the Python captioning application.

## Screenshots

No screenshot files are currently included. After capturing the running app,
place screenshots in `docs/screenshots/` and add relative Markdown image links
here. Suggested captures:

```text
docs/screenshots/home.png
docs/screenshots/generate-caption.png
docs/screenshots/caption-history.png
```

## Run locally

Use Python 3.11, the version used by this Replit workspace. After the GitHub
repository has been created, clone it, create a virtual environment, install the
backend and frontend dependencies, and copy the example configuration:

```bash
git clone https://github.com/<your-account>/AI-Image-Captioning.git
cd AI-Image-Captioning
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r backend/requirements.txt -r frontend/requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Start the API and frontend in separate terminals from the repository root:

```bash
python -m backend.app
```

```bash
streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

The API defaults to `http://127.0.0.1:8000`; the UI defaults to that backend URL.
Visit the URL printed by Streamlit (normally `http://localhost:8501`). The
backend creates its SQLite database in `instance/captions.sqlite3` and stores
normalized uploads in `backend/uploads/`.

The first successful caption request downloads the model checkpoint. In this
environment, the model repository supplied two weight formats of about 982 MB
each, so allow roughly 2 GB for a cold download/cache, plus enough memory to
load the model. It can take several minutes and requires outbound access to
Hugging Face. Subsequent requests reuse the in-memory model.

### Replit run configuration

The project is configured with two workflows:

- **Caption Studio** — runs Streamlit on port `5000` for the preview.
- **Caption API** — runs Flask on port `8000` in the background.

For this local preview the Streamlit server makes HTTP requests to
`http://127.0.0.1:8000`; in hosted deployments, set `BACKEND_URL` to the Flask
service's public API origin.

## Configuration

Copy `.env.example` to `.env` for local development. Important settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Selects development or production settings |
| `PORT` | `8000` | Flask listen port |
| `DATABASE_URL` | Local SQLite file | SQLAlchemy database URL; PostgreSQL URLs are normalized for Psycopg 3 |
| `UPLOAD_DIR` | `backend/uploads` | Directory for normalized image files |
| `MAX_CONTENT_LENGTH` | `10485760` | Maximum upload size in bytes (10 MiB) |
| `MAX_IMAGE_PIXELS` | `25000000` | Maximum decoded pixel count |
| `MODEL_ID` | `nlpconnect/vit-gpt2-image-captioning` | Hugging Face model checkpoint |
| `CORS_ORIGINS` | Local Streamlit origins | Comma-separated allowed browser origins |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Flask API base URL used by Streamlit |

The Streamlit frontend also reads `BACKEND_URL` from Streamlit Community Cloud's
Secrets. Set environment variables through the hosting provider's settings
instead of committing real `.env` files or credentials.

## REST API

Successful responses use `{"success": true, "data": ...}`. Errors use
`{"success": false, "error": {"code": "...", "message": "..."}}`.

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Backend and database readiness |
| `POST` | `/api/caption` | Multipart image upload; use the field name `image` |
| `GET` | `/api/images` | All saved caption records, newest first |
| `GET` | `/api/images/<id>` | One saved caption record |
| `GET` | `/api/images/<id>/file` | The normalized image for a record |
| `DELETE` | `/api/images/<id>` | Delete the record and stored image |

`POST /api/caption` accepts `multipart/form-data` with an `image` field and
returns HTTP `201` with the saved record. Missing or invalid images return
`400`, oversized uploads return `413`, model failures return `503`, and storage
failures return `500`.

Example health check and upload:

```bash
curl http://127.0.0.1:8000/api/health

curl -X POST http://127.0.0.1:8000/api/caption \
  -F "image=@sample.jpg"
```

Caption records include an `id`, safe stored `filename`, sanitized
`original_filename`, generated `caption`, timestamps, and `image_url`. Use
`GET /api/images` for newest-first history, `GET /api/images/<id>` for one
record, and `DELETE /api/images/<id>` to delete a record and its stored image.
Successful requests to `/api/images/<id>/file` return image bytes with an
`image/jpeg` or `image/png` content type, not the JSON response envelope.

The API validates the decoded Pillow format rather than trusting the browser's
MIME type. It rejects mismatched extensions, unsupported or corrupt files,
oversized bodies, and images above the configured pixel limit. Stored filenames
are generated by the server; original client filenames are sanitized. Image
paths are not returned by the API.

## AI model

The default checkpoint, `nlpconnect/vit-gpt2-image-captioning`, combines a
Vision Transformer encoder and GPT-2 decoder. Hugging Face Transformers downloads
the model on the first inference and caches the files in the normal Hugging Face
cache (or the directory selected by `HF_HOME`). No paid AI API or model training
is required.

Inference uses CPU by default and automatically selects a CUDA GPU when PyTorch
can access one. The checkpoint is substantial, so allow enough disk and RAM for
model loading. CPU requests can be slow. Captions can be inaccurate or omit
context; review the model/checkpoint license and usage conditions before
redistributing model weights or presenting captions as authoritative.

## Tests

The test suite replaces model inference with a predictable stub, so running it
does not download the checkpoint:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests cover health checks, upload validation, record creation and retrieval,
safe image serving, deletion, missing records, model failure, multipart API
requests, HTTP errors, unavailable-backend behavior, and timeouts. A successful
mocked test run does not prove that Hugging Face can be reached or that a real
caption can be generated on a particular host.

## Publish to GitHub

Create an empty repository named `AI-Image-Captioning` in your GitHub account
and choose its visibility. Do not initialize it with a separate README, license,
or `.gitignore`; this project already has those files and a local Git history.

To publish manually from this workspace, add GitHub as a separate remote so the
existing Replit backup remote remains unchanged:

```bash
git status --short
git add -A
git commit -m "Prepare AI image captioning project for GitHub"
git remote add github https://github.com/<your-account>/AI-Image-Captioning.git
git push -u github main
```

Replace `<your-account>` with your GitHub username or organization. If a `github`
remote already exists, use `git remote set-url github
https://github.com/<your-account>/AI-Image-Captioning.git` instead. Review the
staged file list before committing or pushing.

## Deployment

Deploy the Flask API and Streamlit UI as separate services. No services or public
URLs have been created from this project.

### 1. Deploy the Flask API on Render or a compatible Python host

1. Connect the GitHub repository in the provider dashboard.
2. Set the service's root directory to the directory containing this README.
3. Set the build command to:

   ```bash
   pip install -r backend/requirements.txt
   ```

4. Set the start command to:

   ```bash
   gunicorn --workers 1 --threads 2 --timeout 240 --bind 0.0.0.0:$PORT backend.app:app
   ```

5. Configure these environment values in the service dashboard:
   - `APP_ENV=production`
   - `MODEL_ID=nlpconnect/vit-gpt2-image-captioning`
   - `DATABASE_URL` to the provider's PostgreSQL connection URL.
   - `UPLOAD_DIR` to a persistent mounted directory, for example
     `/var/data/uploads`, after adding a persistent disk.
   - `CORS_ORIGINS` to the exact Streamlit app origin once it is known.
6. Provision PostgreSQL and persistent image storage in the hosting account.
   Do not rely on the service's temporary filesystem for user images or SQLite.
   Persistent disks and managed databases may require a paid hosting plan.
7. Deploy and check `https://<your-backend-host>/api/health`. Confirm it reports
   both the API and database as connected. Replace the placeholder with the URL
   assigned by your provider; no URL is assumed here.
8. Send a test image to `/api/caption` and verify that `/api/images` and the
   returned `/api/images/<id>/file` work before connecting the UI.

### 2. Deploy Streamlit Community Cloud

1. Create a new Streamlit app and connect the same GitHub repository.
2. Set the main file to `frontend/streamlit_app.py`.
3. Streamlit installs frontend packages from the root `requirements.txt`, which
   includes `frontend/requirements.txt`.
4. In the app's Secrets settings, add the API URL assigned to the Flask service:

   ```toml
   BACKEND_URL = "https://<your-backend-host>"
   ```

5. Deploy, open the Streamlit app, and check the service status on the Home page.
6. On the Flask host, update `CORS_ORIGINS` to the exact Streamlit app origin.
   The current frontend uses server-side Requests; CORS is configured for
   allowed browser origins and is not an access-control or authentication layer.
7. Test the full live flow: upload a JPG/PNG, generate a caption, confirm the
   image and caption appear in history, open the saved image, delete the record,
   and confirm it disappears from history and storage.

### Storage, resource, and privacy limits

- SQLite and the local uploads folder are appropriate for local development,
  not for a hosted instance with ephemeral storage.
- Use hosted PostgreSQL and durable image storage before inviting others to use
  the deployed app. The current implementation stores files on the configured
  filesystem; a persistent disk is the straightforward Render-compatible
  option. Object storage would require an additional storage adapter.
- A model-backed service needs adequate memory and disk for the checkpoint.
  The first request includes model-download and load time. Choose a host that
  supports outbound Hugging Face downloads and the required memory; verify its
  limits before deploying.
- The demo has no login or per-user authorization. Anyone who can reach a public
  deployment can upload, read, and delete its shared records. Do not store
  sensitive images on a public deployment without adding access controls.

## Known limitations and next steps

- There is no authentication, per-user gallery, rate limiting, or object-storage
  adapter.
- Model inference is intentionally serialized within one process; scaling to
  multiple workers duplicates model memory.
- Image records use automatic table creation for simple local setup. A larger
  production application should add an explicit database migration workflow.
- Captions are machine-generated descriptions and should be reviewed for
  accuracy.

Possible extensions include optional user accounts, pagination, object storage,
model benchmarking, configurable caption length, and database migrations.