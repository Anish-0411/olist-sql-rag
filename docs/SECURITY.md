# Security controls and deployment limits

This project is a restricted local development service. It is not a certification that arbitrary
LLM SQL is safe, semantically correct or production-ready.

## Implemented controls

- Random configurable development bearer tokens; no hard-coded working token or secret in the bundle.
- Authentication before JSON parsing/validation; fixed server-side sales/analyst scope mapping.
- Strict Pydantic model; body, question, row and query-size limits; no raw-SQL endpoint.
- Authorized metadata retrieved with the same restricted login that will execute the query.
- Exact view/column/type contract and reviewed logical relationship list.
- Positive AST node/function/operation allowlist and single-statement rule.
- Explicit schemas and aliases, authorized columns, bounded approved joins and no wildcard projection.
- Read-only PostgreSQL transactions and login grants; no base-table SELECT or view modification grants.
- `pg_catalog` search path and standard-conforming strings in every query transaction.
- Startup refusal for privileged flags, role memberships, unexpected effective non-system table
  privileges, schema/database CREATE, TEMP, wrong PG major version or schema drift.
- Statement/lock/idle-transaction/connect/pool budgets, per-process query admission, and bounded fetches.
- Decimal-safe normalization, null/empty handling, non-finite/type/structure checks and response budgets.
- Deterministic grounded answer with executed SQL/source views/truncation metadata.
- HTTPS-only model API by default; administrator-opted loopback HTTP for local servers; redirects
  disabled, ambient proxy settings disabled for model requests, provider response size capped.
- Safe JSON audit log and generic errors; no SQL/parameters/questions/result rows/headers/secrets logged.
- Seed restricted to a separate empty `olist_test` database; no automatic import/reimport or truncation.

## Audit format

One JSON line per HTTP request goes to Python logging's stream handler (stderr).
Fields: event, server request_id, actor, HTTP status, elapsed_ms; authenticated requests include
policy; generation/execution may add strategy, canonical SQL SHA-256 and returned row_count;
errors add a safe error_code. No question hash is stored; no full SQL, question, result rows,
credentials, provider error bodies, arbitrary paths, or stack traces are included by this logger.
The query hash can still correlate repeated queries; treat logs as operational data.
Uvicorn's own access logs are separate; use `--no-access-log` if you do not want them.

## Trust boundaries

Trusted: application source/configuration, pinned parser behavior, database administrators, approved
view definitions and ownership, SQL scripts and configured provider address. Untrusted: HTTP bodies,
tokens presented by callers, model-generated SQL, model explanations and returned database content.
The provider receives the user's question and permitted schema, so apply your organization's data
sharing rules when selecting it. No model call receives database result rows in this implementation.

`ValidatedQuery` is an internal Python value object, not a cryptographic capability. The application
must remain trusted; arbitrary code execution inside the backend can call database drivers directly.
Database grants still bound that login's access, but stolen credentials, malicious administrators,
altered view definitions or modified source are outside what AST checks can prevent.

The SQL validator does not treat keyword regex scanning or prompt instructions as the security
boundary. It parses SQL and permits only known AST structures/references; PostgreSQL enforces the
credential boundary. The model cannot grant itself access by writing a new role in its response.

## Remaining production blockers

1. Run all 15 real PostgreSQL 16 integration tests on a dedicated database; verify the grants and
   actual Olist schema on your laptop. They were not executed in the build environment.
2. Run a real provider smoke test and a representative NL-to-SQL accuracy/security evaluation.
   Mocked provider tests do not demonstrate model quality or account compatibility.
3. Replace static development tokens with trusted identity/session management (e.g. OIDC), rotation,
   expiry and revocation. Add tenant/row isolation for multi-merchant or multi-organization access.
4. Add TLS at ingress, network isolation, managed secrets, distributed rate/concurrency limiting,
   cancellation/deadline handling and workload admission sized for the PostgreSQL instance.
5. Review view ownership, all inherited/PUBLIC grants, schema changes and any installed database
   extensions/functions. Startup checks do not audit all custom function definitions or the entire cluster.
6. Use a dedicated analytics database or replica, reviewed deployment/migration automation, monitoring,
   alerting, protected audit retention/rotation and backup/restore procedures.
7. Add dependency vulnerability scanning, parser regression/fuzz tests and a formal security review
   before exposing broader SQL features or serving untrusted users over the internet.
8. Add semantic checks/evaluation for model-generated joins, filters, dates and aggregates. An allowed
   read-only query can still answer the wrong question or be computationally expensive until timeout.

The current scopes expose all rows of their approved views; there is no claim of row-level tenant
authorization, PII anonymization, formal SQL proof, prompt-injection immunity or full-schema Q&A.
