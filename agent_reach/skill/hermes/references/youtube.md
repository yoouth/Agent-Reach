# YouTube transcripts

Backend: a local `yt-dlp` binary, subtitles only. Nothing is downloaded, no
cookies are read or written, and the child process runs with a scrubbed
environment.

```bash
agent-reach read youtube_transcript --url https://www.youtube.com/watch?v=ID --json
agent-reach read youtube_transcript --url https://youtu.be/ID --lang ja --json
```

Accepted hosts: `youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`.

## Contract

`video_id`, `url` (canonical watch URL), `title`, `channel`, `upload_date`,
`duration_s`, `partial`, and `transcript`:

- `language` — the track actually used, which may differ from `--lang` when a
  regional variant was the closest match.
- `origin` — `manual` when a human-authored track existed, `automatic` when the
  text is machine-generated. A manual track in the requested language always
  wins. Attribute automatic transcripts as machine transcription.
- `segments` — `{"start_s", "end_s", "text"}`, in order. Quote with the
  timestamp.
- `coverage` — `segments`, `first_start_s`, `last_end_s`, `duration_s`, and
  `gaps`: stretches longer than five seconds with no caption. A gap means words
  are missing from the record.
- `transformation` — what was done to the raw file, always starting with
  `vtt-parsed`. Rolling automatic captions repeat each line into the next cue;
  when those duplicates are dropped the list says so.

`partial` is true when the captions have a gap or stop well before the video
ends.

## Gaps

- `access_gap` — no manual or automatic track exists for the requested
  language. Report it as "no transcript was available", never as "the video
  had no relevant content".
- `access_gap` for a signed-in wall — the video needs a session. Out of scope;
  report it.
- `rate_limited` — YouTube is throttling this host. Wait and retry later.
- `backend_unavailable` — yt-dlp is not installed. The reason carries the
  install hint. Installing it is a maintenance action for a human, outside the
  research run.
