"""Get a second opinion from Google Gemini on code, architecture or a decision.

Stdlib only (urllib), no third-party packages. Sends requirements plus raw
material (a diff and/or files) to the Gemini REST API and prints structured
JSON findings to stdout. Token usage and the resolved model version go to
stderr, so stdout stays clean JSON. See ../SKILL.md for method and rules.

Data guard: default-deny. Material may only be sent from repos on the owned
allowlist (matched on the MAIN repo folder name, worktrees resolved). Anything
else is refused before any network call unless --customer-approved is passed,
which stands for Benny's explicit yes for this one run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-pro-latest"
DEFAULT_TIMEOUT_S = 300
KEY_ENV_VAR = "GEMINI_API_KEY"

# Repos Benny owns, matched on the main repo's folder name. Default-deny:
# everything not listed here is refused unless --customer-approved is passed.
OWNED_REPOS = frozenset({"outer_heaven", "command-deck", "datavilla"})

SEVERITIES = ["critical", "major", "minor", "nit"]
VERDICTS = ["approve", "approve_with_changes", "request_changes", "reject"]

SYSTEM_PROMPT = """\
You are an independent senior reviewer giving a second opinion. You are \
adversarial by design: your job is to find what is wrong, missing or risky, \
not to reassure. Assume the author is competent but has blind spots.

Review the MATERIAL against the REQUIREMENTS. Look for:
- requirements that are not met, or met only partly;
- correctness bugs, unhandled edge cases, wrong assumptions;
- security and data-handling problems (secrets, injection, data leaks);
- design choices that will hurt later, and simpler alternatives;
- missing or weak validation and tests.

Rules:
- Only report findings you can tie to a concrete location in the material. \
If you are unsure, say so in the finding; do not invent certainty.
- Do not pad. An empty findings list is a valid answer if the material is sound.
- You have not seen the author's own review or conclusions. Do not guess them.
- Answer in English, as JSON matching the response schema."""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "verdict": {"type": "STRING", "enum": VERDICTS},
        "summary": {"type": "STRING"},
        "findings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "severity": {"type": "STRING", "enum": SEVERITIES},
                    "location": {"type": "STRING"},
                    "issue": {"type": "STRING"},
                    "why_it_matters": {"type": "STRING"},
                    "suggested_fix": {"type": "STRING"},
                    "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                },
                "required": ["severity", "location", "issue", "why_it_matters", "suggested_fix"],
                "propertyOrdering": [
                    "severity",
                    "location",
                    "issue",
                    "why_it_matters",
                    "suggested_fix",
                    "confidence",
                ],
            },
        },
    },
    "required": ["verdict", "summary", "findings"],
    "propertyOrdering": ["verdict", "summary", "findings"],
}


class SecondOpinionError(Exception):
    """A failure to report to the user with a clear message and exit code 1."""


class GuardRefusal(Exception):
    """The data guard refused the run. Raised before any network call."""


@dataclass(frozen=True)
class RepoInfo:
    """Where a path lives: the working tree root and the main repo's name."""

    worktree_root: Path
    main_repo_root: Path

    @property
    def name(self) -> str:
        return self.main_repo_root.name


# --------------------------------------------------------------------------
# Repo resolution and the data guard (pure, file reads only, no git calls)
# --------------------------------------------------------------------------


def _read_gitdir_pointer(dot_git_file: Path) -> Path:
    """Read the `gitdir: <path>` line of a `.git` file (worktree or submodule)."""
    text = dot_git_file.read_text(encoding="utf-8").strip()
    prefix = "gitdir:"
    if not text.startswith(prefix):
        raise SecondOpinionError(f"unrecognised .git file: {dot_git_file}")
    target = Path(text[len(prefix) :].strip())
    if not target.is_absolute():
        target = dot_git_file.parent / target
    return target.resolve()


def _main_repo_root_from_gitdir(gitdir: Path, worktree_root: Path) -> Path:
    """Map a linked gitdir to the main repo's working tree root.

    A worktree's gitdir is `<main>/.git/worktrees/<name>` and holds a
    `commondir` file pointing at `<main>/.git`. Anything else (for example a
    submodule) is treated as its own repo, named after its working tree.
    """
    commondir_file = gitdir / "commondir"
    if commondir_file.is_file():
        common = Path(commondir_file.read_text(encoding="utf-8").strip())
        if not common.is_absolute():
            common = gitdir / common
        common = common.resolve()
        if common.name == ".git":
            return common.parent
        return common  # bare repo: the repo folder itself
    parts = gitdir.parts
    if len(parts) >= 3 and parts[-2] == "worktrees" and parts[-3] == ".git":
        return Path(*parts[:-3])
    return worktree_root


def find_repo(path: Path) -> RepoInfo | None:
    """Find the git repo containing `path`, resolving worktrees to the main repo.

    Returns None when the path is not inside any git working tree.
    """
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        dot_git = candidate / ".git"
        if dot_git.is_dir():
            return RepoInfo(worktree_root=candidate, main_repo_root=candidate)
        if dot_git.is_file():
            gitdir = _read_gitdir_pointer(dot_git)
            return RepoInfo(
                worktree_root=candidate,
                main_repo_root=_main_repo_root_from_gitdir(gitdir, candidate),
            )
    return None


def is_owned(repo: RepoInfo | None, owned: frozenset[str] = OWNED_REPOS) -> bool:
    """True only for a repo whose main folder name is on the owned allowlist."""
    if repo is None:
        return False
    return repo.name.lower() in {name.lower() for name in owned}


def check_guard(
    source_repo: Path,
    input_files: list[Path],
    customer_approved: bool,
    owned: frozenset[str] = OWNED_REPOS,
) -> list[str]:
    """Apply the default-deny data rule.

    Returns the list of reasons the run would be refused (empty means allowed).
    With `customer_approved` the reasons are still computed but not enforced;
    the caller decides how to report them.
    """
    reasons: list[str] = []
    checked: list[tuple[str, Path]] = [("--source-repo", source_repo)]
    checked += [("input file", p) for p in input_files]
    for label, path in checked:
        repo = find_repo(path)
        if repo is None:
            reasons.append(f"{label} {path} is not inside any git repo (unknown provenance)")
        elif not is_owned(repo, owned):
            reasons.append(
                f"{label} {path} belongs to repo '{repo.name}' ({repo.main_repo_root}), "
                "which is not on the owned allowlist"
            )
    return reasons


# --------------------------------------------------------------------------
# Request building and response parsing (pure)
# --------------------------------------------------------------------------


def build_user_prompt(
    requirements: str,
    material: list[tuple[str, str]],
    focus: str | None,
) -> str:
    """Assemble the user turn: requirements, optional focus, then raw material."""
    sections = ["## REQUIREMENTS", requirements.strip() or "(none given)"]
    if focus:
        sections += ["## FOCUS", focus.strip()]
    sections.append("## MATERIAL")
    for label, content in material:
        sections += [f"### {label}", "```", content.rstrip(), "```"]
    return "\n\n".join(sections)


def build_payload(user_prompt: str, use_schema: bool) -> dict[str, Any]:
    """Build the generateContent request body."""
    generation_config: dict[str, Any] = {"responseMimeType": "application/json"}
    if use_schema:
        generation_config["responseSchema"] = RESPONSE_SCHEMA
    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": generation_config,
    }


def extract_text(response: dict[str, Any]) -> str:
    """Return the answer text from a generateContent response, skipping thoughts."""
    candidates = response.get("candidates") or []
    if not candidates:
        block = (response.get("promptFeedback") or {}).get("blockReason")
        raise SecondOpinionError(f"no candidates in response (blockReason: {block or 'none given'})")
    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        reason = candidate.get("finishReason", "unknown")
        raise SecondOpinionError(f"empty answer from model (finishReason: {reason})")
    return text


def parse_findings(response: dict[str, Any]) -> dict[str, Any]:
    """Parse the model's JSON answer and check it has the expected shape."""
    text = extract_text(response)
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as exc:
        finish = (response.get("candidates") or [{}])[0].get("finishReason", "unknown")
        raise SecondOpinionError(
            f"model answer is not valid JSON ({exc}; finishReason: {finish})"
        ) from exc
    if not isinstance(answer, dict) or not isinstance(answer.get("findings"), list):
        raise SecondOpinionError("model answer lacks a 'findings' list")
    answer.setdefault("verdict", "unknown")
    answer.setdefault("summary", "")
    return answer


def usage_lines(response: dict[str, Any]) -> list[str]:
    """Format model version and token usage for stderr."""
    usage = response.get("usageMetadata") or {}
    fields = ["promptTokenCount", "thoughtsTokenCount", "candidatesTokenCount", "totalTokenCount"]
    counts = " ".join(f"{f}={usage.get(f, 0)}" for f in fields)
    return [
        f"model version: {response.get('modelVersion', 'unknown')}",
        f"usage: {counts}",
    ]


def google_error_message(body: bytes) -> str:
    """Extract Google's error message from an error response body."""
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return body.decode("utf-8", errors="replace")[:500]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return f"{error.get('status', '')} {error.get('message', '')}".strip()
    return str(data)[:500]


def redact(text: str, secret: str) -> str:
    """Remove the secret from any text before it can be printed."""
    return text.replace(secret, "***") if secret else text


# --------------------------------------------------------------------------
# I/O at the edges: key lookup, file reading, HTTP
# --------------------------------------------------------------------------


def _key_from_windows_user_env() -> str | None:
    """Read the variable from HKCU\\Environment (the user-level environment).

    Needed because a user variable set after a terminal started is not in that
    terminal's process environment.
    """
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, value_type = winreg.QueryValueEx(key, KEY_ENV_VAR)
    except FileNotFoundError:
        return None
    if value_type == winreg.REG_EXPAND_SZ:
        value = os.path.expandvars(value)
    return str(value).strip() or None


def get_api_key() -> str:
    """Return the API key from the process env, else the Windows user env."""
    key = os.environ.get(KEY_ENV_VAR, "").strip() or _key_from_windows_user_env()
    if not key:
        raise SecondOpinionError(
            f"{KEY_ENV_VAR} is not set in the process environment"
            + (" or in the Windows user environment (HKCU\\Environment)" if sys.platform == "win32" else "")
        )
    return key


def read_material(diff_path: str | None, files: list[Path]) -> list[tuple[str, str]]:
    """Read the diff (file or '-' for stdin) and code files into labelled blocks."""
    material: list[tuple[str, str]] = []
    if diff_path == "-":
        # Read bytes and decode as UTF-8: on Windows a text-mode pipe would use
        # the locale codepage and mangle (or fail on) a UTF-8 git diff.
        material.append(("diff (stdin)", sys.stdin.buffer.read().decode("utf-8", errors="replace")))
    elif diff_path:
        material.append((f"diff: {Path(diff_path).name}", Path(diff_path).read_text(encoding="utf-8")))
    for path in files:
        material.append((f"file: {path.as_posix()}", path.read_text(encoding="utf-8")))
    if not material or not any(content.strip() for _, content in material):
        raise SecondOpinionError("no material to review (give --diff and/or --files, and make sure they are not empty)")
    return material


def call_gemini(model: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    """POST to generateContent. The key goes only in the x-goog-api-key header."""
    url = f"{API_BASE}/{model}:generateContent"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = redact(google_error_message(exc.read()), api_key)
        raise SecondOpinionError(f"HTTP {exc.code} from Gemini: {message}") from None
    except urllib.error.URLError as exc:
        raise SecondOpinionError(f"network error calling Gemini: {redact(str(exc.reason), api_key)}") from None
    except TimeoutError:
        raise SecondOpinionError(f"Gemini did not answer within {timeout}s (raise --timeout)") from None


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get a second opinion from Gemini. See ../SKILL.md.")
    req = parser.add_mutually_exclusive_group(required=True)
    req.add_argument("--requirements", type=Path, help="file with the requirements text")
    req.add_argument("--requirements-text", help="requirements given inline")
    parser.add_argument("--diff", help="diff file to review, or '-' to read it from stdin")
    parser.add_argument("--files", type=Path, nargs="*", default=[], help="code or design files to review")
    parser.add_argument("--focus", help="optional question or focus for the reviewer")
    parser.add_argument(
        "--source-repo",
        type=Path,
        default=Path.cwd(),
        help="repo the material comes from (default: current directory); stdin material is attributed to it",
    )
    parser.add_argument(
        "--customer-approved",
        action="store_true",
        help="Benny has explicitly approved sending this non-owned material, for this run only",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="HTTP timeout in seconds")
    parser.add_argument("--no-schema", action="store_true", help="do not send responseSchema (JSON is still requested)")
    parser.add_argument("--dry-run", action="store_true", help="run the guard and print the request body; no network call")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    input_files = list(args.files)
    if args.requirements:
        input_files.append(args.requirements)
    if args.diff and args.diff != "-":
        input_files.append(Path(args.diff))

    reasons = check_guard(args.source_repo, input_files, args.customer_approved)
    if reasons and not args.customer_approved:
        raise GuardRefusal("\n".join(f"  - {r}" for r in reasons))
    if reasons:
        print("data guard: overridden by --customer-approved for:", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)

    requirements = (
        args.requirements_text
        if args.requirements_text is not None
        else args.requirements.read_text(encoding="utf-8")
    )
    material = read_material(args.diff, list(args.files))
    user_prompt = build_user_prompt(requirements, material, args.focus)
    payload = build_payload(user_prompt, use_schema=not args.no_schema)
    print(f"request: model={args.model} prompt_chars={len(user_prompt)}", file=sys.stderr)

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("dry run: no network call made", file=sys.stderr)
        return 0

    api_key = get_api_key()
    response = call_gemini(args.model, payload, api_key, args.timeout)
    for line in usage_lines(response):
        print(line, file=sys.stderr)
    answer = parse_findings(response)
    answer["model_version"] = response.get("modelVersion", "unknown")
    print(json.dumps(answer, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    # Model answers can hold any Unicode; a Windows console codepage cannot.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    try:
        return run(args)
    except GuardRefusal as exc:
        print(
            "data guard: REFUSED, nothing was sent. Material is not from an owned repo:\n"
            f"{exc}\n"
            "Customer or unknown material needs Benny's explicit yes for this run; "
            "only then rerun with --customer-approved.",
            file=sys.stderr,
        )
        return 2
    except SecondOpinionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not read input: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
