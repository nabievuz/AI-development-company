# Contributing to DasLab

Thank you for contributing. Please follow these rules to keep the codebase healthy.

## Development workflow

DasLab enforces **one issue = one branch = one PR = one worktree**:

1. Pick or create a ticket. Platform/org-engine work: `board/tickets/DAS-*.md`. Project work: `projects/<slug>/board-tickets/` (never in the org board).
2. Create a git worktree off the target branch:
   ```
   git worktree add /tmp/wt-DAS-1234 -b DAS-1234-my-feature <base-branch>
   ```
3. Do all work for that issue inside the worktree. Never commit directly to `main`.
4. Open a PR from your branch into the target branch (see Branch Protection below).
5. Assign the PR for review per `board/ROUTING.md`. You may not review your own PR.
6. Once CI passes and a reviewer approves, the reviewer merges.

## Branch protection

- `main` requires at least one approving review before merge.
- Direct pushes to `main` are blocked.
- Status checks (CI) must pass before merge is allowed.

## Commit messages

Use the imperative mood in the subject line (e.g. `fix: correct token count`).
Keep the subject under 72 characters. Reference the ticket id: `feat(DAS-1234): …`.

## Code style

Follow the conventions already present in the codebase. Run the linter before pushing:

```
ruff check scripts tests
```

For Python files, also run `python -m py_compile <file>` to catch syntax errors.

## Reporting issues

Use the GitHub issue templates in `.github/ISSUE_TEMPLATE/`. Provide enough context
for someone unfamiliar with the problem to reproduce it.

## Security vulnerabilities

Do **not** open a public issue for security vulnerabilities. See `SECURITY.md` for
the private disclosure process.

## Code of Conduct

All contributors must follow the project Code of Conduct. See `CODE_OF_CONDUCT.md`.
