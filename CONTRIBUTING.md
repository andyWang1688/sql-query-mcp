# Contributing

Thanks for contributing to `sql-query-mcp`. We welcome bug fixes,
documentation improvements, and other focused contributions.

## Before you start

Follow these project expectations before you open a pull request:

1. Read [the Git workflow guide](docs/git-workflow.md) for the authoritative
   Git workflow.
2. Open an issue first for larger changes so you can align on scope and
   approach.
3. Keep your change focused on one logical update.
4. Update docs and examples when behavior changes.
5. Run relevant tests locally:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```

## Opening issues and pull requests

Open an issue for bug reports, enhancement requests, or larger proposals. When
you report a bug, include the expected behavior, the actual behavior, and the
smallest reproduction you can provide.

When you open a pull request, explain the problem you are solving, confirm that
you ran relevant tests, and follow [the Git workflow guide](docs/git-workflow.md)
for branch and pull request workflow details.

## New database adapters

New database adapter contributions are welcome, but they need early discussion
because they affect long-term project scope and maintenance.

- Open or join an issue before starting significant adapter work.
- Review [the adapter development guide](docs/adapter-development.md) for
  adapter-specific guidance.
- Check [the roadmap](docs/roadmap.md) to see whether the adapter is already
  planned.
