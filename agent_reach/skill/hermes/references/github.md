# GitHub

Backend: the unauthenticated GitHub REST API (`https://api.github.com`) over the
standard library. No token is sent, even when one exists in the environment.

```bash
agent-reach read github_repo   --repo owner/name --json
agent-reach read github_issue  --repo owner/name --number 123 --comments 50 --json
agent-reach read github_readme --repo owner/name --ref v1.2.0 --json
```

## Contracts

- `github_repo` → `id`, `full_name`, `url`, `description`, `default_branch`,
  `stars`, `forks`, `pushed_at`, `updated_at`, `license` (SPDX id or null),
  `topics`, `archived`.
- `github_issue` → `id`, `number`, `url`, `title`, `state`, `created_at`,
  `updated_at`, `body`, `labels`, `author`, `comments`, `comments_total`,
  `comments_fetched`, `partial`, `language` (always null; GitHub does not
  report an issue's language).
  - `author` and each comment author: `{"login", "kind": "user"|"bot"|
    "organization", "attribution": "handle"}`. A `bot` is not a person; do not
    quote it as community sentiment.
  - Each comment carries `parent_id`, the issue number it belongs to.
  - `--comments` caps at 100. `partial` is true whenever `comments_fetched` is
    below `comments_total`; say so in the write-up.
- `github_readme` → `path`, `url`, `sha`, `ref`, `size`, `text` (decoded
  UTF-8), `truncated` (always false; the API returns the whole file).

## Gaps you will see

- `not_found` — the repository, issue, or README does not exist, or the
  repository is private. A private repository is an access gap in your report,
  not an absence of the thing.
- `rate_limited` — the unauthenticated hourly budget for this host is spent.
  The reason carries the reset time. Wait; do not authenticate around it.

Pull requests are issues on this API: `github_issue` works on a PR number and
returns its conversation comments (not its review comments).
