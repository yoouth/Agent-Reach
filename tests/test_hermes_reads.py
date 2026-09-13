# -*- coding: utf-8 -*-
"""Tests for the Hermes read surface (agent_reach.hermes.reads).

Every backend is mocked: these tests never touch the network, never spawn a
real process, and never read a credential.
"""

import base64
import email.message
import json
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_reach.cli import main
from agent_reach.hermes import reads

# ── fakes ───────────────────────────────────────────


class _FakeResponse:
    def __init__(self, body: bytes, headers=None):
        self._body = body
        self.headers = headers or {}

    def read(self, _limit=None):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _http_error(code, headers=None):
    message = email.message.Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return urllib.error.HTTPError("https://api.github.com/x", code, "Boom", message, None)


@pytest.fixture
def fake_http(monkeypatch):
    """Queue urllib responses keyed by URL substring."""
    calls = []
    routes = {}

    def urlopen(request, timeout=None):
        calls.append({"url": request.full_url, "headers": dict(request.headers), "timeout": timeout})
        for fragment, response in routes.items():
            if fragment in request.full_url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected request: {request.full_url}")

    monkeypatch.setattr(reads, "_open", lambda request, timeout=None: urlopen(request, timeout=timeout))   # the one HTTP seam (redirects refused inside it)
    return {"calls": calls, "routes": routes}


def _json_response(payload, headers=None):
    return _FakeResponse(json.dumps(payload).encode("utf-8"), headers)


@pytest.fixture
def fake_yt_dlp(monkeypatch):
    """Fake yt-dlp: phase 1 dumps JSON, phase 2 writes a .vtt into -o's dir."""
    state = {"metadata": {}, "vtt": "", "envs": [], "commands": [], "returncode": 0, "stderr": ""}

    class _Completed:
        def __init__(self, stdout, returncode=0, stderr=""):
            self.stdout = stdout
            self.returncode = returncode
            self.stderr = stderr

    def run(command, **kwargs):
        state["envs"].append(kwargs.get("env") or {})
        state["commands"].append(list(command))
        if state["returncode"]:
            return _Completed("", state["returncode"], state["stderr"])
        if "--dump-single-json" in command:
            return _Completed(json.dumps(state["metadata"]))
        template = command[command.index("-o") + 1]
        track = command[command.index("--sub-langs") + 1]
        target = Path(template).parent / f"{state['metadata'].get('id', 'vid')}.{track}.vtt"
        target.write_text(state["vtt"], encoding="utf-8")
        return _Completed("")

    monkeypatch.setattr(reads.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(reads.subprocess, "run", run)
    return state


VTT_WITH_GAP_AND_DUPES = """WEBVTT

00:00:01.000 --> 00:00:03.000
hello <c>world</c>

00:00:03.000 --> 00:00:05.000
hello world
second &amp; line

00:00:12.000 --> 00:00:14.000
after the gap
"""


# ── GitHub ──────────────────────────────────────────


class TestGitHubIssue:
    def _issue_payload(self, comments_total):
        return {
            "id": 11,
            "number": 7,
            "html_url": "https://github.com/o/r/issues/7",
            "title": "Broken thing",
            "state": "open",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "body": "details",
            "labels": [{"name": "bug"}],
            "user": {"login": "octocat", "type": "User"},
            "comments": comments_total,
        }

    def _comment(self, identifier, login, kind):
        return {
            "id": identifier,
            "html_url": f"https://github.com/o/r/issues/7#issuecomment-{identifier}",
            "created_at": "2026-01-03T00:00:00Z",
            "updated_at": "2026-01-03T00:00:00Z",
            "body": "a reply",
            "user": {"login": login, "type": kind},
        }

    def test_normalizes_authors_and_reports_partial(self, fake_http):
        fake_http["routes"]["/issues/7/comments"] = _json_response(
            [self._comment(1, "octocat", "User"), self._comment(2, "dependabot[bot]", "Bot")]
        )
        fake_http["routes"]["/issues/7"] = _json_response(self._issue_payload(9))

        result = reads.run("github_issue", repo="o/r", number="7", comments=2)

        assert result["ok"] is True
        assert result["backend"] == "github-rest"
        data = result["data"]
        assert data["url"] == "https://github.com/o/r/issues/7"
        assert data["labels"] == ["bug"]
        assert data["language"] is None
        assert data["author"] == {"login": "octocat", "kind": "user", "attribution": "handle"}
        assert data["comments_total"] == 9
        assert data["comments_fetched"] == 2
        assert data["partial"] is True
        assert [c["author"]["kind"] for c in data["comments"]] == ["user", "bot"]
        assert {c["parent_id"] for c in data["comments"]} == {7}
        assert data["comments"][0]["url"].endswith("#issuecomment-1")

    def test_complete_comment_set_is_not_partial(self, fake_http):
        fake_http["routes"]["/issues/7/comments"] = _json_response(
            [self._comment(1, "octocat", "User")]
        )
        fake_http["routes"]["/issues/7"] = _json_response(self._issue_payload(1))

        data = reads.run("github_issue", repo="o/r", number="7")["data"]

        assert data["comments_fetched"] == 1
        assert data["partial"] is False

    def test_comment_count_is_capped_at_one_hundred(self, fake_http):
        fake_http["routes"]["/issues/7/comments"] = _json_response([])
        fake_http["routes"]["/issues/7"] = _json_response(self._issue_payload(500))

        reads.run("github_issue", repo="o/r", number="7", comments=500)

        assert any("per_page=100" in call["url"] for call in fake_http["calls"])

    def test_never_sends_a_token(self, fake_http, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "secret-token")
        fake_http["routes"]["/repos/o/r"] = _json_response({"id": 1, "full_name": "o/r"})

        reads.run("github_repo", repo="o/r")

        sent = " ".join(str(call["headers"]) for call in fake_http["calls"]).lower()
        assert "authorization" not in sent
        assert "secret-token" not in sent


class TestGitHubReadme:
    def test_decodes_base64_content(self, fake_http):
        fake_http["routes"]["/readme"] = _json_response(
            {
                "path": "README.md",
                "html_url": "https://github.com/o/r/blob/main/README.md",
                "sha": "abc123",
                "size": 12,
                "encoding": "base64",
                "content": base64.b64encode("# Title\né".encode("utf-8")).decode("ascii"),
            }
        )

        data = reads.run("github_readme", repo="o/r")["data"]

        assert data["text"] == "# Title\né"
        assert data["ref"] == "main"
        assert data["sha"] == "abc123"
        assert data["truncated"] is False

    def test_explicit_ref_is_requested_and_reported(self, fake_http):
        fake_http["routes"]["/readme"] = _json_response(
            {"path": "README.md", "html_url": "", "sha": "s", "size": 0,
             "content": base64.b64encode(b"x").decode("ascii")}
        )

        data = reads.run("github_readme", repo="o/r", ref="v1.2.3")["data"]

        assert data["ref"] == "v1.2.3"
        assert any("ref=v1.2.3" in call["url"] for call in fake_http["calls"])


class TestGitHubErrors:
    def test_rate_limit_becomes_a_gap_with_reset_time(self, fake_http):
        fake_http["routes"]["/repos/o/r"] = _http_error(
            403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1767225600"}
        )

        result = reads.run("github_repo", repo="o/r")

        assert result["ok"] is False
        assert result["gap"]["type"] == "rate_limited"
        assert "2026-01-01T00:00:00Z" in result["gap"]["reason"]
        assert result["error"] is None

    def test_missing_resource_becomes_not_found(self, fake_http):
        fake_http["routes"]["/repos/o/r"] = _http_error(404)

        result = reads.run("github_repo", repo="o/r")

        assert result["gap"]["type"] == "not_found"

    def test_network_failure_is_an_error(self, fake_http):
        fake_http["routes"]["/repos/o/r"] = urllib.error.URLError("no route to host")

        result = reads.run("github_repo", repo="o/r")

        assert result["error"]["type"] == "network_error"
        assert result["gap"] is None

    def test_timeout_is_reported_as_timeout(self, fake_http):
        fake_http["routes"]["/repos/o/r"] = urllib.error.URLError(TimeoutError("slow"))

        assert reads.run("github_repo", repo="o/r")["error"]["type"] == "timeout"

    def test_bad_repo_is_rejected_before_any_request(self, fake_http):
        result = reads.run("github_repo", repo="not-a-repo")

        assert result["error"]["type"] == "invalid_input"
        assert fake_http["calls"] == []


# ── RSS / Atom ──────────────────────────────────────


RSS_FEED = """<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Example feed</title>
    <link>https://example.com/</link>
    <lastBuildDate>Mon, 05 Jan 2026 10:00:00 +0000</lastBuildDate>
    <item>
      <guid>https://example.com/a</guid>
      <title>First</title>
      <link>https://example.com/a</link>
      <pubDate>Mon, 05 Jan 2026 09:00:00 +0000</pubDate>
      <dc:creator>Ada</dc:creator>
      <description>About the first</description>
    </item>
    <item>
      <guid>https://example.com/b</guid>
      <title>Second</title>
      <link>https://example.com/b</link>
      <pubDate>Mon, 05 Jan 2026 08:00:00 +0000</pubDate>
      <description>About the second</description>
    </item>
  </channel>
</rss>
"""

ATOM_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom example</title>
  <link href="https://example.org/" rel="alternate"/>
  <updated>2026-01-05T10:00:00Z</updated>
  <entry>
    <id>tag:example.org,2026:1</id>
    <title>Atom first</title>
    <link href="https://example.org/1" rel="alternate"/>
    <published>2026-01-05T09:00:00Z</published>
    <updated>2026-01-05T09:30:00Z</updated>
    <author><name>Grace</name></author>
    <summary>Atom summary</summary>
  </entry>
</feed>
"""


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(
        reads.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [(2, 1, 6, "", ("93.184.216.34", port))],
    )


class TestRSS:
    def test_parses_rss_two_point_zero(self, fake_http, public_dns):
        fake_http["routes"]["example.com"] = _FakeResponse(RSS_FEED.encode("utf-8"))

        result = reads.run("rss_feed", url="https://example.com/feed.xml")

        assert result["backend"] == "xml.etree"
        data = result["data"]
        assert data["format"] == "rss"
        assert data["title"] == "Example feed"
        assert data["link"] == "https://example.com/"
        assert data["updated"] == "Mon, 05 Jan 2026 10:00:00 +0000"
        assert data["entries_total"] == 2
        assert data["entries_returned"] == 2
        assert data["partial"] is False
        first = data["entries"][0]
        assert first["id"] == "https://example.com/a"
        assert first["title"] == "First"
        assert first["author"] == "Ada"
        assert first["published"] == "Mon, 05 Jan 2026 09:00:00 +0000"
        assert first["summary"] == "About the first"

    def test_limit_marks_the_result_partial(self, fake_http, public_dns):
        fake_http["routes"]["example.com"] = _FakeResponse(RSS_FEED.encode("utf-8"))

        data = reads.run("rss_feed", url="https://example.com/feed.xml", limit=1)["data"]

        assert data["entries_returned"] == 1
        assert data["entries_total"] == 2
        assert data["partial"] is True

    def test_parses_atom(self, fake_http, public_dns):
        fake_http["routes"]["example.org"] = _FakeResponse(ATOM_FEED.encode("utf-8"))

        data = reads.run("rss_feed", url="https://example.org/feed")["data"]

        assert data["format"] == "atom"
        assert data["title"] == "Atom example"
        assert data["link"] == "https://example.org/"
        assert data["updated"] == "2026-01-05T10:00:00Z"
        entry = data["entries"][0]
        assert entry["id"] == "tag:example.org,2026:1"
        assert entry["link"] == "https://example.org/1"
        assert entry["author"] == "Grace"
        assert entry["updated"] == "2026-01-05T09:30:00Z"
        assert entry["summary"] == "Atom summary"

    def test_doctype_payload_is_refused(self, fake_http, public_dns):
        bomb = (
            '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "AA">]>'
            "<rss version=\"2.0\"><channel><title>&a;</title></channel></rss>"
        )
        fake_http["routes"]["example.com"] = _FakeResponse(bomb.encode("utf-8"))

        result = reads.run("rss_feed", url="https://example.com/feed.xml")

        assert result["error"]["type"] == "parse_error"


# ── URL validation ──────────────────────────────────


class TestUrlValidation:
    def test_http_feed_is_rejected(self, fake_http):
        result = reads.run("rss_feed", url="http://example.com/feed.xml")

        assert result["error"]["type"] == "invalid_input"
        assert fake_http["calls"] == []

    def test_private_feed_host_is_rejected_by_resolved_address(self, fake_http, monkeypatch):
        monkeypatch.setattr(
            reads.socket,
            "getaddrinfo",
            lambda host, port, **kwargs: [(2, 1, 6, "", ("127.0.0.1", port))],
        )

        result = reads.run("rss_feed", url="https://internal.example.com/feed.xml")

        assert result["error"]["type"] == "invalid_input"
        assert "non-public" in result["error"]["message"]
        assert fake_http["calls"] == []

    def test_literal_private_feed_host_is_rejected(self, fake_http):
        result = reads.run("rss_feed", url="https://10.0.0.5/feed.xml")

        assert result["error"]["type"] == "invalid_input"
        assert fake_http["calls"] == []

    def test_youtube_host_allowlist(self, fake_yt_dlp):
        result = reads.run("youtube_transcript", url="https://vimeo.com/watch?v=abcdefghijk")

        assert result["error"]["type"] == "invalid_input"
        assert fake_yt_dlp["commands"] == []

    def test_youtube_http_url_is_rejected(self, fake_yt_dlp):
        result = reads.run("youtube_transcript", url="http://www.youtube.com/watch?v=abcdefghijk")

        assert result["error"]["type"] == "invalid_input"
        assert fake_yt_dlp["commands"] == []


# ── YouTube ─────────────────────────────────────────


class TestYouTube:
    def _metadata(self, manual=None, automatic=None):
        return {
            "id": "abcdefghijk",
            "title": "A talk",
            "channel": "Some channel",
            "upload_date": "20260101",
            "duration": 14.0,
            "language": "en-US",
            "subtitles": manual or {},
            "automatic_captions": automatic or {},
        }

    def test_manual_track_parsing_coverage_and_dedup(self, fake_yt_dlp):
        fake_yt_dlp["metadata"] = self._metadata(manual={"en": [{"ext": "vtt"}]})
        fake_yt_dlp["vtt"] = VTT_WITH_GAP_AND_DUPES

        result = reads.run("youtube_transcript", url="https://www.youtube.com/watch?v=abcdefghijk")

        assert result["ok"] is True
        data = result["data"]
        assert data["url"] == "https://www.youtube.com/watch?v=abcdefghijk"
        assert data["title"] == "A talk"
        assert data["channel"] == "Some channel"
        assert data["duration_s"] == 14.0
        transcript = data["transcript"]
        assert transcript["language"] == "en"
        assert transcript["origin"] == "manual"
        assert [s["text"] for s in transcript["segments"]] == [
            "hello world",
            "second & line",
            "after the gap",
        ]
        assert transcript["segments"][0] == {
            "start_s": 1.0,
            "end_s": 3.0,
            "text": "hello world",
        }
        assert transcript["coverage"]["gaps"] == [{"from_s": 5.0, "to_s": 12.0}]
        assert transcript["coverage"]["first_start_s"] == 1.0
        assert transcript["coverage"]["last_end_s"] == 14.0
        assert transcript["transformation"] == [
            "vtt-parsed",
            "overlapping auto-caption lines deduplicated",
        ]
        assert data["partial"] is True

    def test_automatic_track_is_reported_as_automatic(self, fake_yt_dlp):
        fake_yt_dlp["metadata"] = self._metadata(automatic={"en": [{"ext": "vtt"}]})
        fake_yt_dlp["vtt"] = VTT_WITH_GAP_AND_DUPES

        transcript = reads.run(
            "youtube_transcript", url="https://youtu.be/abcdefghijk"
        )["data"]["transcript"]

        assert transcript["origin"] == "automatic"
        assert transcript["language"] == "en"

    def test_manual_track_wins_over_automatic(self, fake_yt_dlp):
        fake_yt_dlp["metadata"] = self._metadata(
            manual={"en": [{"ext": "vtt"}]}, automatic={"en": [{"ext": "vtt"}]}
        )
        fake_yt_dlp["vtt"] = VTT_WITH_GAP_AND_DUPES

        transcript = reads.run(
            "youtube_transcript", url="https://www.youtube.com/watch?v=abcdefghijk"
        )["data"]["transcript"]

        assert transcript["origin"] == "manual"

    def test_absent_transcript_is_an_access_gap(self, fake_yt_dlp):
        fake_yt_dlp["metadata"] = self._metadata()

        result = reads.run(
            "youtube_transcript", url="https://www.youtube.com/watch?v=abcdefghijk", lang="ja"
        )

        assert result["ok"] is False
        assert result["error"] is None
        assert result["gap"] == {
            "type": "access_gap",
            "reason": "no manual or automatic transcript available for ja",
        }

    def test_missing_backend_is_reported_never_installed(self, monkeypatch):
        monkeypatch.setattr(reads.shutil, "which", lambda name: None)

        def explode(*_args, **_kwargs):
            raise AssertionError("no process may run when the backend is missing")

        monkeypatch.setattr(reads.subprocess, "run", explode)

        result = reads.run("youtube_transcript", url="https://www.youtube.com/watch?v=abcdefghijk")

        assert result["gap"]["type"] == "backend_unavailable"
        assert "yt-dlp is not installed" in result["gap"]["reason"]

    def test_rate_limited_backend_becomes_a_gap(self, fake_yt_dlp):
        fake_yt_dlp["metadata"] = self._metadata(manual={"en": [{"ext": "vtt"}]})
        fake_yt_dlp["returncode"] = 1
        fake_yt_dlp["stderr"] = "ERROR: HTTP Error 429: Too Many Requests"

        result = reads.run("youtube_transcript", url="https://www.youtube.com/watch?v=abcdefghijk")

        assert result["gap"]["type"] == "rate_limited"

    def test_child_environment_is_scrubbed(self, fake_yt_dlp, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "gh-secret")
        monkeypatch.setenv("GITHUB_TOKEN", "gh-secret")
        monkeypatch.setenv("X_API_KEY", "api-secret")
        monkeypatch.setenv("MY_SECRET", "shh")
        monkeypatch.setenv("MY_PASSWORD", "shh")
        monkeypatch.setenv("COOKIES", "sid=1")
        monkeypatch.setenv("BROWSER_COOKIE", "sid=1")
        monkeypatch.setenv("PATH", "/usr/bin")
        fake_yt_dlp["metadata"] = self._metadata(manual={"en": [{"ext": "vtt"}]})
        fake_yt_dlp["vtt"] = VTT_WITH_GAP_AND_DUPES

        reads.run("youtube_transcript", url="https://www.youtube.com/watch?v=abcdefghijk")

        assert fake_yt_dlp["envs"], "yt-dlp was never invoked"
        for env in fake_yt_dlp["envs"]:
            for banned in (
                "GH_TOKEN",
                "GITHUB_TOKEN",
                "X_API_KEY",
                "MY_SECRET",
                "MY_PASSWORD",
                "COOKIES",
                "BROWSER_COOKIE",
            ):
                assert banned not in env
            assert "gh-secret" not in env.values()
            assert env["PATH"] == "/usr/bin"

    def test_no_cookie_flags_are_ever_passed(self, fake_yt_dlp):
        fake_yt_dlp["metadata"] = self._metadata(manual={"en": [{"ext": "vtt"}]})
        fake_yt_dlp["vtt"] = VTT_WITH_GAP_AND_DUPES

        reads.run("youtube_transcript", url="https://www.youtube.com/watch?v=abcdefghijk")

        flattened = " ".join(" ".join(command) for command in fake_yt_dlp["commands"])
        assert "--cookies" not in flattened
        assert "--skip-download" in flattened
        assert "--username" not in flattened


class TestVttParser:
    def test_timestamps_and_deduplication(self):
        segments, removed = reads.parse_vtt(VTT_WITH_GAP_AND_DUPES)

        assert removed == 1
        assert segments[1] == {"start_s": 3.0, "end_s": 5.0, "text": "second & line"}

    def test_hour_and_comma_timestamps(self):
        segments, _removed = reads.parse_vtt(
            "WEBVTT\n\n01:02:03,500 --> 01:02:04,000\nlate line\n"
        )

        assert segments == [{"start_s": 3723.5, "end_s": 3724.0, "text": "late line"}]


# ── status ──────────────────────────────────────────


class TestStatus:
    @pytest.fixture(autouse=True)
    def _stub_youtube_channel(self, monkeypatch):
        from agent_reach.channels.youtube import YouTubeChannel

        monkeypatch.setattr(
            YouTubeChannel, "check", lambda self, config=None: ("ok", "可提取视频信息和字幕")
        )

    def test_authorization_and_last_success_belong_to_the_plugin(self):
        result = reads.run("status")

        assert result["ok"] is True
        operations = result["data"]["operations"]
        assert set(operations) == {
            "github_repo",
            "github_issue",
            "github_readme",
            "rss_feed",
            "youtube_transcript",
        }
        for name, entry in operations.items():
            assert entry["authorized"] is False, name
            assert entry["last_success"] is None, name
            assert entry["environment"] in ("headless", "desktop")
            assert entry["check_time"].endswith("Z")
            assert entry["notes"]

    def test_installed_does_not_imply_authenticated(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setattr(reads, "_github_credentials_present", lambda: False)

        operations = reads.run("status")["data"]["operations"]

        assert operations["github_repo"]["installed"] is True
        assert operations["github_repo"]["authenticated"] is False
        assert operations["rss_feed"]["authenticated"] is None

    def test_token_presence_is_informational_only(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "gh-secret")

        operations = reads.run("status")["data"]["operations"]

        assert operations["github_issue"]["authenticated"] is True
        assert operations["github_issue"]["authorized"] is False

    def test_missing_yt_dlp_is_reported_not_installed(self, monkeypatch):
        from agent_reach.channels.youtube import YouTubeChannel

        monkeypatch.setattr(
            YouTubeChannel, "check", lambda self, config=None: ("off", "yt-dlp 未安装")
        )

        entry = reads.run("status")["data"]["operations"]["youtube_transcript"]

        assert entry["installed"] is False
        assert entry["configured"] is False


# ── envelope and CLI ────────────────────────────────


class TestEnvelope:
    def test_shape_is_stable_for_every_result(self, fake_http):
        fake_http["routes"]["/repos/o/r"] = _http_error(404)

        result = reads.run("github_repo", repo="o/r")

        assert set(result) == {
            "ok",
            "op",
            "backend",
            "checked_at",
            "environment",
            "elapsed_ms",
            "data",
            "error",
            "gap",
        }
        assert result["checked_at"].endswith("Z")
        assert isinstance(result["elapsed_ms"], int)
        assert result["environment"] in ("headless", "desktop")

    def test_unknown_operation_is_invalid_input(self):
        result = reads.run("delete_everything")

        assert result["ok"] is False
        assert result["error"]["type"] == "invalid_input"


class TestReadCommand:
    def test_prints_one_json_object_and_exits_zero(self, capsys):
        envelope = {
            "ok": True,
            "op": "status",
            "backend": "local",
            "checked_at": "2026-01-01T00:00:00Z",
            "environment": "headless",
            "elapsed_ms": 2,
            "data": {"operations": {}},
            "error": None,
            "gap": None,
        }
        with patch("agent_reach.hermes.reads.run", return_value=envelope), patch(
            "sys.argv", ["agent-reach", "read", "status", "--json"]
        ), pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 0
        assert json.loads(capsys.readouterr().out) == envelope

    def test_exits_one_when_the_read_did_not_succeed(self, capsys):
        envelope = {
            "ok": False,
            "op": "github_repo",
            "backend": "github-rest",
            "checked_at": "2026-01-01T00:00:00Z",
            "environment": "headless",
            "elapsed_ms": 1,
            "data": None,
            "error": None,
            "gap": {"type": "not_found", "reason": "gone"},
        }
        with patch("agent_reach.hermes.reads.run", return_value=envelope), patch(
            "sys.argv", ["agent-reach", "read", "github_repo", "--repo", "o/r", "--json"]
        ), pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 1
        assert json.loads(capsys.readouterr().out)["gap"]["type"] == "not_found"


class TestMaintenanceBoundary:
    def test_module_never_names_an_install_command(self):
        source = Path(reads.__file__).read_text(encoding="utf-8")

        for forbidden in ("pip install", "uv tool", "brew ", "gh auth"):
            assert forbidden not in source, forbidden



def test_http_redirects_are_refused_before_any_second_request(monkeypatch):
    """A public host that redirects to a private or foreign address must not be followed (SSRF via redirect)."""
    handler = reads._NoRedirect()
    with pytest.raises(reads.ReadError) as info:
        handler.redirect_request(None, None, 302, "Found", {}, "https://169.254.169.254/latest/meta-data")
    assert info.value.error_type == "invalid_input"
    assert "169.254.169.254" in str(info.value)
    assert "not followed" in str(info.value)

    calls = []

    def opener_open(request, timeout=None):
        calls.append(request.full_url)
        raise reads.ReadError("invalid_input", "HTTP 301 redirect to evil.example refused: redirects are not followed")

    monkeypatch.setattr(reads._OPENER, "open", opener_open)
    with pytest.raises(reads.ReadError) as info:
        reads._http_get("https://api.github.com/repos/x/y", timeout=5, accept="application/json")
    assert info.value.error_type == "invalid_input"
    assert calls == ["https://api.github.com/repos/x/y"]
