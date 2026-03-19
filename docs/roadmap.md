# Roadmap

This page explains which databases `sql-query-mcp` supports today and how to
talk about possible future adapters without overstating project plans. Use it
with [the contribution guide](../CONTRIBUTING.md) and
[the Git workflow guide](git-workflow.md) so your proposal matches the current
codebase and contribution process.

## Supported now

This project currently supports PostgreSQL and MySQL only. That is a deliberate
project limit. The current adapter modules, connection registry, metadata
helpers, query executor, and tests are all written around those two engines.

- PostgreSQL is supported through `sql_query_mcp/adapters/postgres.py`.
- MySQL is supported through `sql_query_mcp/adapters/mysql.py`.
- Metadata tools preserve engine-specific namespace concepts: PostgreSQL uses
  `schema`, and MySQL uses `database`.
- Runtime support does not currently extend to any other engine.

## Candidate adapters

The project is open to discussing additional adapters in the future, but no
adapter beyond PostgreSQL and MySQL is supported yet. The items in this section
are examples of future candidates only. They are not an implementation queue,
not a published roadmap commitment, and not a promise that work has started.

- SQLite is one example of a future candidate for lightweight local and
  embedded workflows.
- SQL Server is one example of a future candidate for teams that need
  Microsoft ecosystem coverage.
- ClickHouse is one example of a future candidate for analytics-heavy read-only
  workloads.
- Any new adapter must be proposed and scoped before implementation work
  starts. See [the contribution guide](../CONTRIBUTING.md) for contribution
  expectations.

## Open for contribution

If you want to help expand adapter coverage, start with design alignment before
you write code. A new adapter changes the code that opens connections, lists
schemas or databases, describes tables, runs read-only queries, and keeps test
coverage current. For that reason, the project treats adapter work as reviewed
scope changes rather than simple add-ons.

- Open or join an issue before starting a new adapter.
- Read [the adapter development guide](adapter-development.md) for
  implementation guidance.
- Follow [the Git workflow guide](git-workflow.md) for branch and pull request
  flow.
- Keep proposals explicit about engine behavior, namespace handling, and
  read-only guarantees.

## Next steps

If you plan to contribute adapter work, review the implementation guide before
opening code changes.

1. Read [the adapter development guide](adapter-development.md) to understand
   the adapter methods and tests you need to match.
2. Re-read [the contribution guide](../CONTRIBUTING.md) for issue and test
   expectations.
3. Follow [the Git workflow guide](git-workflow.md) when you prepare a branch
   or pull request.
