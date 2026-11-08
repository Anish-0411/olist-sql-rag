# Final verification report

Date: 2026-10-28. Results refer to the final acceptance run, not intermediate development runs.

## Outcome

The complete implementation, SQL scripts, API/architecture/security documentation and tests are
included. The deterministic placeholder and API adapter both pass their Python-level tests.
The project built and installed successfully as an editable package in the build environment.
Live PostgreSQL integration and a real provider call remain unverified; this report does not
claim the service has connected to your Mac or executed against your imported Olist dataset.

## Environment and changes

- Build host: Linux x86_64, Python 3.12.14, existing compatible installation.
- Project created from an empty task workspace. No existing project source files were modified.
- Your laptop, Olist rows and existing DOCX/PDF/TXT RAG project were not accessed or changed.
- Development packages were installed into an isolated `.venv` outside the delivered source folder.
- PostgreSQL was not available. Local installation attempts could not provision a usable server
  under the build host's process/filesystem restrictions. No usable PostgreSQL instance was created.
- Database objects created in this environment: **none**. All database DDL is supplied as scripts
  for you to execute locally; script existence is not evidence that it has been executed.
- External model calls made: **none**. No user/provider API key was available.
- The ZIP excludes virtual environments, credentials, CSV files, bytecode, caches and build metadata.

## Dependencies installed

| Package | Installed version |
|---|---|
| fastapi | 0.162.0 |
| uvicorn | 0.54.0 |
| pydantic | 2.14.1 |
| pydantic-settings | 2.16.1 |
| SQLAlchemy | 2.1.6 |
| psycopg | 3.3.6 |
| psycopg-binary | 3.3.6 |
| sqlglot | 30.25.0 |
| pytest | 9.2.0 |
| httpx | 0.28.1 |
| ruff | 0.17.3 |

`requirements.lock` records the complete resolved package set, including transitive dependencies
and optional Uvicorn packages installed for testing. `pyproject.toml` pins direct requirements.
Build isolation also installed setuptools for the editable build; that isolated build dependency
is not part of the running service. Application version: olist-sql-rag 0.1.0.

## Tests and checks actually executed

| Check | Result |
|---|---|
| pytest collected test cases | 174 |
| Passed | 159 |
| Failed | 0 |
| Collection/runtime errors in final run | 0 |
| Skipped | 15 |
| Warnings | 1: Starlette deprecates its current httpx TestClient integration in favor of httpx2 |
| `ruff check app scripts tests` | Passed |
| `python -m compileall -q app scripts tests` | Passed |
| `python -m pip check` | Passed; no broken requirements |
| Editable wheel build/install | Passed via pip install -e './olist-sql-rag[dev]' --no-deps |
| OpenAPI schema generation | Passed; snapshot in docs/openapi.json |
| Real PostgreSQL execution | Not executed |
| Real provider generation | Not executed; HTTP provider behavior tested using httpx.MockTransport |
| Native macOS Apple Silicon setup | Commands documented; not executed on a Mac |

Evidence: `reports/test-results.xml`, `reports/pytest-output.txt`, `reports/ruff-output.txt`,
`reports/dependency-check.txt`. The pytest run reports 0.703 seconds.

Passing tests cover authentication before validation, scope filtering, request/response handling,
truncation, safe failures/audit fields, startup refusal with resource cleanup, generator contracts,
provider failure modes, SQL rejection/acceptance/limit cases, normalization, and database driver
error mapping. The passing HTTP end-to-end tests use an explicitly named **FakeDatabase**;
they prove orchestration, not PostgreSQL SQL semantics or grants.

All 15 skipped cases are in `tests/test_postgres_integration.py`. Their fixture skips
when both TEST_*_DATABASE_URL values are absent; no SQLite replacement is used. They require a
separate seeded PostgreSQL 16 database named `olist_test` and cover:

- Real version/role/metadata verification.
- Top-product revenue excluding canceled orders and freight.
- Purchase-month revenue, total orders, status counts and review-record average.
- Real row-limit lookahead/truncation.
- Six direct database denials: base customer/review reads, unauthorized review view, updates,
  temporary table creation and analytics table creation.
- Statement timeout and full HTTP-to-PostgreSQL execution.

These checks must be run locally before calling the deployment verified. If URLs are provided
but provisioning/schema/version is wrong, the integration tests fail rather than silently skip.

## Database objects supplied for local provisioning

| Script | Objects/actions |
|---|---|
| db/001_schema.sql | Nine standard Olist public tables for a fresh database; existing tables retained |
| db/002_seed.sql | Guarded synthetic fixture data only in empty olist_test; six tables populated |
| db/003_views.sql | analytics schema; orders, order_items, products, sellers, reviews security-barrier views |
| db/004_roles.sql | sql_rag_sales and sql_rag_analyst; explicit SELECT grants; readonly defaults and hardening |
| db/005_verify_permissions.sql | Per-login checks and assertions; full startup checks also run in Database.verify |
| scripts/provision_passwords.py | Enables dedicated logins and applies privately generated role passwords |

For your already loaded `olist`, run only the view/role/password/verification setup described
in README section 4. Do not run test seed data against your imported dataset.

## Security controls implemented

Authentication and scope mapping precede body validation. Live metadata is permission-filtered
and checked against the contract. Generated SQL is untrusted, parsed into an AST, limited to a
small positive SELECT subset and checked for allowed views/columns/functions/relationships.
The executor requires validated queries and rechecks view scopes. Dedicated database credentials,
explicit read-only transactions, safe search path/string settings, no base-table grants, startup
privilege checks, query/body/row/response/time/concurrency budgets, bounded fetching, verified
normalization, SQL evidence, request IDs, sanitized errors and safe structured audits are included.
See `docs/SECURITY.md` for details and the trust model.

## Known limitations and remaining production blockers

- The live SQL scripts and SQLAlchemy/psycopg path have not been verified against a running server here.
- API adapter behavior is mocked; real model/account compatibility and question interpretation need testing.
- Placeholder mode supports five intent families and complete documented phrases, not arbitrary NL.
- API SQL must fit a deliberately small subset; no CTEs, subqueries, unions, windows, explicit casts,
  offsets, arbitrary functions, raw SQL input or automatic repair.
- Static development bearer tokens are not production identity management; no expiration/revocation flow.
- Scopes separate views/columns, not tenants. Both scopes can read every row in their approved views.
- SQL safety validation does not prove semantic correctness, prevent all aggregation fanout, or replace
  an NL-to-SQL evaluation set. Review API-mode evidence and add metric-specific correctness checks.
- Metadata type/name checks trust administrator-managed view definitions and do not audit all custom functions.
- Query admission/pools are per process; add distributed controls, TLS, isolation, managed secrets,
  observability, protected audit retention, dependency scanning and formal review before public deployment.
- Local model inference and integration with the existing document RAG are extension points, not implemented
  model runtimes or a merged RAG application. A compatible local HTTP server can reuse the API adapter.
- One test framework deprecation warning remains; it does not fail tests, and httpx is retained as requested.

## Commands to run locally

After extracting the project and completing README provisioning:

```bash
cd ~/Downloads/olist-sql-rag
source .venv/bin/activate
python -m scripts.check_database
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second activated terminal:

```bash
python scripts/query_example.py 'Show the top 5 products by revenue'
```

Tests after separately preparing `olist_test`:

```bash
python -m pytest -m 'not integration' -q
python scripts/run_integration.py
```

## Files created

All files below are new. Files modified in your existing projects: **none**.

- `.env.example`
- `.gitignore`
- `README.md`
- `app/__init__.py`
- `app/config.py`
- `app/database.py`
- `app/errors.py`
- `app/generators.py`
- `app/main.py`
- `app/middleware.py`
- `app/models.py`
- `app/policy.py`
- `app/results.py`
- `app/security.py`
- `app/service.py`
- `db/001_schema.sql`
- `db/002_seed.sql`
- `db/003_views.sql`
- `db/004_roles.sql`
- `db/005_verify_permissions.sql`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/REFERENCES.md`
- `docs/SECURITY.md`
- `docs/VERIFICATION.md`
- `docs/openapi.json`
- `pyproject.toml`
- `reports/dependency-check.txt`
- `reports/pytest-output.txt`
- `reports/ruff-output.txt`
- `reports/test-results.xml`
- `requirements.lock`
- `scripts/check_database.py`
- `scripts/init_env.py`
- `scripts/provision_passwords.py`
- `scripts/query_example.py`
- `scripts/run_integration.py`
- `tests/conftest.py`
- `tests/test_api.py`
- `tests/test_config.py`
- `tests/test_database_boundary.py`
- `tests/test_generators.py`
- `tests/test_postgres_integration.py`
- `tests/test_results.py`
- `tests/test_security.py`
