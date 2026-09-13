# -*- coding: utf-8 -*-
"""Typed public read operations for the Hermes research plugin.

Every operation returns one JSON-serialisable envelope. The surface is
deliberately narrow:

  - Public, cookie-free reads only. GitHub goes through the unauthenticated
    REST API; a token in the environment is never sent. YouTube transcripts
    come from a local yt-dlp binary (subtitles only, no download, no cookies).
    RSS is parsed with the standard library.
  - Nothing here installs, upgrades, logs in, or acquires cookies. A missing
    backend is reported as a gap so the caller can decide; it is never
    repaired at runtime.
  - Child processes inherit a scrubbed environment (see `scrubbed_env`) and
    every network call and subprocess is bounded by a timeout.
"""

from __future__ import annotations

import base64
import html
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlsplit

from agent_reach import __version__
from agent_reach.utils.process import utf8_subprocess_env
from agent_reach.utils.text import scrub_url_credentials
from agent_reach.utils.url import normalize_public_http_url

DEFAULT_TIMEOUT = 60
OPERATIONS = (
    "github_repo",
    "github_issue",
    "github_readme",
    "rss_feed",
    "youtube_transcript",
    "status",
)

_BACKENDS = {
    "github_repo": "github-rest",
    "github_issue": "github-rest",
    "github_readme": "github-rest",
    "rss_feed": "xml.etree",
    "youtube_transcript": "yt-dlp",
    "status": "local",
}

_USER_AGENT = f"agent-reach-hermes/{__version__}"
_GITHUB_API = "https://api.github.com"
_GITHUB_HOSTS = {"api.github.com"}
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{5,32}$")
_MAX_BODY_BYTES = 8 * 1024 * 1024
_MAX_COMMENTS = 100
_MAX_ENTRIES = 200
_ACTOR_KINDS = {"user": "user", "bot": "bot", "organization": "organization"}
#: A caption gap longer than this many seconds is reported in `coverage`.
_GAP_SECONDS = 5.0

#: Environment variables never handed to a child process.
_SECRET_SUFFIXES = ("_TOKEN", "_KEY", "_SECRET", "_PASSWORD", "COOKIE", "COOKIES")
_SECRET_NAMES = {"GH_TOKEN", "GITHUB_TOKEN"}
_KEEP_ENV = ("PATH", "HOME", "LANG", "TMPDIR")


class ReadGap(Exception):
    """A read that could not happen for a reportable, non-error reason."""

    def __init__(self, gap_type: str, reason: str):
        super().__init__(reason)
        self.gap_type = gap_type
        self.reason = reason


class ReadError(Exception):
    """A read that failed."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


# ── envelope ────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def environment() -> str:
    """Report whether a desktop session is available to this process."""
    if sys.platform in ("darwin", "win32"):
        return "desktop"
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return "desktop"
    return "headless"


def run(op: str, **options: Any) -> dict:
    """Execute one read operation and return its envelope."""
    started = time.monotonic()
    data: Optional[dict] = None
    error: Optional[dict] = None
    gap: Optional[dict] = None

    handler = _HANDLERS.get(op)
    if handler is None:
        error = {"type": "invalid_input", "message": f"unknown operation: {op}"}
    else:
        try:
            data = handler(options)
        except ReadGap as exc:
            gap = {"type": exc.gap_type, "reason": scrub_url_credentials(exc.reason)}
        except ReadError as exc:
            error = {"type": exc.error_type, "message": scrub_url_credentials(exc.message)}

    return {
        "ok": data is not None,
        "op": op,
        "backend": _BACKENDS.get(op, "unknown"),
        "checked_at": _now_iso(),
        "environment": environment(),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "data": data,
        "error": error,
        "gap": gap,
    }


# ── shared helpers ──────────────────────────────────


def scrubbed_env() -> dict:
    """Environment for child processes: no credentials, still usable."""
    env = {
        name: value
        for name, value in os.environ.items()
        if name.upper() not in _SECRET_NAMES and not name.upper().endswith(_SECRET_SUFFIXES)
    }
    for name in _KEEP_ENV:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    return utf8_subprocess_env(env)


def _timeout(options: dict) -> float:
    value = options.get("timeout") or DEFAULT_TIMEOUT
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise ReadError("invalid_input", "--timeout must be a number") from None
    if seconds <= 0:
        raise ReadError("invalid_input", "--timeout must be positive")
    return seconds


def _clamp(value: Any, default: int, maximum: int, flag: str) -> int:
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ReadError("invalid_input", f"{flag} must be an integer") from None
    if number < 0:
        raise ReadError("invalid_input", f"{flag} must not be negative")
    return min(number, maximum)


def _required(options: dict, name: str, flag: str) -> str:
    value = options.get(name)
    if value is None or str(value).strip() == "":
        raise ReadError("invalid_input", f"{flag} is required for this operation")
    return str(value).strip()


def _repo(options: dict) -> str:
    repo = _required(options, "repo", "--repo")
    if not _REPO_RE.match(repo):
        raise ReadError("invalid_input", "--repo must look like owner/name")
    return repo


def _https_url(url: str, allowed_hosts: set) -> str:
    """Accept an https URL whose host is in *allowed_hosts*."""
    candidate = str(url or "").strip()
    parsed = urlsplit(candidate)
    try:
        host = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
    except (TypeError, ValueError):
        raise ReadError("invalid_input", "malformed URL") from None
    if parsed.scheme.lower() != "https":
        raise ReadError("invalid_input", "only https URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ReadError("invalid_input", "URLs with credentials are not allowed")
    if host not in allowed_hosts:
        allowed = ", ".join(sorted(allowed_hosts))
        raise ReadError("invalid_input", f"host {host or '(none)'} is not allowed here; allowed: {allowed}")
    return candidate


def _public_https_url(url: str) -> str:
    """Accept an https URL on any host that resolves to a public address."""
    candidate = str(url or "").strip()
    if urlsplit(candidate).scheme.lower() != "https":
        raise ReadError("invalid_input", "only https URLs are allowed")
    try:
        normalized = normalize_public_http_url(candidate)
    except ValueError:
        raise ReadError("invalid_input", "only public https URLs are allowed") from None

    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").lower()
    port = parsed.port or 443
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ReadError("network_error", f"cannot resolve {host}: {exc}") from None
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ReadError("invalid_input", f"{host} resolves to a non-public address")
    return normalized


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are never followed: the validated host must be the host that answers (a public host redirecting to a
    private address would otherwise bypass _https_url / _public_https_url)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = (urlsplit(str(newurl)).hostname or "?").lower()
        raise ReadError(
            "invalid_input",
            f"HTTP {code} redirect to {target} refused: redirects are not followed; "
            "re-run with the redirect target only if it is an allowed public https URL",
        )


_OPENER = urllib.request.build_opener(_NoRedirect())


def _open(request: urllib.request.Request, timeout: float):
    """The single HTTP seam for the read operations (tests patch this)."""
    return _OPENER.open(request, timeout=timeout)


def _http_get(url: str, timeout: float, accept: str) -> tuple:
    """GET *url* with no credentials and no redirect following; return (body bytes, headers)."""
    request = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": _USER_AGENT},
        method="GET",
    )
    try:
        with _open(request, timeout=timeout) as response:
            return response.read(_MAX_BODY_BYTES), response.headers
    except urllib.error.HTTPError as exc:
        _raise_http_error(exc)
    except socket.timeout:
        raise ReadError("timeout", f"request timed out after {timeout:g}s") from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout) or isinstance(reason, TimeoutError):
            raise ReadError("timeout", f"request timed out after {timeout:g}s") from None
        raise ReadError("network_error", f"request failed: {reason}") from None
    except (TimeoutError, OSError) as exc:
        raise ReadError("network_error", f"request failed: {exc}") from None
    raise ReadError("network_error", "request failed")  # pragma: no cover - defensive


def _raise_http_error(exc: urllib.error.HTTPError) -> None:
    headers = getattr(exc, "headers", None) or {}
    remaining = headers.get("X-RateLimit-Remaining")
    if exc.code in (403, 429) and str(remaining) == "0":
        reset = _reset_time(headers.get("X-RateLimit-Reset"))
        raise ReadGap(
            "rate_limited",
            f"GitHub rate limit exhausted for unauthenticated reads; resets at {reset}",
        )
    if exc.code == 404:
        raise ReadGap("not_found", "the requested resource does not exist or is not public")
    raise ReadError("backend_error", f"HTTP {exc.code} {exc.reason}")


def _reset_time(raw: Any) -> str:
    try:
        moment = datetime.fromtimestamp(int(str(raw)), tz=timezone.utc)
    except (TypeError, ValueError):
        return "an unknown time"
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _github_json(path: str, timeout: float) -> Any:
    body, _ = _http_get(f"{_GITHUB_API}{path}", timeout, "application/vnd.github+json")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ReadError("parse_error", f"GitHub returned unreadable JSON: {exc}") from None


def _actor(payload: Any) -> dict:
    user = payload if isinstance(payload, dict) else {}
    kind = _ACTOR_KINDS.get(str(user.get("type", "")).lower(), "user")
    return {
        "login": user.get("login") or "unknown",
        "kind": kind,
        "attribution": "handle",
    }


# ── GitHub ──────────────────────────────────────────


def _github_repo(options: dict) -> dict:
    repo = _repo(options)
    payload = _github_json(f"/repos/{repo}", _timeout(options))
    license_payload = payload.get("license") or {}
    return {
        "id": payload.get("id"),
        "full_name": payload.get("full_name"),
        "url": payload.get("html_url"),
        "description": payload.get("description"),
        "default_branch": payload.get("default_branch"),
        "stars": payload.get("stargazers_count"),
        "forks": payload.get("forks_count"),
        "pushed_at": payload.get("pushed_at"),
        "updated_at": payload.get("updated_at"),
        "license": license_payload.get("spdx_id") or license_payload.get("key"),
        "topics": list(payload.get("topics") or []),
        "archived": bool(payload.get("archived")),
    }


def _github_issue(options: dict) -> dict:
    repo = _repo(options)
    number = _required(options, "number", "--number")
    try:
        number = int(number)
    except ValueError:
        raise ReadError("invalid_input", "--number must be an integer") from None
    wanted = _clamp(options.get("comments"), 30, _MAX_COMMENTS, "--comments")
    timeout = _timeout(options)

    issue = _github_json(f"/repos/{repo}/issues/{number}", timeout)
    comments_total = int(issue.get("comments") or 0)

    raw_comments: list = []
    if wanted and comments_total:
        raw_comments = _github_json(
            f"/repos/{repo}/issues/{number}/comments?per_page={wanted}", timeout
        )
        if not isinstance(raw_comments, list):
            raise ReadError("parse_error", "GitHub returned an unexpected comment payload")

    comments = [
        {
            "id": comment.get("id"),
            "parent_id": number,
            "url": comment.get("html_url"),
            "created_at": comment.get("created_at"),
            "updated_at": comment.get("updated_at"),
            "body": comment.get("body"),
            "author": _actor(comment.get("user")),
        }
        for comment in raw_comments
    ]
    return {
        "id": issue.get("id"),
        "number": issue.get("number", number),
        "url": issue.get("html_url"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "body": issue.get("body"),
        "labels": [
            label.get("name") if isinstance(label, dict) else str(label)
            for label in (issue.get("labels") or [])
        ],
        "author": _actor(issue.get("user")),
        "comments": comments,
        "comments_total": comments_total,
        "comments_fetched": len(comments),
        "partial": len(comments) < comments_total,
        "language": None,
    }


def _github_readme(options: dict) -> dict:
    repo = _repo(options)
    ref = options.get("ref")
    path = f"/repos/{repo}/readme"
    if ref:
        path += f"?ref={quote(str(ref), safe='')}"
    payload = _github_json(path, _timeout(options))

    encoded = payload.get("content") or ""
    if str(payload.get("encoding") or "base64") != "base64":
        raise ReadError("parse_error", f"unsupported README encoding: {payload.get('encoding')}")
    try:
        text = base64.b64decode(encoded).decode("utf-8", errors="replace")
    except (ValueError, TypeError) as exc:
        raise ReadError("parse_error", f"README content could not be decoded: {exc}") from None

    html_url = payload.get("html_url") or ""
    return {
        "path": payload.get("path"),
        "url": html_url,
        "sha": payload.get("sha"),
        "ref": str(ref) if ref else _ref_from_blob_url(html_url),
        "size": payload.get("size"),
        "text": text,
        "truncated": False,
    }


def _ref_from_blob_url(html_url: str) -> Optional[str]:
    """Recover the ref GitHub served from its blob permalink."""
    parts = str(html_url).split("/blob/", 1)
    if len(parts) != 2 or "/" not in parts[1]:
        return None
    return parts[1].split("/", 1)[0] or None


def _github_credentials_present() -> bool:
    """Whether a GitHub credential exists locally. Informational only."""
    if any(os.environ.get(name) for name in ("GH_TOKEN", "GITHUB_TOKEN")):
        return True
    try:
        from agent_reach.channels.github import (
            GitHubConfigError,
            _saved_github_host_configured,
        )

        return bool(_saved_github_host_configured())
    except Exception:  # noqa: BLE001 — credential presence is never load-bearing
        return False


# ── RSS / Atom ──────────────────────────────────────


def _local_name(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


def _child(element, name: str):
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _child_text(element, *names: str) -> Optional[str]:
    for name in names:
        child = _child(element, name)
        if child is not None and (child.text or "").strip():
            return child.text.strip()
    return None


def _atom_link(entry) -> Optional[str]:
    fallback = None
    for child in entry:
        if _local_name(child.tag) != "link":
            continue
        href = child.get("href")
        if not href:
            if (child.text or "").strip():
                fallback = fallback or child.text.strip()
            continue
        rel = (child.get("rel") or "alternate").lower()
        if rel == "alternate":
            return href
        fallback = fallback or href
    return fallback


def _author_text(element) -> Optional[str]:
    author = _child(element, "author")
    if author is not None:
        name = _child_text(author, "name")
        if name:
            return name
        if (author.text or "").strip():
            return author.text.strip()
    return _child_text(element, "creator")


def _rss_feed(options: dict) -> dict:
    url = _public_https_url(_required(options, "url", "--url"))
    limit = _clamp(options.get("limit"), 50, _MAX_ENTRIES, "--limit")
    body, _ = _http_get(
        url, _timeout(options), "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8"
    )
    if b"<!DOCTYPE" in body or b"<!doctype" in body:
        raise ReadError("parse_error", "feed declares a DTD; refusing to parse it")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ReadError("parse_error", f"feed is not well-formed XML: {exc}") from None

    if _local_name(root.tag) == "feed":
        return _parse_atom(root, limit)
    channel = _child(root, "channel")
    if channel is None:
        raise ReadError("parse_error", "feed is neither RSS 2.0 nor Atom")
    return _parse_rss(channel, limit)


def _parse_rss(channel, limit: int) -> dict:
    items = [child for child in channel if _local_name(child.tag) == "item"]
    entries = [
        {
            "id": _child_text(item, "guid") or _child_text(item, "link"),
            "title": _child_text(item, "title"),
            "link": _child_text(item, "link"),
            "published": _child_text(item, "pubdate", "date"),
            "updated": _child_text(item, "updated"),
            "author": _author_text(item),
            "summary": _child_text(item, "description", "summary"),
        }
        for item in items[:limit]
    ]
    return {
        "title": _child_text(channel, "title"),
        "link": _child_text(channel, "link"),
        "updated": _child_text(channel, "lastbuilddate", "pubdate"),
        "format": "rss",
        "entries": entries,
        "entries_total": len(items),
        "entries_returned": len(entries),
        "partial": len(entries) < len(items),
    }


def _parse_atom(root, limit: int) -> dict:
    items = [child for child in root if _local_name(child.tag) == "entry"]
    entries = [
        {
            "id": _child_text(item, "id") or _atom_link(item),
            "title": _child_text(item, "title"),
            "link": _atom_link(item),
            "published": _child_text(item, "published", "issued"),
            "updated": _child_text(item, "updated"),
            "author": _author_text(item),
            "summary": _child_text(item, "summary", "content"),
        }
        for item in items[:limit]
    ]
    return {
        "title": _child_text(root, "title"),
        "link": _atom_link(root),
        "updated": _child_text(root, "updated"),
        "format": "atom",
        "entries": entries,
        "entries_total": len(items),
        "entries_returned": len(entries),
        "partial": len(entries) < len(items),
    }


# ── YouTube ─────────────────────────────────────────


_VTT_TIMING_RE = re.compile(
    r"^\s*((?:\d{1,3}:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d{1,3}:)?\d{1,2}:\d{2}[.,]\d{1,3})"
)
_VTT_TAG_RE = re.compile(r"<[^>]*>")


def _vtt_seconds(stamp: str) -> float:
    parts = stamp.strip().replace(",", ".").split(":")
    seconds = float(parts[-1])
    if len(parts) > 1:
        seconds += int(parts[-2]) * 60
    if len(parts) > 2:
        seconds += int(parts[-3]) * 3600
    return round(seconds, 3)


def _clean_caption_line(line: str) -> str:
    return " ".join(html.unescape(_VTT_TAG_RE.sub("", line)).split())


def parse_vtt(text: str) -> tuple:
    """Parse WebVTT into (segments, duplicate_lines_removed)."""
    segments: list = []
    removed = 0
    last_line: Optional[str] = None
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    index = 0
    while index < len(lines):
        match = _VTT_TIMING_RE.match(lines[index])
        index += 1
        if not match:
            continue
        start_s = _vtt_seconds(match.group(1))
        end_s = _vtt_seconds(match.group(2))
        kept: list = []
        while index < len(lines) and lines[index].strip() and not _VTT_TIMING_RE.match(lines[index]):
            cleaned = _clean_caption_line(lines[index])
            index += 1
            if not cleaned:
                continue
            if cleaned == last_line:
                removed += 1
                continue
            kept.append(cleaned)
            last_line = cleaned
        if kept:
            segments.append({"start_s": start_s, "end_s": end_s, "text": " ".join(kept)})
    return segments, removed


def _coverage(segments: list, duration_s: Optional[float]) -> dict:
    gaps = []
    for previous, current in zip(segments, segments[1:]):
        if current["start_s"] - previous["end_s"] > _GAP_SECONDS:
            gaps.append({"from_s": previous["end_s"], "to_s": current["start_s"]})
    return {
        "segments": len(segments),
        "first_start_s": segments[0]["start_s"] if segments else None,
        "last_end_s": segments[-1]["end_s"] if segments else None,
        "duration_s": duration_s,
        "gaps": gaps,
    }


def _video_id(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    else:
        query = dict(
            pair.split("=", 1) for pair in parsed.query.split("&") if "=" in pair
        )
        candidate = query.get("v", "")
        if not candidate:
            segments = [segment for segment in parsed.path.split("/") if segment]
            if len(segments) >= 2 and segments[0] in ("shorts", "live", "embed", "v"):
                candidate = segments[1]
    if not _VIDEO_ID_RE.match(candidate or ""):
        raise ReadError("invalid_input", "could not find a video id in the URL")
    return candidate


def _yt_dlp(args: list, timeout: float) -> str:
    binary = shutil.which("yt-dlp")
    if not binary:
        raise ReadGap("backend_unavailable", f"yt-dlp is not installed. Install hint: {_ytdlp_hint()}")
    try:
        completed = subprocess.run(  # noqa: S603 — fixed binary, no shell
            [binary, *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=scrubbed_env(),
        )
    except subprocess.TimeoutExpired:
        raise ReadError("timeout", f"yt-dlp timed out after {timeout:g}s") from None
    except OSError as exc:
        raise ReadGap("backend_unavailable", f"yt-dlp could not be executed: {exc}") from None
    if completed.returncode != 0:
        combined = (completed.stderr or completed.stdout or "").strip()
        detail = combined.splitlines()
        message = detail[-1] if detail else "yt-dlp failed"
        lowered = combined.lower()
        if "429" in combined or "too many requests" in lowered:
            raise ReadGap("rate_limited", f"YouTube is rate limiting this host: {message}")
        if "sign in to confirm" in lowered or "cookies" in lowered:
            raise ReadGap(
                "access_gap",
                f"YouTube requires a signed-in session for this video: {message}",
            )
        raise ReadError("backend_error", message)
    return completed.stdout


def _ytdlp_hint() -> str:
    """The install hint the doctor already shows. Reported, never executed."""
    try:
        from agent_reach.channels.youtube import _YTDLP_UPGRADE_COMMAND

        return _YTDLP_UPGRADE_COMMAND
    except Exception:  # noqa: BLE001 — the hint is cosmetic
        return "see `agent-reach doctor`"


def _match_track(keys: list, wanted: str) -> Optional[str]:
    """Match a language tag exactly, then by its base subtag (en-US -> en)."""
    wanted = wanted.lower()
    base = wanted.split("-", 1)[0]
    for candidate in (wanted, base):
        for key in keys:
            if key.lower() == candidate:
                return key
        for key in keys:
            if key.lower().split("-", 1)[0] == candidate:
                return key
    return None


def _pick_track(tracks: dict, lang: Optional[str], video_language: Optional[str]) -> Optional[str]:
    """Choose one subtitle track: the requested language, else the video's own."""
    keys = [key for key in tracks if key != "live_chat"]
    if not keys:
        return None
    if lang:
        return _match_track(keys, lang)
    if video_language:
        matched = _match_track(keys, video_language)
        if matched:
            return matched
    return keys[0]


def _youtube_transcript(options: dict) -> dict:
    url = _https_url(_required(options, "url", "--url"), _YOUTUBE_HOSTS)
    lang = (options.get("lang") or "").strip() or None
    timeout = _timeout(options)
    video_id = _video_id(url)

    raw = _yt_dlp(
        ["--skip-download", "--no-warnings", "--no-playlist", "--dump-single-json", url],
        timeout,
    )
    try:
        meta = json.loads(raw)
    except ValueError as exc:
        raise ReadError("parse_error", f"yt-dlp returned unreadable JSON: {exc}") from None

    manual = meta.get("subtitles") or {}
    automatic = meta.get("automatic_captions") or {}
    video_language = meta.get("language")
    track = _pick_track(manual, lang, video_language)
    origin = "manual"
    if track is None:
        track = _pick_track(automatic, lang, video_language)
        origin = "automatic"
    if track is None:
        raise ReadGap(
            "access_gap",
            f"no manual or automatic transcript available for {lang or 'any'}",
        )

    with tempfile.TemporaryDirectory(prefix="agent-reach-hermes-") as work_dir:
        _yt_dlp(
            [
                "--skip-download",
                "--no-simulate",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                track,
                "--sub-format",
                "vtt",
                "--no-warnings",
                "--no-playlist",
                "-o",
                os.path.join(work_dir, "%(id)s"),
                url,
            ],
            timeout,
        )
        written = sorted(Path(work_dir).glob("*.vtt"))
        preferred = [path for path in written if f".{track}." in path.name]
        chosen = (preferred or written)[:1]
        if not chosen:
            raise ReadGap(
                "access_gap",
                f"no manual or automatic transcript available for {lang or 'any'}",
            )
        vtt_text = chosen[0].read_text(encoding="utf-8", errors="replace")

    segments, removed = parse_vtt(vtt_text)
    if not segments:
        raise ReadGap(
            "access_gap",
            f"no manual or automatic transcript available for {lang or 'any'}",
        )

    duration = meta.get("duration")
    duration_s = float(duration) if isinstance(duration, (int, float)) else None
    coverage = _coverage(segments, duration_s)
    transformation = ["vtt-parsed"]
    if removed:
        transformation.append("overlapping auto-caption lines deduplicated")

    partial = bool(coverage["gaps"]) or bool(
        duration_s and coverage["last_end_s"] is not None
        and duration_s - coverage["last_end_s"] > _GAP_SECONDS
    )
    return {
        "video_id": meta.get("id") or video_id,
        "url": f"https://www.youtube.com/watch?v={meta.get('id') or video_id}",
        "title": meta.get("title"),
        "channel": meta.get("channel") or meta.get("uploader"),
        "upload_date": meta.get("upload_date"),
        "duration_s": duration_s,
        "transcript": {
            "language": track,
            "origin": origin,
            "segments": segments,
            "coverage": coverage,
            "transformation": transformation,
        },
        "partial": partial,
    }


# ── status ──────────────────────────────────────────


def _youtube_readiness() -> tuple:
    """(installed, configured, notes) from the channel check doctor already runs."""
    try:
        from agent_reach.channels.youtube import YouTubeChannel

        status, message = YouTubeChannel().check(None)
    except Exception as exc:  # noqa: BLE001 — status must never fail
        return False, False, f"yt-dlp readiness could not be determined: {exc}"
    return status != "off", status == "ok", message


def _status(options: dict) -> dict:
    checked_at = _now_iso()
    env = environment()
    github_authenticated = _github_credentials_present()
    installed, configured, youtube_notes = _youtube_readiness()

    def entry(op: str, *, installed: bool, configured: bool, authenticated, notes: str) -> dict:
        return {
            "installed": installed,
            "configured": configured,
            "authenticated": authenticated,
            "authorized": False,
            "last_success": None,
            "check_time": checked_at,
            "environment": env,
            "backend": _BACKENDS[op],
            "notes": notes,
        }

    github_notes = (
        "unauthenticated api.github.com reads over stdlib urllib; "
        "a local token is never sent"
    )
    operations = {
        op: entry(
            op,
            installed=True,
            configured=True,
            authenticated=github_authenticated,
            notes=github_notes,
        )
        for op in ("github_repo", "github_issue", "github_readme")
    }
    operations["rss_feed"] = entry(
        "rss_feed",
        installed=True,
        configured=True,
        authenticated=None,
        notes="standard-library XML parsing; public https feeds only",
    )
    operations["youtube_transcript"] = entry(
        "youtube_transcript",
        installed=installed,
        configured=configured,
        authenticated=None,
        notes=scrub_url_credentials(youtube_notes),
    )
    return {"operations": operations}


_HANDLERS = {
    "github_repo": _github_repo,
    "github_issue": _github_issue,
    "github_readme": _github_readme,
    "rss_feed": _rss_feed,
    "youtube_transcript": _youtube_transcript,
    "status": _status,
}
