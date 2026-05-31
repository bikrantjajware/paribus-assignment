# Hospital Bulk Upload API

A Flask REST API that accepts a CSV file of hospital records, validates and persists each row via an external Hospital Directory API, then triggers a batch-activation call — all in a single `POST /hospitals/bulk` request.

---

## Features

- **Bulk CSV Upload** — `POST /hospitals/bulk` accepts a multipart CSV file and processes every row in one shot.
- **Row-level Validation** — Each row is validated with Pydantic; invalid rows are collected into a structured error list without aborting the whole batch.
- **In-Memory Store** — Successfully created hospitals are mirrored into a process-level in-memory store (`DBHospital` / `HOSPITALS` dict) for fast local reads.
- **External API Client** — A thin `HospitalAPIClient` wrapper (using `requests.Session`) communicates with the upstream Hospital Directory service for hospital creation and batch activation.
- **Batch Activation** — After all valid rows are persisted remotely, a single `PATCH /hospitals/batch/{batch_id}/activate` call activates the entire batch; the in-memory store is updated to reflect this.
- **Structured Response** — The endpoint returns a JSON summary with batch ID, counts, per-hospital statuses, processing time, and activation flag.
- **Health Check** — `GET /health` for liveness probing.

---

## Tech Stack

| Layer           | Technology                                                            |
| --------------- | --------------------------------------------------------------------- |
| Web Framework   | [Flask 3.x](https://flask.palletsprojects.com/)                       |
| Data Validation | [Pydantic v2](https://docs.pydantic.dev/latest/)                      |
| HTTP Client     | [Requests](https://requests.readthedocs.io/) (via `requests.Session`) |
| WSGI Server     | [Gunicorn](https://gunicorn.org/)                                     |
| Config          | [python-dotenv](https://pypi.org/project/python-dotenv/)              |
| Runtime         | Python 3.12+                                                          |

---

## Design Decisions

### Separation of Concerns (layered architecture)

`routes.py` it only handles HTTP requests (file presence, content-type guard, error-to-status mapping). All business logic lives in `services/hospital_service.py`, making the service testable in isolation without spinning up a Flask test client.

### Pydantic v2 for validation

Pydantic's `model_validate` checks each CSV row, automatically converts values, shows clear errors, and keeps the data format defined in one place.

### Partial-failure model

Invalid CSV rows are collected into a `RowError` and skipped, allowing all valid rows to be processed without stopping the request.

### `requests.Session` for the API client

Using a shared `Session` object enables HTTP keep-alive connection pooling across multiple rows in a single batch, reducing TCP overhead compared to individual `requests.get/post` calls.

### Flask Application Factory

`create_app()` follows the Flask application factory pattern, which makes it straightforward to instantiate the app with different configs (e.g., test vs. production) and avoids circular import issues.

### Batch activation as a single call

Rather than activating each hospital individually after creation, all hospitals in a batch are activated with a single `PATCH /hospitals/batch/{batch_id}/activate` call. This reduces the number of external HTTP round-trips from `O(n)` to `O(1)` relative to the number of rows.

---

## Project Structure

```
paribus-assignment/
├── app/
│   ├── __init__.py              # App factory (create_app), blueprint registration
│   ├── extensions.py            # Singleton HospitalAPIClient instance
│   ├── hospital_api_client.py   # External API client (create, activate, CRUD)
│   ├── db.py                    # In-memory store — DBHospital model + HOSPITALS dict
│   ├── schemas.py               # Pydantic schemas (HospitalRow, BulkUploadResponse, …)
│   ├── routes.py                # Blueprint — request/response layer only
│   ├── services/
│   │   ├── __init__.py
│   │   └── hospital_service.py  # Business logic: orchestrates parse → persist → activate
│   └── utils/
│       ├── file_utils.py        # Generic CSV parsing + Pydantic row validation
│       └── hospital_utils.py    # Hospital-specific helpers (wraps client + DB write)
├── requirements.txt
├── .env                         # Environment variables (see Setup)
└── README.md
```

### Layer Responsibilities

```
routes.py          →  HTTP boundary (request parsing, error → HTTP status mapping)
services/          →  Use-case orchestration (parse CSV → create hospitals → activate batch)
utils/             →  Reusable helpers (CSV parsing, external API ↔ local DB bridge)
hospital_api_client.py  →  External HTTP calls (single responsibility)
db.py              →  In-memory persistence model
schemas.py         →  Shared data contracts (input + output)
```

---

## Setup — Run Locally

### Prerequisites

- Python 3.11+
- `pip` (or `pip3`)

### 1. Clone & create a virtual environment

```bash
git clone <repo-url>
cd paribus-assignment

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example below into a `.env` file at the project root:

```env
HOSPITAL_API_BASE_URL=https://hospital-directory.onrender.com
```

| Variable                | Description                                     |
| ----------------------- | ----------------------------------------------- |
| `HOSPITAL_API_BASE_URL` | Base URL of the upstream Hospital Directory API |

### 4. Run the development server

```bash
python -m flask run
```

The API will be available at `http://127.0.0.1:5000`.

### 5. (Optional) Run with Gunicorn

```bash
gunicorn app:app -b 0.0.0.0:8080 -w 2
```

---

## API Reference

### `POST /hospitals/bulk`

Upload a CSV file to bulk-create and activate hospitals.

**Request** — multipart/form-data

| Field  | Type        | Required | Description                                                  |
| ------ | ----------- | -------- | ------------------------------------------------------------ |
| `file` | `.csv` file | ✅       | CSV with columns `name`, `address`, `phone` (phone optional) |

**CSV format**

```csv
name,address,phone
appolo,blr street a,123
ruby hospital,em by pass road,122
```

**Success Response** — `200 OK`

```json
{
  "batch_activated": true,
  "batch_id": "1a83c86e-0b29-41a0-8a4b-5444929d6906",
  "failed_hospitals": 1,
  "hospitals": [
    {
      "hospital_id": 26,
      "name": "appolo",
      "row": 1,
      "status": "created"
    },
    {
      "hospital_id": 27,
      "name": "ruby hospital",
      "row": 3,
      "status": "created"
    }
  ],
  "processed_hospitals": 2,
  "processing_time_seconds": 11,
  "total_hospitals": 3
}
```

**Error Responses**

| Status | Cause                                          |
| ------ | ---------------------------------------------- |
| `400`  | Missing file, empty CSV, or no valid data rows |
| `415`  | Uploaded file is not a CSV                     |
| `500`  | Upstream API or persistence failure            |

### `GET /health`

Liveness check — returns `{"status": "ok"}` with `200 OK`.

---

## Future Improvements

- **Unit & integration tests** — Add a `pytest` test suite covering:
  - `parse_csv_upload` with valid/invalid/empty CSVs
  - `process_bulk_upload` with mocked `hospital_utils` calls
  - Route-level tests using Flask's test client
  - `HospitalAPIClient` with `responses` or `httpretty` for HTTP mocking

- **Dockerize the application** — Add a `Dockerfile` and `docker-compose.yml` so the service (and a mock upstream) can be spun up with a single command:

  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8080", "-w", "2"]
  ```

- **Persistent database** — Replace the in-memory `HOSPITALS` dict with SQLAlchemy + PostgreSQL/SQLite so data survives process restarts.

- **Async / concurrent processing** — Use `asyncio` + `aiohttp` (or a task queue like Celery) to fire external API calls concurrently instead of sequentially, significantly reducing total processing time for large batches.

- **Pagination & querying** — Expose `GET /hospitals` with cursor-based pagination and filters (by batch, status, name).

- **Authentication & rate limiting** — Add API-key or JWT authentication and per-client rate limiting via Flask-Limiter.

- **OpenAPI / Swagger docs** — Auto-generate API documentation from the Pydantic schemas using `flask-openapi3` or `apiflask`.
