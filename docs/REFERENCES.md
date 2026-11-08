# Implementation references

Official documentation consulted while implementing this project:

- [PostgreSQL 16 client connection defaults and transaction timeouts](https://www.postgresql.org/docs/16/runtime-config-client.html)
- [PostgreSQL 16 rules and view privileges](https://www.postgresql.org/docs/16/rules-privileges.html)
- [PostgreSQL 16 CREATE VIEW](https://www.postgresql.org/docs/16/sql-createview.html)
- [SQLAlchemy PostgreSQL psycopg dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [SQLAlchemy engine connections and streaming results](https://docs.sqlalchemy.org/en/20/core/connections.html)
- [FastAPI security reference](https://fastapi.tiangolo.com/reference/security/)
- [SQLGlot AST and optimizer documentation](https://sqlglot.com/sqlglot/optimizer/qualify.html)
- [OpenAI JSON/structured output mode](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat)
- [Homebrew PostgreSQL 16 formula and service commands](https://formulae.brew.sh/formula/postgresql@16)

These are API/behavior references, not evidence that the live PostgreSQL or provider tests were run.
The project uses its own narrow column/AST checks rather than enabling SQLGlot's full optimizer.
