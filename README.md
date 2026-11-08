# Olist Text-to-SQL

A standalone FastAPI backend for the Olist tables already imported into your `olist` database.
It authenticates a development bearer token, retrieves only approved schema metadata, generates
SQL, validates it with SQLGlot, queries PostgreSQL through a restricted role, and returns rows,
SQL evidence, a deterministic answer, and a server-generated request ID.

**Default:** deterministic placeholder; no model key or paid API calls required.
**Optional:** API LLM generation using a Chat Completions endpoint supporting JSON mode.
Both modes use the same security checks. The endpoint does not accept raw SQL or caller-supplied roles.

The implementation and test evidence were produced in a Linux Python 3.12 environment.
The macOS commands below have not been executed on your laptop. Live PostgreSQL checks are
included but were not runnable in the build environment; see `docs/VERIFICATION.md`.

## 1. Extract and select an existing compatible Python

Unzip `olist-sql-rag.zip`. You can place the extracted `olist-sql-rag` folder alongside
your existing `SQL_RAG/archive` folder; do not move or re-import your CSVs.

For example, after extracting into Downloads:

```bash
cd ~/Downloads/olist-sql-rag
python3 --version
```

Use an existing **Python 3.11–3.14** installation. If compatible:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Only if you do not already have a compatible Python, the Apple Silicon Homebrew alternative is:

```bash
brew install python@3.12
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

`pyproject.toml` pins direct dependencies to the tested versions. `requirements.lock` records
the full build environment dependency set, including development and optional Uvicorn packages.
For that full pinned set, use `python -m pip install -r requirements.lock` before installing editable
with `python -m pip install -e . --no-deps`. The lock was resolved on Linux/Python 3.12;
Apple Silicon wheel availability has not been verified here.

## 2. Confirm the existing PostgreSQL server

Run in the Mac terminal, **not inside `psql`**:

```bash
psql -U saianish -d olist -c 'SHOW server_version;'
```

This service requires **PostgreSQL 16** and fails startup on a different major version.
If `psql` works only with a host/port/password in your installation, add those options consistently
to the setup commands and edit the generated connection URLs accordingly.

Your existing running PostgreSQL installation may already be sufficient. Do not install/start a
second server on the same port. For a new Apple Silicon Homebrew installation only:

```bash
brew install postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
brew services start postgresql@16
```

If an existing cluster uses another major version, back it up and plan a PostgreSQL-supported
upgrade or restore into a separate PG16 cluster; installing another version does not migrate it.
These scripts assume the `olist` database and tables are owned by `saianish`, as in your output,
and that this administrator can create roles. No administrator credentials are stored in the API.

## 3. Generate configuration

From the project root with `.venv` activated:

```bash
python scripts/init_env.py
```

This creates a private `.env` file with distinct random bearer tokens and random database role
passwords. It refuses to overwrite an existing file. Keep `.env` private and out of git.
The defaults use `127.0.0.1:5432/olist`. Edit `.env` if your PostgreSQL uses another port.
Database URL passwords must be URL-encoded if you replace the generated hexadecimal passwords.

## 4. Add the approved views and restricted roles to your existing data

Your nine tables already exist, so **skip `001_schema.sql` and `002_seed.sql` for `olist`**.
Run these commands from the extracted project root:

```bash
psql -U saianish -d olist -v ON_ERROR_STOP=1 -f db/003_views.sql
psql -U saianish -d olist -v ON_ERROR_STOP=1 -f db/004_roles.sql
python scripts/provision_passwords.py --admin-url 'postgresql:///olist?user=saianish'
python -m scripts.check_database
```

For a password-authenticated administrator over TCP, use
`--admin-url 'postgresql://saianish@127.0.0.1:5432/olist'` and a private `.pgpass` entry or
`PGPASSWORD` for the setup process. Never use the administrator URL as an API connection URL.

`003_views.sql` adds an `analytics` schema and five approved views. It reads the existing data;
it does not copy or change your imported rows. `004_roles.sql` creates/grants the two dedicated
cluster-wide roles. It revokes database TEMP access and public-schema CREATE from `PUBLIC`;
review that effect if other applications share this database. It does not drop your tables.
It deliberately does not remove an existing PUBLIC base-table SELECT grant: startup rejects such
an unexpected effective grant, so an administrator can review and correct it explicitly.

For a **new empty database**, run `db/001_schema.sql` before the view and role scripts, then
import your CSVs separately using the `\copy` commands from your earlier setup. The seed is
only for the test database below. Existing tables with a different layout need a reviewed migration;
`CREATE TABLE IF NOT EXISTS` does not repair their definitions.

Optional manual permission display (use the matching password from your private `.env`):

```bash
psql -h 127.0.0.1 -U sql_rag_sales -d olist -W -f db/005_verify_permissions.sql
psql -h 127.0.0.1 -U sql_rag_analyst -d olist -W -f db/005_verify_permissions.sql
```

## 5. Start the API

Keep the working directory at the project root so `.env` can be loaded:

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/docs>. Click **Authorize** and enter the generated `SALES_TOKEN`
or `ANALYST_TOKEN` value from `.env` without the `Bearer ` prefix. Swagger adds the prefix.
Do not use the literal string `development-token`; configured tokens must be at least 32 characters.

Or run in a second terminal:

```bash
cd ~/Downloads/olist-sql-rag
source .venv/bin/activate
python scripts/query_example.py 'Show the top 5 products by revenue'
python scripts/query_example.py 'monthly revenue'
python scripts/query_example.py 'average review score' --role analyst
```

The helper reads the appropriate token from `.env`, sends the HTTP request, and prints the response.

Placeholder questions are deliberately limited:

| Question | Required policy | Meaning |
|---|---|---|
| `Show the top 5 products by revenue` | sales or analyst | Top 1–100 product IDs; delivered item prices, excluding freight |
| `Show monthly revenue` | sales or analyst | Delivered item revenue grouped by purchase month |
| `How many orders are there?` | sales or analyst | All order statuses |
| `Show orders by status` | sales or analyst | Order counts by status |
| `What is the average review score?` | analyst | Mean over review records |

Limited phrasing variants are listed in `docs/API.md`. Extra filters such as “in 2018” return an
unsupported-question error in placeholder mode, rather than silently returning an unfiltered result.

## 6. Enable API LLM generation

First get the placeholder working. Then edit these entries in your private `.env`:

```dotenv
GENERATOR_MODE=api
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=YOUR_COMPATIBLE_MODEL_ID
LLM_API_KEY=YOUR_API_KEY
```

Use a model that supports Chat Completions, `response_format: json_object`, and
`max_completion_tokens`. The adapter uses `httpx` so it does not require a vendor SDK.
The model ID is explicit; this project does not assume which models your account can access.
Restart Uvicorn after configuration changes.

API mode sends the question and **authorized schema metadata** to the configured provider.
It sends no database passwords, bearer tokens, or result rows. The returned answer is built locally
from executed results. There is no automatic fallback, automatic SQL repair, or hidden retry loop.
Live provider access was not tested without your API key; provider behavior is covered by mocked tests.

## 7. Run tests

```bash
python -m pytest -m 'not integration' -q
ruff check app scripts tests
python -m pip check
```

For database integration tests, create a **separate** fixture database. Use the same local cluster
so it has the same dedicated roles/passwords as your configured service:

```bash
createdb -U saianish olist_test
psql -U saianish -d olist_test -v ON_ERROR_STOP=1 -f db/001_schema.sql
psql -U saianish -d olist_test -v ON_ERROR_STOP=1 -f db/002_seed.sql
psql -U saianish -d olist_test -v ON_ERROR_STOP=1 -f db/003_views.sql
psql -U saianish -d olist_test -v ON_ERROR_STOP=1 -f db/004_roles.sql
python scripts/provision_passwords.py --admin-url 'postgresql:///olist_test?user=saianish'
python scripts/run_integration.py
```

The seed refuses any database except `olist_test` and refuses populated fixture tables.
The integration tests do not seed, truncate, or drop data automatically. They require exactly
the documented fixture, use the real SQLAlchemy/psycopg execution path and PostgreSQL 16,
and fail if configured against another database name. A raw `pytest` invocation skips these
tests unless both `TEST_SALES_DATABASE_URL` and `TEST_ANALYST_DATABASE_URL` are set.
Do not treat skipped tests as passed tests.

## 8. Later: offline generation and document RAG integration

`Generator.generate(question, authorized_schema, row_limit) -> Candidate` is the replacement
boundary. A compatible local inference server can use the current API adapter with a loopback URL:

```dotenv
GENERATOR_MODE=api
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_ALLOW_LOCAL_HTTP=true
LLM_MODEL=YOUR_LOCAL_MODEL
LLM_API_KEY=local-only
```

This is a configuration pattern, not a claim that a particular local server/model was tested.
Check JSON mode and token-parameter compatibility or implement a separate `Generator` adapter.
For direct local inference, add a generator class that loads your selected model. Keep schema
filtering, AST validation, authorization, restricted execution, and answer generation unchanged.

Your PDF/DOCX/TXT RAG can later route structured analytics questions to this endpoint and document
questions to your existing retrieval chain. Keep database evidence and document citations distinct;
retrieved document instructions must never alter SQL permissions or bypass the validator. Shared
authentication should issue/resolve trusted scopes server-side rather than accepting a role in JSON.

See `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/API.md`, and `docs/VERIFICATION.md`.

## Troubleshooting

| Symptom | Action |
|---|---|
| `Startup checks failed` | Run `python -m scripts.check_database`; confirm PG16, both passwords, view schemas and effective privileges |
| `psql: command not found` | Add your PostgreSQL installation's `bin` directory to PATH |
| Password authentication fails | Check localhost/port in `.env`, run password provisioning, and check local `pg_hba.conf` authentication |
| Permission denied running setup | Use the data owner/admin for setup; restricted API logins cannot provision objects |
| HTTP 401 | Use a configured `.env` bearer token, not a database password |
| HTTP 403 for reviews | Use the analyst token |
| HTTP 422 unsupported question | Use a supported placeholder phrase or enable the API adapter |
| HTTP 422 SQL rejected in API mode | The model used unsupported SQL; inspect the policy and rephrase. Rejected SQL is not executed |
| HTTP 504 | Query exceeded its timeout. Review the workload and plan before increasing budgets |
| HTTP 502 generator unavailable | Check provider credentials/model capabilities; provider error bodies are intentionally hidden |
| Empty table response | Check the original imports; the service reads live data and does not import CSVs |

Use request IDs to correlate safe audit records. Never enable SQLAlchemy SQL echo in a shared deployment.
