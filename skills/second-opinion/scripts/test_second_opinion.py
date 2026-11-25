"""Unit tests for the pure parts of second_opinion.py (stdlib unittest).

Run: python -m unittest discover -s skills/second-opinion/scripts -v
No test makes a network call; the guard test asserts urlopen is never reached.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import second_opinion as so


def make_main_repo(root: Path, name: str) -> Path:
    repo = root / name
    (repo / ".git" / "worktrees").mkdir(parents=True)
    return repo


def make_worktree(main_repo: Path, wt_path: Path, wt_name: str) -> Path:
    """Lay out a linked worktree the way git does: a .git FILE plus commondir."""
    gitdir = main_repo / ".git" / "worktrees" / wt_name
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    wt_path.mkdir(parents=True)
    (wt_path / ".git").write_text(f"gitdir: {gitdir.as_posix()}\n", encoding="utf-8")
    return wt_path


class RepoResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_plain_repo_resolves_to_itself(self) -> None:
        repo = make_main_repo(self.root, "outer_heaven")
        (repo / "skills").mkdir()
        info = so.find_repo(repo / "skills")
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "outer_heaven")

    def test_worktree_resolves_to_main_repo(self) -> None:
        main = make_main_repo(self.root, "outer_heaven")
        wt = make_worktree(main, main / ".claude" / "worktrees" / "agent-x", "agent-x")
        info = so.find_repo(wt)
        self.assertEqual(info.name, "outer_heaven")
        self.assertEqual(info.worktree_root, wt)

    def test_worktree_without_commondir_uses_gitdir_path(self) -> None:
        main = make_main_repo(self.root, "datavilla")
        wt = make_worktree(main, self.root / "elsewhere" / "wt", "wt")
        (main / ".git" / "worktrees" / "wt" / "commondir").unlink()
        self.assertEqual(so.find_repo(wt).name, "datavilla")

    def test_file_path_inside_repo(self) -> None:
        repo = make_main_repo(self.root, "command-deck")
        f = repo / "a" / "b.md"
        f.parent.mkdir()
        f.write_text("x", encoding="utf-8")
        self.assertEqual(so.find_repo(f).name, "command-deck")

    def test_outside_any_repo_is_none(self) -> None:
        (self.root / "loose").mkdir()
        self.assertIsNone(so.find_repo(self.root / "loose"))

    def test_real_worktree_resolves_to_outer_heaven(self) -> None:
        here = Path(__file__).resolve()
        info = so.find_repo(here)
        self.assertIsNotNone(info)
        self.assertEqual(info.name, "outer_heaven")


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.owned = make_main_repo(self.root, "outer_heaven")
        self.other = make_main_repo(self.root, "some-customer-repo")
        self.loose = self.root / "loose"
        self.loose.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_owned_repo_allowed(self) -> None:
        self.assertEqual(so.check_guard(self.owned, [], customer_approved=False), [])

    def test_allowlist_is_case_insensitive(self) -> None:
        repo = make_main_repo(self.root, "Datavilla")
        self.assertTrue(so.is_owned(so.find_repo(repo)))

    def test_unknown_repo_refused(self) -> None:
        reasons = so.check_guard(self.other, [], customer_approved=False)
        self.assertEqual(len(reasons), 1)
        self.assertIn("some-customer-repo", reasons[0])

    def test_outside_repo_refused(self) -> None:
        reasons = so.check_guard(self.loose, [], customer_approved=False)
        self.assertIn("not inside any git repo", reasons[0])

    def test_input_file_in_other_repo_refused_even_from_owned_source(self) -> None:
        f = self.other / "x.py"
        f.write_text("x", encoding="utf-8")
        reasons = so.check_guard(self.owned, [f], customer_approved=False)
        self.assertEqual(len(reasons), 1)
        self.assertIn("some-customer-repo", reasons[0])

    def test_worktree_named_like_owned_but_main_is_not(self) -> None:
        wt = make_worktree(self.other, self.root / "wts" / "outer_heaven", "outer_heaven")
        self.assertFalse(so.is_owned(so.find_repo(wt)))

    def test_refusal_makes_no_network_call(self) -> None:
        args = [
            "--requirements-text", "r",
            "--files", str(Path(__file__).resolve()),
            "--source-repo", str(self.other),
        ]
        err = io.StringIO()
        with mock.patch.object(so.urllib.request, "urlopen") as urlopen, \
                mock.patch.object(so, "get_api_key") as get_key, redirect_stderr(err):
            code = so.main(args)
        self.assertEqual(code, 2)
        urlopen.assert_not_called()
        get_key.assert_not_called()
        self.assertIn("REFUSED", err.getvalue())

    def test_approval_flag_lets_run_through(self) -> None:
        f = self.other / "x.py"
        f.write_text("print(1)\n", encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        args = ["--requirements-text", "r", "--files", str(f), "--source-repo", str(self.other),
                "--customer-approved", "--dry-run"]
        with mock.patch.object(so.urllib.request, "urlopen") as urlopen, \
                redirect_stdout(out), redirect_stderr(err):
            code = so.main(args)
        self.assertEqual(code, 0)
        urlopen.assert_not_called()
        self.assertIn("overridden by --customer-approved", err.getvalue())


class CliTests(unittest.TestCase):
    def test_empty_inline_requirements_do_not_crash(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        here = str(Path(__file__).resolve())
        with redirect_stdout(out), redirect_stderr(err):
            code = so.main(["--requirements-text", "", "--files", here, "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("(none given)", out.getvalue())

    def _dry_run(self, *extra: str) -> tuple[int, dict, str]:
        out, err = io.StringIO(), io.StringIO()
        here = str(Path(__file__).resolve())
        argv = ["--requirements-text", "r", "--files", here, "--dry-run", *extra]
        with mock.patch.object(so.urllib.request, "urlopen") as urlopen, \
                mock.patch.object(so, "get_api_key") as get_key, \
                redirect_stdout(out), redirect_stderr(err):
            code = so.main(argv)
        urlopen.assert_not_called()
        get_key.assert_not_called()
        return code, json.loads(out.getvalue()), err.getvalue()

    def test_thinking_level_reaches_dry_run_body(self) -> None:
        code, body, err = self._dry_run("--thinking-level", "low")
        self.assertEqual(code, 0)
        self.assertEqual(body["generationConfig"]["thinkingConfig"], {"thinkingLevel": "LOW"})
        self.assertIn("thinking_level=low", err)

    def test_no_thinking_level_means_no_thinking_config(self) -> None:
        code, body, err = self._dry_run()
        self.assertEqual(code, 0)
        self.assertNotIn("thinkingConfig", body["generationConfig"])
        self.assertNotIn("thinking_level", err)

    def test_invalid_thinking_level_rejected_by_argparse(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            so.parse_args(["--requirements-text", "r", "--thinking-level", "extreme"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("invalid choice", err.getvalue())

    def test_uppercase_thinking_level_rejected_by_argparse(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            so.parse_args(["--requirements-text", "r", "--thinking-level", "LOW"])


class ResponseParsingTests(unittest.TestCase):
    def _response(self, text: str, **extra: object) -> dict:
        resp = {
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "modelVersion": "gemini-test",
            "usageMetadata": {"promptTokenCount": 10, "thoughtsTokenCount": 20,
                              "candidatesTokenCount": 5, "totalTokenCount": 35},
        }
        resp.update(extra)
        return resp

    def test_parses_findings(self) -> None:
        body = {"verdict": "approve", "summary": "ok", "findings": [{"severity": "nit"}]}
        answer = so.parse_findings(self._response(json.dumps(body)))
        self.assertEqual(answer["verdict"], "approve")
        self.assertEqual(len(answer["findings"]), 1)

    def test_thought_parts_are_skipped(self) -> None:
        resp = self._response(json.dumps({"verdict": "approve", "summary": "", "findings": []}))
        resp["candidates"][0]["content"]["parts"].insert(0, {"text": "thinking...", "thought": True})
        self.assertEqual(so.parse_findings(resp)["findings"], [])

    def test_invalid_json_raises(self) -> None:
        with self.assertRaises(so.SecondOpinionError) as ctx:
            so.parse_findings(self._response("not json"))
        self.assertIn("finishReason: STOP", str(ctx.exception))

    def test_missing_findings_raises(self) -> None:
        with self.assertRaises(so.SecondOpinionError):
            so.parse_findings(self._response(json.dumps({"verdict": "approve"})))

    def test_blocked_prompt_raises(self) -> None:
        with self.assertRaises(so.SecondOpinionError) as ctx:
            so.parse_findings({"promptFeedback": {"blockReason": "SAFETY"}})
        self.assertIn("SAFETY", str(ctx.exception))

    def test_usage_lines(self) -> None:
        lines = so.usage_lines(self._response("{}"))
        self.assertEqual(lines[0], "model version: gemini-test")
        self.assertEqual(
            lines[1],
            "usage: promptTokenCount=10 thoughtsTokenCount=20 candidatesTokenCount=5 totalTokenCount=35",
        )

    def test_google_error_message(self) -> None:
        body = json.dumps({"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})
        self.assertEqual(so.google_error_message(body.encode()), "INVALID_ARGUMENT bad")

    def test_redact(self) -> None:
        self.assertEqual(so.redact("key=SECRET123 end", "SECRET123"), "key=*** end")

    def test_payload_has_no_key_and_requests_json(self) -> None:
        payload = so.build_payload("prompt", use_schema=True)
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("responseSchema", payload["generationConfig"])
        self.assertNotIn("responseSchema", so.build_payload("p", use_schema=False)["generationConfig"])

    def test_payload_with_thinking_level(self) -> None:
        for level in so.THINKING_LEVELS:
            with self.subTest(level=level):
                config = so.build_payload("p", use_schema=True, thinking_level=level)["generationConfig"]
                self.assertEqual(config["thinkingConfig"], {"thinkingLevel": level.upper()})
                self.assertEqual(config["responseMimeType"], "application/json")
                self.assertIn("responseSchema", config)

    def test_payload_without_thinking_level_has_no_thinking_config(self) -> None:
        for payload in (
            so.build_payload("p", use_schema=True),
            so.build_payload("p", use_schema=True, thinking_level=None),
        ):
            self.assertNotIn("thinkingConfig", payload["generationConfig"])
        self.assertEqual(
            so.build_payload("p", use_schema=True),
            so.build_payload("p", use_schema=True, thinking_level=None),
        )

    def _call_with_urlopen_raising(self, exc: Exception) -> str:
        with mock.patch.object(so.urllib.request, "urlopen", side_effect=exc):
            with self.assertRaises(so.SecondOpinionError) as ctx:
                so.call_gemini("model-x", {}, "NOT-A-REAL-KEY", 7)
        return str(ctx.exception)

    def test_bare_timeout_gives_timeout_message(self) -> None:
        message = self._call_with_urlopen_raising(TimeoutError())
        self.assertEqual(message, "Gemini did not answer within 7s (raise --timeout)")

    def test_timeout_wrapped_in_urlerror_gives_timeout_message(self) -> None:
        wrapped = so.urllib.error.URLError(TimeoutError("timed out"))
        message = self._call_with_urlopen_raising(wrapped)
        self.assertEqual(message, "Gemini did not answer within 7s (raise --timeout)")

    def test_other_urlerror_stays_a_network_error(self) -> None:
        message = self._call_with_urlopen_raising(so.urllib.error.URLError("connection refused"))
        self.assertEqual(message, "network error calling Gemini: connection refused")

    def test_payload_rejects_unknown_thinking_level(self) -> None:
        with self.assertRaises(so.SecondOpinionError):
            so.build_payload("p", use_schema=True, thinking_level="extreme")


if __name__ == "__main__":
    unittest.main()
