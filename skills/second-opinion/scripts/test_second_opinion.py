"""Unit tests for the pure parts of second_opinion.py (stdlib unittest).

Run: python -m unittest discover -s skills/second-opinion/scripts -v
No test makes a network call; the guard test asserts urlopen is never reached.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
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


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"not a real picture, only the magic bytes"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"synthetic"
WEBP_BYTES = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"synthetic"
GIF_BYTES = b"GIF89a" + b"synthetic"

# sha256 of the --dry-run stdout of a plain call (no new flag), taken from the
# script at commit 0492b68, before modes, context, images and cost existed.
# Input: _plain_dry_run_stdout() below. It pins the code-mode system prompt,
# RESPONSE_SCHEMA and the user prompt layout byte for byte.
PLAIN_DRY_RUN_SHA256 = "81369e1cca5f0bdd55e8d90d3f82af1b9e4da17d8e324cc0d0c6bbc1a4683296"

CONTROL_USAGE = {"promptTokenCount": 19271, "thoughtsTokenCount": 12632, "candidatesTokenCount": 982,
                 "totalTokenCount": 32885}
BEFORE_PRICE_CHANGE = date(2026, 12, 31)
AFTER_PRICE_CHANGE = date(2027, 1, 1)


class OwnedRepoCase(unittest.TestCase):
    """A fake owned repo and a fake non-owned repo, with the cwd in the owned one."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.owned = make_main_repo(self.root, "outer_heaven")
        self.other = make_main_repo(self.root, "some-customer-repo")
        (self.owned / "a.py").write_text("x = 1\n", encoding="utf-8")
        self._old_cwd = os.getcwd()
        os.chdir(self.owned)
        # A rate in the developer's own environment must not steer the tests.
        self._env = mock.patch.dict(os.environ)
        self._env.start()
        os.environ.pop(so.USD_DKK_ENV_VAR, None)

    def tearDown(self) -> None:
        self._env.stop()
        os.chdir(self._old_cwd)
        self._tmp.cleanup()

    def run_main(self, *argv: str, stdin: bytes | None = None, response: dict | None = None) -> tuple[int, str, str]:
        """Run main() with the network closed. `response` fakes a Gemini answer."""
        out, err = io.StringIO(), io.StringIO()
        fake_stdin = mock.Mock(buffer=io.BytesIO(stdin or b""))
        with mock.patch.object(so.urllib.request, "urlopen") as urlopen, \
                mock.patch.object(so, "get_api_key", return_value="NOT-A-REAL-KEY") as get_key, \
                mock.patch.object(so, "call_gemini", return_value=response) as call, \
                mock.patch.object(so.sys, "stdin", fake_stdin), \
                redirect_stdout(out), redirect_stderr(err):
            code = so.main(list(argv))
        urlopen.assert_not_called()
        if response is None:
            get_key.assert_not_called()
            call.assert_not_called()
        return code, out.getvalue(), err.getvalue()

    def write_image(self, name: str, data: bytes = PNG_BYTES, repo: Path | None = None) -> Path:
        path = (repo or self.owned) / name
        path.write_bytes(data)
        return path


def fake_response(answer: dict, model_version: str = "gemini-3.1-pro-preview", usage: dict | None = None) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}, "finishReason": "STOP"}],
        "modelVersion": model_version,
        "usageMetadata": dict(usage or CONTROL_USAGE),
    }


class CostTests(unittest.TestCase):
    def _cost(self, model: str = "gemini-3.1-pro-preview", usage: dict | None = None,
              call_date: date = BEFORE_PRICE_CHANGE, **kwargs: object) -> dict:
        return so.estimate_cost(model, usage or CONTROL_USAGE, call_date, **kwargs)

    def test_control_sum(self) -> None:
        cost = self._cost()
        self.assertEqual(cost["usd"], 0.20191)  # 0.038542 + 0.163368
        self.assertEqual(cost["dkk"], 1.3766)
        self.assertEqual(f"{cost['usd']:.4f}", "0.2019")
        self.assertEqual(f"{cost['dkk']:.2f}", "1.38")
        self.assertIs(cost["estimate"], True)
        self.assertEqual(cost["model_version"], "gemini-3.1-pro-preview")
        self.assertEqual(cost["prices_as_of"], "2026-11-25")
        self.assertEqual(cost["tier"], "<=200k")
        self.assertEqual(cost["usd_dkk_rate"], 6.8178)
        self.assertEqual(cost["usd_dkk_rate_source"], "fixed, 2026-11-24")
        self.assertNotIn("reason", cost)

    def test_control_sum_cost_line(self) -> None:
        self.assertEqual(
            so.cost_line(self._cost()),
            "cost (estimate): 0.2019 USD = 1.38 DKK | prices as of 2026-11-25 (table), tier <=200k | "
            "1 USD = 6.8178 DKK (fixed, 2026-11-24)",
        )

    def test_thought_tokens_are_priced_as_output(self) -> None:
        only_thoughts = self._cost(usage={"promptTokenCount": 0, "thoughtsTokenCount": 1_000_000})
        only_answer = self._cost(usage={"promptTokenCount": 0, "candidatesTokenCount": 1_000_000})
        self.assertEqual(only_thoughts["usd"], 12.0)
        self.assertEqual(only_answer["usd"], 12.0)

    def test_200k_is_the_low_tier_and_200001_the_high(self) -> None:
        low = self._cost(usage={"promptTokenCount": 200_000, "candidatesTokenCount": 1_000_000})
        high = self._cost(usage={"promptTokenCount": 200_001, "candidatesTokenCount": 1_000_000})
        self.assertEqual(low["tier"], "<=200k")
        self.assertEqual(low["usd"], round(200_000 * 2.0 / 1e6 + 12.0, 6))
        self.assertEqual(high["tier"], ">200k")
        self.assertEqual(high["usd"], round(200_001 * 4.0 / 1e6 + 18.0, 6))

    def test_flash_price_changes_at_new_year(self) -> None:
        usage = {"promptTokenCount": 1_000_000, "candidatesTokenCount": 1_000_000}
        for model in ("gemini-3.6-flash", "gemini-3.8-flash"):
            with self.subTest(model=model):
                self.assertEqual(self._cost(model, usage, BEFORE_PRICE_CHANGE)["usd"], 0.75 + 3.75)
                self.assertEqual(self._cost(model, usage, AFTER_PRICE_CHANGE)["usd"], 1.50 + 7.50)

    def test_flat_rows(self) -> None:
        usage = {"promptTokenCount": 1_000_000, "candidatesTokenCount": 1_000_000}
        expected = {"gemini-3-flash-preview": 3.50, "gemini-3.1-flash-lite": 1.75, "gemini-3.5-flash-lite": 2.80}
        for model, usd in expected.items():
            with self.subTest(model=model):
                cost = self._cost(model, usage)
                self.assertEqual(cost["usd"], usd)
                self.assertEqual(cost["tier"], "flat")

    def test_unknown_model_gets_no_number(self) -> None:
        # The alias and a longer version string must not match by prefix.
        for model in ("gemini-pro-latest", "gemini-3.1-pro-preview-0925", "gemini-3.1-pro", "unknown"):
            with self.subTest(model=model):
                cost = self._cost(model)
                self.assertIsNone(cost["usd"])
                self.assertIsNone(cost["dkk"])
                self.assertIsNone(cost["tier"])
                self.assertIn("price unknown", cost["reason"])
                line = so.cost_line(cost)
                self.assertTrue(line.startswith(f"cost (estimate): price unknown for model version '{model}'"))
                self.assertNotIn(" USD =", line)
                self.assertNotIn("DKK", line)

    def test_no_token_usage_gets_no_number(self) -> None:
        # No usageMetadata, or one without promptTokenCount: 0.0000 USD would be a wrong number.
        for usage in ({}, {"totalTokenCount": 0}, {"candidatesTokenCount": 50}, {"promptTokenCount": None}):
            for override in (None, (1.0, 5.0)):
                with self.subTest(usage=usage, override=override):
                    cost = so.estimate_cost("gemini-3.1-pro-preview", usage, BEFORE_PRICE_CHANGE,
                                            price_override=override)
                    self.assertIsNone(cost["usd"])
                    self.assertIsNone(cost["dkk"])
                    self.assertIsNone(cost["tier"])
                    self.assertIn("no token usage", cost["reason"])
                    line = so.cost_line(cost)
                    self.assertTrue(line.startswith("cost (estimate): price unknown: the response carried no token "
                                                    "usage"))
                    self.assertNotIn("USD", line)
                    self.assertNotIn("DKK", line)
        # A reported count of zero is usage, and is priced.
        zero = so.estimate_cost("gemini-3.1-pro-preview", {"promptTokenCount": 0}, BEFORE_PRICE_CHANGE)
        self.assertEqual(zero["usd"], 0.0)

    def test_price_override_wins_over_the_table(self) -> None:
        usage = {"promptTokenCount": 1_000_000, "candidatesTokenCount": 1_000_000}
        for model in ("gemini-3.1-pro-preview", "a-model-not-in-the-table"):
            with self.subTest(model=model):
                cost = self._cost(model, usage, price_override=(1.0, 5.0))
                self.assertEqual(cost["usd"], 6.0)
                self.assertEqual(cost["tier"], "override")
                self.assertIsNone(cost["prices_as_of"])
                self.assertIn("--price-in/--price-out", cost["note"])
                self.assertIn("prices from --price-in/--price-out (override, flat)", so.cost_line(cost))

    def test_cached_tokens_are_priced_in_full_and_flagged(self) -> None:
        cached = self._cost(usage={**CONTROL_USAGE, "cachedContentTokenCount": 5000})
        self.assertEqual(cached["usd"], self._cost()["usd"])
        self.assertIn("upper bound", cached["note"])
        self.assertIn("upper bound", so.cost_line(cached))
        self.assertNotIn("upper bound", self._cost()["note"])
        self.assertNotIn("upper bound", so.cost_line(self._cost()))

    def test_rate_from_flag_env_or_constant(self) -> None:
        self.assertEqual(so.resolve_usd_dkk(None, {}), (6.8178, "fixed, 2026-11-24"))
        self.assertEqual(so.resolve_usd_dkk(None, {so.USD_DKK_ENV_VAR: "7.5"}),
                         (7.5, "from env SECOND_OPINION_USD_DKK"))
        self.assertEqual(so.resolve_usd_dkk(7.0, {so.USD_DKK_ENV_VAR: "7.5"}), (7.0, "from --usd-dkk"))

    def test_overridden_rate_is_named_without_a_date(self) -> None:
        cost = self._cost(usd_dkk_rate=7.0, usd_dkk_rate_source="from --usd-dkk")
        self.assertEqual(cost["dkk"], round(0.20191 * 7.0, 4))
        line = so.cost_line(cost)
        self.assertTrue(line.endswith("1 USD = 7 DKK (from --usd-dkk)"))
        self.assertNotIn("2026-11-24", line)

    def test_bad_rate_is_a_usage_error_not_a_fallback(self) -> None:
        for bad in ("abc", "0", "-1", "nan", "inf", "6,8"):
            with self.subTest(source="flag", bad=bad):
                err = io.StringIO()
                with mock.patch.dict(os.environ), redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
                    os.environ.pop(so.USD_DKK_ENV_VAR, None)
                    so.parse_args(["--requirements-text", "r", f"--usd-dkk={bad}"])
                self.assertEqual(ctx.exception.code, 2)
            with self.subTest(source="env", bad=bad):
                err = io.StringIO()
                with mock.patch.dict(os.environ, {so.USD_DKK_ENV_VAR: bad}), redirect_stderr(err), \
                        self.assertRaises(SystemExit) as ctx:
                    so.parse_args(["--requirements-text", "r"])
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn(so.USD_DKK_ENV_VAR, err.getvalue())

    def test_price_flags_must_come_together(self) -> None:
        for argv in (["--price-in", "1"], ["--price-out", "1"], ["--price-in", "x", "--price-out", "1"],
                     ["--price-in", "-1", "--price-out", "1"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
                so.parse_args(["--requirements-text", "r", *argv])
            self.assertEqual(ctx.exception.code, 2)
        args = so.parse_args(["--requirements-text", "r", "--price-in", "1.5", "--price-out", "0"])
        self.assertEqual((args.price_in, args.price_out), (1.5, 0.0))

    def test_usage_counts_are_integers(self) -> None:
        self.assertEqual(so.usage_counts({"usageMetadata": {"promptTokenCount": 3}}),
                         {"promptTokenCount": 3, "thoughtsTokenCount": 0, "candidatesTokenCount": 0,
                          "totalTokenCount": 0})


class CostOutputTests(OwnedRepoCase):
    ANSWER = {"verdict": "approve", "summary": "ok", "findings": []}

    def test_stderr_and_json_carry_usage_and_cost(self) -> None:
        code, out, err = self.run_main("--requirements-text", "r", "--files", "a.py",
                                       response=fake_response(self.ANSWER))
        self.assertEqual(code, 0)
        self.assertEqual(err.splitlines()[1:], [
            "model version: gemini-3.1-pro-preview",
            "usage: promptTokenCount=19271 thoughtsTokenCount=12632 candidatesTokenCount=982 totalTokenCount=32885",
            "cost (estimate): 0.2019 USD = 1.38 DKK | prices as of 2026-11-25 (table), tier <=200k | "
            "1 USD = 6.8178 DKK (fixed, 2026-11-24)",
        ])
        answer = json.loads(out)
        self.assertEqual(answer["mode"], "code")
        self.assertEqual(answer["model_version"], "gemini-3.1-pro-preview")
        self.assertEqual(answer["usage"], CONTROL_USAGE)
        self.assertEqual(answer["cost"]["usd"], 0.20191)
        self.assertEqual(answer["cost"]["dkk"], 1.3766)
        self.assertNotIn("coverage", answer)

    def test_unknown_model_prints_tokens_and_no_number(self) -> None:
        code, out, err = self.run_main("--requirements-text", "r", "--files", "a.py",
                                       response=fake_response(self.ANSWER, model_version="gemini-9-new"))
        self.assertEqual(code, 0)
        self.assertIn("usage: promptTokenCount=19271", err)
        self.assertIn("cost (estimate): price unknown for model version 'gemini-9-new'", err)
        cost = json.loads(out)["cost"]
        self.assertIsNone(cost["usd"])
        self.assertIsNone(cost["dkk"])
        self.assertTrue(cost["reason"])

    def test_response_without_usage_metadata_prints_no_number(self) -> None:
        response = fake_response(self.ANSWER)
        del response["usageMetadata"]
        code, out, err = self.run_main("--requirements-text", "r", "--files", "a.py", response=response)
        self.assertEqual(code, 0)
        self.assertIn("usage: promptTokenCount=0 thoughtsTokenCount=0 candidatesTokenCount=0 totalTokenCount=0", err)
        self.assertIn("cost (estimate): price unknown: the response carried no token usage", err)
        self.assertNotIn("0.0000", err)
        result = json.loads(out)
        self.assertIsNone(result["cost"]["usd"])
        self.assertIsNone(result["cost"]["dkk"])
        self.assertIn("no token usage", result["cost"]["reason"])
        self.assertEqual(result["usage"]["promptTokenCount"], 0)

    def test_flags_and_env_reach_the_output(self) -> None:
        os.environ[so.USD_DKK_ENV_VAR] = "7.5"
        code, out, err = self.run_main("--requirements-text", "r", "--files", "a.py",
                                       "--price-in", "1", "--price-out", "1",
                                       response=fake_response(self.ANSWER, model_version="gemini-9-new"))
        self.assertEqual(code, 0)
        cost = json.loads(out)["cost"]
        self.assertEqual(cost["usd"], round(32885 / 1e6, 6))
        self.assertEqual(cost["usd_dkk_rate"], 7.5)
        self.assertIn("(override, flat)", err)
        self.assertIn("1 USD = 7.5 DKK (from env SECOND_OPINION_USD_DKK)", err)


class ModeTests(OwnedRepoCase):
    def _plain_dry_run_stdout(self) -> str:
        code, out, _ = self.run_main("--requirements-text", "The value must be 1.", "--files", "a.py",
                                     "--focus", "Is the value right?", "--source-repo", ".", "--dry-run")
        self.assertEqual(code, 0)
        return out

    def test_default_call_sends_todays_body(self) -> None:
        out = self._plain_dry_run_stdout()
        self.assertEqual(hashlib.sha256(out.encode("utf-8")).hexdigest(), PLAIN_DRY_RUN_SHA256)

    def test_explicit_code_mode_equals_default(self) -> None:
        code, out, _ = self.run_main("--requirements-text", "The value must be 1.", "--files", "a.py",
                                     "--focus", "Is the value right?", "--source-repo", ".", "--dry-run",
                                     "--mode", "code")
        self.assertEqual(code, 0)
        self.assertEqual(out, self._plain_dry_run_stdout())
        self.assertEqual(so.build_payload("p", use_schema=True), so.build_payload("p", use_schema=True, mode="code"))
        self.assertIs(so.SYSTEM_PROMPTS["code"], so.SYSTEM_PROMPT)
        self.assertIs(so.RESPONSE_SCHEMAS["code"], so.RESPONSE_SCHEMA)

    def test_modes(self) -> None:
        self.assertEqual(so.MODES, ["code", "architecture", "solution", "product", "design"])
        self.assertEqual(so.parse_args(["--requirements-text", "r"]).mode, "code")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            so.parse_args(["--requirements-text", "r", "--mode", "poetry"])

    def test_mode_selects_prompt_and_schema(self) -> None:
        prompts = set()
        for mode in so.MODES:
            with self.subTest(mode=mode):
                payload = so.build_payload("p", use_schema=True, mode=mode)
                prompt = payload["systemInstruction"]["parts"][0]["text"]
                self.assertEqual(prompt, so.SYSTEM_PROMPTS[mode])
                self.assertEqual(payload["generationConfig"]["responseSchema"], so.RESPONSE_SCHEMAS[mode])
                prompts.add(prompt)
        self.assertEqual(len(prompts), len(so.MODES))
        with self.assertRaises(so.SecondOpinionError):
            so.build_payload("p", use_schema=True, mode="poetry")

    def test_category_enum_equals_coverage_dimension_enum(self) -> None:
        expected = {
            "architecture": ["layering", "responsibilities", "coupling", "scalability", "redundancy", "gaps",
                             "operability", "requirements_fit"],
            "solution": ["requirements_coverage", "user_flow", "data_model", "integration", "security_privacy",
                         "operation_and_cost", "simpler_alternative", "delivery_risk"],
            "product": ["target_user", "problem", "unsupported_assumptions", "scope_boundary",
                        "value_and_differentiation", "risks", "success_measure"],
            "design": ["task_support", "hierarchy", "readability", "consistency", "accessibility",
                       "data_presentation"],
        }
        self.assertEqual(set(expected), set(so.MODES) - {"code"})
        for mode, dimensions in expected.items():
            with self.subTest(mode=mode):
                schema = so.RESPONSE_SCHEMAS[mode]
                finding = schema["properties"]["findings"]["items"]
                coverage = schema["properties"]["coverage"]["items"]
                self.assertEqual(finding["properties"]["category"]["enum"], dimensions)
                self.assertEqual(coverage["properties"]["dimension"]["enum"], dimensions)
                self.assertEqual(coverage["properties"]["assessment"]["enum"],
                                 ["problems_found", "no_problems_found", "not_assessable"])
                self.assertEqual(coverage["required"], ["dimension", "assessment", "basis"])
                for field in ("category", "evidence", "location"):
                    self.assertIn(field, finding["required"])
                self.assertIn("coverage", schema["required"])
                for dimension in dimensions:
                    self.assertIn(f"- {dimension}: ", so.SYSTEM_PROMPTS[mode])

    def test_non_code_schema_keeps_todays_finding_fields(self) -> None:
        today = so.RESPONSE_SCHEMA["properties"]["findings"]["items"]
        for mode in so.MODE_DIMENSIONS:
            with self.subTest(mode=mode):
                schema = so.RESPONSE_SCHEMAS[mode]
                finding = schema["properties"]["findings"]["items"]
                for name, spec in today["properties"].items():
                    self.assertEqual(finding["properties"][name], spec)
                self.assertTrue(set(today["required"]) <= set(finding["required"]))
                self.assertEqual(set(schema["properties"]), {"verdict", "summary", "findings", "coverage"})
                # Every property is ordered, and nothing is ordered that does not exist.
                self.assertEqual(sorted(schema["propertyOrdering"]), sorted(schema["properties"]))
                self.assertEqual(sorted(finding["propertyOrdering"]), sorted(finding["properties"]))

    def test_non_code_prompts_carry_the_rules(self) -> None:
        for mode in so.MODE_DIMENSIONS:
            with self.subTest(mode=mode):
                prompt = so.SYSTEM_PROMPTS[mode]
                self.assertIn("adversarial by design", prompt)
                self.assertIn("at the level of the material", prompt)
                # Only the modes whose material is files carry the line-level sentence.
                line_level = "Line-level bugs in a single file are out of scope unless they show a structural problem"
                self.assertEqual(line_level in prompt, mode in ("architecture", "solution"))
                self.assertNotIn(". \n", prompt)
                self.assertNotIn("..", prompt)
                self.assertIn("exactly one coverage item for every dimension", prompt)
                self.assertIn("not_assessable is a valid and expected answer", prompt)
                self.assertIn("The summary must not call anything sound", prompt)
                self.assertIn("Do not pad.", prompt)
                self.assertIn("do not invent certainty", prompt)
                self.assertTrue(prompt.isascii())
        self.assertIn("not line-level procedure", so.SYSTEM_PROMPTS["architecture"])

    def test_coverage_is_tolerant(self) -> None:
        body = {"verdict": "approve", "summary": "", "findings": []}
        for broken in (body, {**body, "coverage": None}, {**body, "coverage": "none"}):
            answer = so.parse_findings(fake_response(broken), "architecture")
            self.assertEqual(answer["coverage"], [])
        kept = [{"dimension": "gaps", "assessment": "not_assessable", "basis": "b"}]
        self.assertEqual(so.parse_findings(fake_response({**body, "coverage": kept}), "design")["coverage"], kept)
        self.assertNotIn("coverage", so.parse_findings(fake_response(body)))
        self.assertNotIn("coverage", so.parse_findings(fake_response(body), "code"))

    def test_mode_is_named_on_stderr_and_in_the_json(self) -> None:
        answer = {"verdict": "approve", "summary": "", "findings": []}
        code, out, err = self.run_main("--requirements-text", "r", "--files", "a.py", "--mode", "solution",
                                       response=fake_response(answer))
        self.assertEqual(code, 0)
        self.assertTrue(err.startswith("request: model=gemini-pro-latest mode=solution prompt_chars="))
        result = json.loads(out)
        self.assertEqual(result["mode"], "solution")
        self.assertEqual(result["coverage"], [])


class ContextTests(OwnedRepoCase):
    def _prompt(self, out: str) -> str:
        return json.loads(out)["contents"][0]["parts"][0]["text"]

    def test_context_alone_is_enough_material(self) -> None:
        (self.owned / "overview.md").write_text("Three layers.\n", encoding="utf-8")
        code, out, _ = self.run_main("--requirements-text", "r", "--context", "overview.md",
                                     "--mode", "architecture", "--dry-run")
        self.assertEqual(code, 0)
        prompt = self._prompt(out)
        self.assertIn("### context: overview.md\n\n```\n\nThree layers.\n\n```", prompt)
        self.assertNotIn("diff", prompt)

    def test_context_label(self) -> None:
        (self.owned / "overview.md").write_text("Three layers.\n", encoding="utf-8")
        code, out, _ = self.run_main("--requirements-text", "r", "--context", "overview.md",
                                     "--context-label", "system overview", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("### context: system overview\n", self._prompt(out))
        self.assertNotIn("overview.md", self._prompt(out))

    def test_context_on_stdin(self) -> None:
        code, out, _ = self.run_main("--requirements-text", "r", "--context", "-", "--files", "a.py", "--dry-run",
                                     stdin="Søjler og lag.\n".encode("utf-8"))
        self.assertEqual(code, 0)
        prompt = self._prompt(out)
        self.assertIn("### context: stdin\n\n```\n\nSøjler og lag.\n\n```", prompt)
        self.assertLess(prompt.index("### context: stdin"), prompt.index("### file: a.py"))

    def test_stdin_context_is_attributed_to_source_repo(self) -> None:
        code, _, err = self.run_main("--requirements-text", "r", "--context", "-", "--dry-run",
                                     "--source-repo", str(self.other), stdin=b"text")
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("data guard: REFUSED"))

    def test_context_file_passes_the_path_guard(self) -> None:
        foreign = self.other / "note.md"
        foreign.write_text("text", encoding="utf-8")
        code, _, err = self.run_main("--requirements-text", "r", "--context", str(foreign), "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("some-customer-repo", err)

    def test_diff_and_context_cannot_both_be_stdin(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            so.parse_args(["--requirements-text", "r", "--diff", "-", "--context", "-"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("cannot both read stdin", err.getvalue())

    def test_context_label_needs_context(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            so.parse_args(["--requirements-text", "r", "--context-label", "x"])
        self.assertEqual(ctx.exception.code, 2)

    def test_no_material_at_all_is_still_an_error(self) -> None:
        code, _, err = self.run_main("--requirements-text", "r", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("no material to review", err)


class ImageTests(OwnedRepoCase):
    BASE = ("--requirements-text", "r", "--mode", "design", "--dry-run")

    def test_magic_bytes_decide_the_type(self) -> None:
        self.assertEqual(so.detect_image_type(PNG_BYTES), "image/png")
        self.assertEqual(so.detect_image_type(JPEG_BYTES), "image/jpeg")
        self.assertEqual(so.detect_image_type(WEBP_BYTES), "image/webp")
        for other in (GIF_BYTES, b"RIFF\x10\x00\x00\x00WAVEfmt ", b"", b"<svg>"):
            self.assertIsNone(so.detect_image_type(other))

    def test_check_image(self) -> None:
        self.assertEqual(so.check_image("a.png", PNG_BYTES), "image/png")
        self.assertEqual(so.check_image("a.JPG", JPEG_BYTES), "image/jpeg")
        self.assertEqual(so.check_image("a.jpeg", JPEG_BYTES), "image/jpeg")
        self.assertEqual(so.check_image("a.webp", WEBP_BYTES), "image/webp")
        for name, data in (("a.gif", GIF_BYTES), ("a.png", GIF_BYTES), ("a.png", JPEG_BYTES),
                           ("a.jpg", PNG_BYTES), ("a", PNG_BYTES), ("a.txt", b"hello")):
            with self.subTest(name=name), self.assertRaises(so.SecondOpinionError):
                so.check_image(name, data)

    def test_refused_without_the_flag_and_nothing_is_sent(self) -> None:
        self.write_image("one.png")
        self.write_image("two.jpg", JPEG_BYTES)
        for dry_run in (("--dry-run",), ()):
            with self.subTest(dry_run=dry_run):
                # run_main asserts that neither the key lookup nor the network was reached.
                code, out, err = self.run_main("--requirements-text", "r", "--images", "one.png", "two.jpg",
                                               *dry_run)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertTrue(err.startswith("data guard: REFUSED"))
                self.assertIn("image 1: one.png", err)
                self.assertIn("image 2: two.jpg", err)
                self.assertIn("cannot see what a picture shows", err)
                self.assertIn("--images-approved", err)
                self.assertNotIn("--customer-approved", err)

    def test_flag_lets_it_through_and_leaves_a_trace(self) -> None:
        self.write_image("one.png")
        code, out, err = self.run_main(*self.BASE, "--images", "one.png", "--images-approved")
        self.assertEqual(code, 0)
        self.assertIn("data guard: images released by --images-approved (inline data):", err)
        self.assertIn(f"  - image 1: one.png ({len(PNG_BYTES)} bytes, image/png)", err)
        self.assertIn(" mode=design ", err)
        self.assertIn(" images=1", err)

    def test_non_owned_image_needs_both_flags(self) -> None:
        foreign = str(self.write_image("shot.png", repo=self.other))
        loose_dir = self.root / "loose"
        loose_dir.mkdir()
        loose = str(self.write_image("shot.png", repo=loose_dir))
        for image in (foreign, loose):
            with self.subTest(image=image):
                code, _, err = self.run_main(*self.BASE, "--images", image)
                self.assertEqual(code, 2)
                self.assertIn("--customer-approved", err)
                self.assertIn("--images-approved", err)

                code, _, err = self.run_main(*self.BASE, "--images", image, "--images-approved")
                self.assertEqual(code, 2)
                self.assertTrue(err.startswith("data guard: REFUSED"))
                self.assertIn("--customer-approved", err)

                code, _, err = self.run_main(*self.BASE, "--images", image, "--customer-approved")
                self.assertEqual(code, 2)
                self.assertTrue(err.startswith("data guard: REFUSED"))
                self.assertIn("--images-approved", err)

                code, _, err = self.run_main(*self.BASE, "--images", image, "--images-approved",
                                             "--customer-approved")
                self.assertEqual(code, 0)
                self.assertIn("overridden by --customer-approved", err)

    def test_wrong_type_is_an_error_before_any_network_call(self) -> None:
        self.write_image("anim.gif", GIF_BYTES)
        self.write_image("lies.png", JPEG_BYTES)
        for name in ("anim.gif", "lies.png"):
            with self.subTest(name=name):
                code, out, err = self.run_main("--requirements-text", "r", "--images", name, "--images-approved")
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn(f"error: image {name}", err)

    def test_size_refusal_names_the_size(self) -> None:
        so.check_request_size(20_000_000)
        with self.assertRaises(so.SecondOpinionError) as ctx:
            so.check_request_size(20_000_001)
        self.assertIn("20,000,001 bytes", str(ctx.exception))
        self.write_image("one.png")
        with mock.patch.object(so, "MAX_REQUEST_BYTES", 500):
            for dry_run in (("--dry-run",), ()):
                code, out, err = self.run_main("--requirements-text", "r", "--images", "one.png",
                                               "--images-approved", *dry_run)
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn("over the 500 byte limit", err)

    def test_payload_has_text_first_then_inline_data(self) -> None:
        images = [so.ImagePart("one.png", "image/png", PNG_BYTES), so.ImagePart("two.webp", "image/webp", WEBP_BYTES)]
        prompt = so.build_user_prompt("r", [], None, [image.name for image in images])
        self.assertIn("image 1: one.png\nimage 2: two.webp", prompt)
        parts = so.build_payload(prompt, use_schema=True, mode="design", images=images)["contents"][0]["parts"]
        self.assertEqual(parts[0], {"text": prompt})
        self.assertEqual(parts[1], {"inlineData": {"mimeType": "image/png",
                                                   "data": base64.b64encode(PNG_BYTES).decode("ascii")}})
        self.assertEqual(parts[2]["inlineData"]["mimeType"], "image/webp")
        self.assertEqual(base64.b64decode(parts[2]["inlineData"]["data"]), WEBP_BYTES)
        self.assertEqual(len(parts), 3)

    def test_dry_run_replaces_the_data_with_a_placeholder(self) -> None:
        for extra in (b"", b"1", b"12"):  # all three base64 padding lengths
            data = PNG_BYTES + extra
            self.write_image("one.png", data)
            code, out, _ = self.run_main(*self.BASE, "--images", "one.png", "--images-approved")
            self.assertEqual(code, 0)
            parts = json.loads(out)["contents"][0]["parts"]
            self.assertEqual(parts[1]["inlineData"],
                             {"mimeType": "image/png", "data": f"<base64 omitted, {len(data)} bytes>"})
            self.assertNotIn(base64.b64encode(data).decode("ascii"), out)
            self.assertIn("image 1: one.png", parts[0]["text"])

    def test_display_copy_leaves_the_real_payload_alone(self) -> None:
        payload = so.build_payload("p", use_schema=False, images=[so.ImagePart("one.png", "image/png", PNG_BYTES)])
        so.payload_for_display(payload)
        self.assertEqual(base64.b64decode(payload["contents"][0]["parts"][1]["inlineData"]["data"]), PNG_BYTES)

    def test_the_real_data_goes_on_the_wire(self) -> None:
        self.write_image("one.png")
        answer = {"verdict": "approve", "summary": "", "findings": [], "coverage": []}
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(so, "get_api_key", return_value="NOT-A-REAL-KEY"), \
                mock.patch.object(so, "call_gemini", return_value=fake_response(answer)) as call, \
                redirect_stdout(out), redirect_stderr(err):
            code = so.main(["--requirements-text", "r", "--mode", "design", "--images", "one.png",
                            "--images-approved"])
        self.assertEqual(code, 0)
        sent = call.call_args.args[1]
        self.assertEqual(base64.b64decode(sent["contents"][0]["parts"][1]["inlineData"]["data"]), PNG_BYTES)
        self.assertNotIn("NOT-A-REAL-KEY", out.getvalue() + err.getvalue())


if __name__ == "__main__":
    unittest.main()
