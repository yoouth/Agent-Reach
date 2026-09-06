# Hermes edition — typed platform reads

The Hermes research plugin needs platform reads it can cite: stable field
names, explicit partial flags, and an honest distinction between "there was
nothing" and "we could not see it". `agent-reach read` is that surface.

```bash
agent-reach read status --json
agent-reach read github_repo --repo owner/name --json
agent-reach read github_issue --repo owner/name --number 123 --comments 50 --json
agent-reach read github_readme --repo owner/name --ref main --json
agent-reach read rss_feed --url https://example.com/feed.xml --limit 20 --json
agent-reach read youtube_transcript --url https://www.youtube.com/watch?v=ID --lang en --json
```

JSON is the only output format. The command prints exactly one object on
stdout and exits `0` when `ok` is true, `1` otherwise.

## The envelope

| Field | Meaning |
|---|---|
| `ok` | whether `data` is present |
| `op` | the operation that ran |
| `backend` | what served it: `github-rest`, `xml.etree`, `yt-dlp`, `local` |
| `checked_at` | ISO-8601 UTC instant of the call |
| `environment` | `headless` or `desktop` |
| `elapsed_ms` | wall time of the call |
| `data` | the operation's payload, or `null` |
| `error` | `{type, message}` when the read failed |
| `gap` | `{type, reason}` when the read could not happen |

`error` types: `network_error`, `timeout`, `invalid_input`, `parse_error`,
`backend_error`. `gap` types: `access_gap`, `backend_unavailable`,
`not_found`, `rate_limited`.

The distinction is the point. An `error` says the attempt broke. A `gap` says
the attempt was fine and the content is out of reach — a private repository, a
video with no captions, an exhausted rate-limit budget. A research agent must
report a gap as an access limitation, never as an absence of discussion.

## Operations

- `github_repo --repo owner/name`
- `github_issue --repo owner/name --number N [--comments K]` — K defaults to
  30 and caps at 100; `partial` is true when `comments_fetched` is below
  `comments_total`. Comments carry `parent_id` and their author's `kind`
  (`user`, `bot`, `organization`).
- `github_readme --repo owner/name [--ref R]` — README decoded to UTF-8.
- `rss_feed --url U [--limit N]` — N defaults to 50 and caps at 200; RSS 2.0
  and Atom, parsed with the standard library.
- `youtube_transcript --url U [--lang xx]` — a manual track is preferred, an
  automatic one is used and labelled as such, and `coverage` reports caption
  gaps longer than five seconds.
- `status` — per-operation diagnostics.

`--timeout` (default 60 seconds) bounds every HTTP call and subprocess.

## What `status` proves, and what it does not

`installed` means the backend is present. It is not proof that a read
succeeds; only a read proves that. `configured` means the backend's
prerequisites are met, such as yt-dlp having a JS runtime.

`authenticated` is informational: it reports that a credential exists on this
machine. Reads never use it. `authorized` is always `false` and
`last_success` is always `null` — authorization and success history live in
the Hermes research plugin, not in this tool.

## Security boundary

- Public, cookie-free reads only. GitHub goes through the unauthenticated REST
  API; a `GH_TOKEN` or `GITHUB_TOKEN` in the environment is never sent.
- yt-dlp runs with a scrubbed environment: every variable whose name ends in
  `_TOKEN`, `_KEY`, `_SECRET`, `_PASSWORD`, or `COOKIE(S)`, plus `GH_TOKEN` and
  `GITHUB_TOKEN`, is dropped from the child process.
- Hosts are allowlisted per operation. Feeds must be https and must resolve to
  a public address; loopback, private, and link-local targets are refused.
- Output carries no tokens, cookies, or signed URLs.

## Maintenance boundary

Nothing in this surface installs, upgrades, logs in, or acquires cookies. A
missing backend is reported as `backend_unavailable` with the install hint the
doctor already shows, and the hint is never executed. Installing yt-dlp,
upgrading it, or signing in are maintenance actions taken by a human between
research runs — `agent-reach install` and `agent-reach configure` remain the
place for them.

## Skill

`agent_reach/skill/hermes/SKILL.md` (`agent-reach-hermes`) is the agent-facing
version of this contract, with per-platform detail in
`agent_reach/skill/hermes/references/`. It is scoped to platform access only:
general web search and reading belong to the plugin's own research tools.
