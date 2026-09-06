---
name: agent-reach-hermes
description: Platform reads for Hermes research: GitHub, RSS, YouTube
---

# Platform access (Hermes edition)

This skill covers one thing: how you reach a platform. It does not tell you how
to research, summarise, or write.

## Which tool

- **Platform reads go through `research_platform` only.** That tool calls
  `agent-reach read <op> --json` and returns one JSON envelope. There is no
  other sanctioned path to GitHub, RSS, or YouTube.
- **Everything else on the open web goes through the research tools**:
  `research_search` to find sources, `research_read` to read one page,
  `research_collect` to gather many, `research_job` for a long-running
  provider run.
- Never reach a platform with mcporter, curl, jina, or Playwright. If a source
  is not reachable through these tools, that is a finding to report, not a
  problem to route around.

## The envelope

Every read returns the same object:

```json
{"ok": true, "op": "...", "backend": "...", "checked_at": "...Z",
 "environment": "headless|desktop", "elapsed_ms": 0,
 "data": {}, "error": null, "gap": null}
```

- `data` is present only when `ok` is true.
- `error` means the read failed: `network_error`, `timeout`, `invalid_input`,
  `parse_error`, `backend_error`.
- `gap` means the read could not happen for a reportable reason:
  `access_gap` (the content exists but is not reachable this way),
  `backend_unavailable` (the tool is not installed),
  `not_found`, `rate_limited`.

A `gap` is evidence about access. It is never evidence about content.

## The five operations

| Operation | Required | Optional | Returns |
|---|---|---|---|
| `github_repo` | `--repo owner/name` | | id, full_name, url, description, default_branch, stars, forks, pushed_at, updated_at, license, topics, archived |
| `github_issue` | `--repo`, `--number` | `--comments` (default 30, max 100) | issue fields, `author`, `comments[]` with `parent_id`, `comments_total`, `comments_fetched`, `partial` |
| `github_readme` | `--repo` | `--ref` | path, url, sha, ref, size, decoded `text`, `truncated` |
| `rss_feed` | `--url` | `--limit` (default 50, max 200) | title, link, updated, `format` (rss/atom), `entries[]`, `entries_total`, `entries_returned`, `partial` |
| `youtube_transcript` | `--url` | `--lang` | video_id, url, title, channel, upload_date, duration_s, `transcript` (language, origin, segments, coverage, transformation), `partial` |

`--timeout` (seconds) bounds any operation. Per-platform detail lives in
`references/github.md`, `references/rss.md`, `references/youtube.md`. Read one
only when you need it.

## Diagnostics: `read status`

`status` reports, per operation: `installed`, `configured`, `authenticated`,
`authorized`, `last_success`, `check_time`, `environment`, `backend`, `notes`.

What each one proves:

- `installed` — the backend binary or module is present. **It does not prove a
  read will succeed.** Only a real read proves that.
- `configured` — the backend's prerequisites are met (yt-dlp has a JS runtime,
  for example).
- `authenticated` — a credential exists on this machine. It is informational.
  Reads are unauthenticated and no token is ever sent.
- `authorized` — always `false` here. Authorization is decided by the Hermes
  research plugin, not by this tool.
- `last_success` — always `null` here. The plugin keeps that record.

## Evidence rules

- Keep the identifiers: post and comment ids, `parent_id` relationships,
  permalinks, and timestamps. Cite the permalink, never a constructed URL.
- Carry `partial` through to your write-up. When `comments_fetched` is below
  `comments_total`, say how many you read.
- Transcripts keep their `language`, their `manual` or `automatic` origin, and
  their segment timestamps. Quote with a timestamp. An automatic transcript is
  a machine guess at speech; attribute it as such.
- Report `coverage` when it matters: a gap in the captions means words are
  missing, not that nothing was said.
- An absent transcript or an unreachable comment thread is an **access gap**.
  Write "no transcript was available", never "there was no discussion" or "no
  relevant content".
- Access-bearing URLs, signed URLs, cookies, and tokens never enter a citation,
  a quote, or a report.

## Maintenance boundary

Installing, upgrading, logging in, and acquiring cookies are maintenance
actions. They happen outside a research run, by a human decision. During a run
a missing or unauthenticated backend is reported and the research continues
without it.
