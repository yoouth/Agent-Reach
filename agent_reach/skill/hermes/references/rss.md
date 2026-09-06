# RSS and Atom

Backend: `xml.etree` from the standard library. No third-party parser, no
network beyond the one feed fetch.

```bash
agent-reach read rss_feed --url https://example.com/feed.xml --limit 20 --json
```

## Contracts

- Feed level: `title`, `link`, `updated`, `format` (`rss` or `atom`),
  `entries`, `entries_total`, `entries_returned`, `partial`.
- Entry level: `id`, `title`, `link`, `published`, `updated`, `author`,
  `summary`.
- `entries_total` counts what the feed carried; `entries_returned` counts what
  `--limit` allowed through. `partial` is true when they differ, which means
  the feed had more items, not that the site had nothing more.
- Dates arrive exactly as the feed wrote them (RFC 822 for RSS, ISO 8601 for
  Atom). Do not silently reformat them in a citation.
- `summary` is the feed's own excerpt and often contains HTML. It is not the
  article. To read the article, follow `link` with `research_read`.

## Limits

- https only. The host must resolve to a public address; loopback, private,
  and link-local targets are refused as `invalid_input`.
- A feed that declares a DTD is refused (`parse_error`). That is an
  entity-expansion defence, not a comment on the publisher.
- Podcast feeds work: the entry `link` is the episode page. Audio itself is out
  of scope here.
