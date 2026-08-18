import json
import http.client
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


from scripts.build_site_data import (
    _request_json,
    aggregate_star_history,
    build_repository_stats,
    fetch_github_data,
    render_star_history_svg,
    write_site_data,
)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = json.dumps(payload).encode()
        self.headers = {"X-Test": "ok"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self._payload


class RawResponse(FakeResponse):
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.headers = {}


class SiteDataTests(unittest.TestCase):
    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_github_requests_use_the_current_api_contract(
        self, urlopen: mock.Mock
    ) -> None:
        urlopen.return_value = FakeResponse({"ok": True})

        _request_json(
            "https://api.github.test/repo", None, "application/vnd.github+json"
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header("X-github-api-version"), "2026-03-10"
        )

    @mock.patch("scripts.build_site_data.time.sleep", return_value=None)
    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_github_request_retries_rate_limit_then_fails(
        self, urlopen: mock.Mock, _sleep: mock.Mock
    ) -> None:
        urlopen.side_effect = urllib.error.URLError("HTTP 429 rate limited")

        with self.assertRaisesRegex(RuntimeError, "GitHub API request failed"):
            _request_json("https://api.github.test/repo", None, "application/json")

        self.assertEqual(urlopen.call_count, 3)

    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_github_request_rejects_malformed_json_without_retry(
        self, urlopen: mock.Mock
    ) -> None:
        urlopen.return_value = RawResponse(b"not-json")

        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            _request_json("https://api.github.test/repo", None, "application/json")

        self.assertEqual(urlopen.call_count, 1)

    @mock.patch("scripts.build_site_data.time.sleep", return_value=None)
    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_unauthenticated_history_failure_keeps_repository_stats(
        self, urlopen: mock.Mock, _sleep: mock.Mock
    ) -> None:
        repository = {
            "full_name": "aAAaqwq/AGI-Super-Team",
            "stargazers_count": 78,
            "forks_count": 18,
        }
        history_url = (
            "https://api.github.com/repos/aAAaqwq/AGI-Super-Team/"
            "stargazers?per_page=100"
        )
        urlopen.side_effect = [
            FakeResponse(repository),
            urllib.error.HTTPError(
                history_url, 401, "authentication required", None, None
            ),
        ]

        payload, stargazers = fetch_github_data("aAAaqwq/AGI-Super-Team", None)

        self.assertEqual(payload, repository)
        self.assertEqual(stargazers, [])

    @mock.patch("scripts.build_site_data.time.sleep", return_value=None)
    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_authenticated_history_http_unavailability_keeps_repository_stats(
        self, urlopen: mock.Mock, _sleep: mock.Mock
    ) -> None:
        repository = {
            "full_name": "aAAaqwq/AGI-Super-Team",
            "stargazers_count": 78,
            "forks_count": 18,
        }
        history_url = (
            "https://api.github.com/repos/aAAaqwq/AGI-Super-Team/"
            "stargazers?per_page=100"
        )

        for status_code in (401, 403, 429, 500, 503):
            with self.subTest(status_code=status_code):
                urlopen.reset_mock()
                failure_count = 3 if status_code == 429 or status_code >= 500 else 1
                failures = [
                    urllib.error.HTTPError(
                        history_url, status_code, "history unavailable", None, None
                    )
                    for _ in range(failure_count)
                ]
                urlopen.side_effect = [FakeResponse(repository), *failures]

                payload, stargazers = fetch_github_data(
                    "aAAaqwq/AGI-Super-Team", "workflow-token"
                )

                self.assertEqual(payload, repository)
                self.assertEqual(stargazers, [])

    @mock.patch("scripts.build_site_data.time.sleep", return_value=None)
    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_unexpected_history_http_error_is_not_silenced(
        self, urlopen: mock.Mock, _sleep: mock.Mock
    ) -> None:
        repository = {
            "full_name": "aAAaqwq/AGI-Super-Team",
            "stargazers_count": 78,
            "forks_count": 18,
        }
        history_url = (
            "https://api.github.com/repos/aAAaqwq/AGI-Super-Team/"
            "stargazers?per_page=100"
        )
        urlopen.side_effect = [
            FakeResponse(repository),
            urllib.error.HTTPError(history_url, 404, "not found", None, None),
        ]

        with self.assertRaisesRegex(RuntimeError, "HTTP 404"):
            fetch_github_data("aAAaqwq/AGI-Super-Team", "workflow-token")

    @mock.patch("scripts.build_site_data.time.sleep", return_value=None)
    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_authenticated_transient_history_failure_keeps_repository_stats(
        self, urlopen: mock.Mock, _sleep: mock.Mock
    ) -> None:
        repository = {
            "full_name": "aAAaqwq/AGI-Super-Team",
            "stargazers_count": 78,
            "forks_count": 18,
        }
        urlopen.side_effect = [
            FakeResponse(repository),
            http.client.RemoteDisconnected("transient"),
            http.client.RemoteDisconnected("transient"),
            http.client.RemoteDisconnected("transient"),
        ]

        payload, stargazers = fetch_github_data(
            "aAAaqwq/AGI-Super-Team", "workflow-token"
        )

        self.assertEqual(payload, repository)
        self.assertEqual(stargazers, [])

    @mock.patch("scripts.build_site_data._request_json")
    def test_malformed_authenticated_history_is_not_silenced(
        self, request_json: mock.Mock
    ) -> None:
        repository = {
            "full_name": "aAAaqwq/AGI-Super-Team",
            "stargazers_count": 78,
            "forks_count": 18,
        }
        request_json.side_effect = [
            (repository, {}),
            RuntimeError("GitHub API returned invalid JSON"),
        ]

        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            fetch_github_data("aAAaqwq/AGI-Super-Team", "workflow-token")

    @mock.patch("scripts.build_site_data._request_json")
    def test_malformed_stargazer_payload_is_not_silenced(
        self, request_json: mock.Mock
    ) -> None:
        repository = {
            "full_name": "aAAaqwq/AGI-Super-Team",
            "stargazers_count": 78,
            "forks_count": 18,
        }
        request_json.side_effect = [
            (repository, {}),
            ({"unexpected": "object"}, {}),
        ]

        with self.assertRaisesRegex(RuntimeError, "was not a list"):
            fetch_github_data("aAAaqwq/AGI-Super-Team", "workflow-token")

    @mock.patch("scripts.build_site_data.time.sleep", return_value=None)
    @mock.patch("scripts.build_site_data.urllib.request.urlopen")
    def test_github_request_retries_transient_disconnect(
        self, urlopen: mock.Mock, _sleep: mock.Mock
    ) -> None:
        urlopen.side_effect = [
            http.client.RemoteDisconnected("transient"),
            FakeResponse({"ok": True}),
        ]

        payload, headers = _request_json(
            "https://api.github.test/repo", None, "application/json"
        )

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(headers["x-test"], "ok")
        self.assertEqual(urlopen.call_count, 2)

    def test_repository_stats_rejects_wrong_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository identity"):
            build_repository_stats(
                "aAAaqwq/AGI-Super-Team",
                {"full_name": "someone/else", "stargazers_count": 12, "forks_count": 3},
                datetime(2026, 7, 21, tzinfo=timezone.utc),
            )

    def test_repository_stats_rejects_negative_or_boolean_counts(self) -> None:
        invalid_values = (-1, True, "78")
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "non-negative integer"):
                    build_repository_stats(
                        "aAAaqwq/AGI-Super-Team",
                        {
                            "full_name": "aAAaqwq/AGI-Super-Team",
                            "stargazers_count": value,
                            "forks_count": 18,
                        },
                        datetime(2026, 7, 21, tzinfo=timezone.utc),
                    )

    def test_star_history_aggregates_same_day_and_sorts_dates(self) -> None:
        history = aggregate_star_history(
            "aAAaqwq/AGI-Super-Team",
            [
                {"starred_at": "2026-07-20T17:00:00Z"},
                {"starred_at": "2026-07-19T02:00:00Z"},
                {"starred_at": "2026-07-20T01:00:00Z"},
            ],
            datetime(2026, 7, 21, tzinfo=timezone.utc),
        )

        self.assertEqual(
            history["points"],
            [
                {"date": "2026-07-19", "stars": 1},
                {"date": "2026-07-20", "stars": 3},
            ],
        )
        self.assertEqual(history["latestStars"], 3)
        self.assertNotIn("login", json.dumps(history))
        self.assertNotIn("private-identity", json.dumps(history))

    def test_star_history_rejects_missing_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "starred_at"):
            aggregate_star_history(
                "aAAaqwq/AGI-Super-Team",
                [{"login": "private-identity"}],
                datetime(2026, 7, 21, tzinfo=timezone.utc),
            )

    def test_svg_contains_accessible_description_and_escaped_repository(self) -> None:
        svg = render_star_history_svg(
            {
                "repository": "owner/<unsafe>&repo",
                "generatedAt": "2026-07-21T00:00:00Z",
                "latestStars": 2,
                "points": [
                    {"date": "2026-07-19", "stars": 1},
                    {"date": "2026-07-20", "stars": 2},
                ],
            }
        )

        self.assertIn('<title id="title">AGI Super Team star history</title>', svg)
        self.assertIn('<desc id="desc">', svg)
        self.assertIn("owner/&lt;unsafe&gt;&amp;repo", svg)
        self.assertNotIn("owner/<unsafe>&repo", svg)

    def test_svg_marks_history_refresh_pending_when_only_current_count_exists(self) -> None:
        svg = render_star_history_svg(
            {
                "repository": "aAAaqwq/AGI-Super-Team",
                "latestStars": 78,
                "points": [],
            }
        )

        self.assertIn("History refresh pending", svg)
        self.assertNotIn("No stars yet", svg)

    def test_write_site_data_creates_versioned_json_and_svg(self) -> None:
        generated_at = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
        repository_payload = {
            "full_name": "aAAaqwq/AGI-Super-Team",
            "stargazers_count": 78,
            "forks_count": 18,
        }
        stargazers = [
            {"starred_at": "2026-07-19T02:00:00Z"},
            {"starred_at": "2026-07-20T17:00:00Z"},
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            docs_directory = Path(temporary_directory)
            write_site_data(
                docs_directory,
                "aAAaqwq/AGI-Super-Team",
                repository_payload,
                stargazers,
                generated_at,
            )
            stats = json.loads((docs_directory / "data/repo-stats.json").read_text())
            history = json.loads((docs_directory / "data/star-history.json").read_text())
            svg = (docs_directory / "assets/star-history.svg").read_text()

        self.assertEqual(stats["schemaVersion"], 1)
        self.assertEqual(stats["stars"], 78)
        self.assertEqual(stats["forks"], 18)
        self.assertEqual(history["schemaVersion"], 1)
        self.assertEqual(history["latestStars"], 78)
        self.assertIn("Latest count: 78 stars", svg)


if __name__ == "__main__":
    unittest.main()
