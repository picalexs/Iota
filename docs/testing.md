# Testing

Run checks from a clean checkout. Do not use a local `.env`, Docker volume,
database, or credential file as test input.

## Frontend

```sh
npm --prefix frontend ci
npm --prefix frontend run check:generated-types
npm --prefix frontend run lint
npm --prefix frontend run test:run
npm --prefix frontend run build
```

## Backend and worker

Install the locked requirements in a virtual environment, then run:

```sh
python3 -m compileall backend worker shared scripts/contracts
ruff check --select E4,E7,E9,F,I backend worker shared scripts/contracts
PYTHONPATH=.:backend .venv/bin/pytest backend/tests -q
PYTHONPATH=. .venv/bin/pytest worker/tests -q
```

The backend and worker suites use different import roots. Keep the two test
commands separate.

## Compose smoke check

Validate the Compose model before starting services:

```sh
docker compose config --quiet
```

For a local smoke run, copy `.env.example` to `.env`, keep `HOST_BIND` set to
`127.0.0.1`, and start the stack:

```sh
docker compose up --build -d
curl --fail http://127.0.0.1:5173
curl --fail http://127.0.0.1:18000/api/health
docker compose down
```

Do not run real IBM Runtime jobs as part of the standard test gate.

## Evidence rules

- Record timeouts as unverified.
- Keep local simulator and IBM Runtime results separate.
- Do not commit test output, coverage files, logs, database files, or Docker
  volumes.
