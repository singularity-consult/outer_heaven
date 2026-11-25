"""Get a second opinion from Google Gemini on code, architecture or a decision.

Stdlib only (urllib), no third-party packages. Sends requirements plus raw
material (a diff, files, context text and/or images) to the Gemini REST API
and prints structured JSON findings to stdout. Token usage, an estimated cost
and the resolved model version go to stderr, so stdout stays clean JSON. See
../SKILL.md for method and rules.

Review modes (--mode): code (the default), architecture, solution, product
and design. Each non-code mode has its own system prompt and response schema.

Data guard: default-deny. Material may only be sent from repos on the owned
allowlist (matched on the MAIN repo folder name, worktrees resolved). Anything
else is refused before any network call unless --customer-approved is passed,
which stands for Benny's explicit yes for this one run.

Image guard: on top of the path guard. A path says nothing about what a
picture shows, so every run with --images is refused unless --images-approved
is passed, which stands for Benny's explicit yes to send exactly these images.
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import math
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-pro-latest"
DEFAULT_TIMEOUT_S = 300
KEY_ENV_VAR = "GEMINI_API_KEY"

# Repos Benny owns, matched on the main repo's folder name. Default-deny:
# everything not listed here is refused unless --customer-approved is passed.
OWNED_REPOS = frozenset({"outer_heaven", "command-deck", "datavilla"})

# CLI spellings of GenerationConfig.thinkingConfig.thinkingLevel. The API wants
# the uppercase enum name. Which levels a model accepts is NOT checked here:
# the default alias moves between models. What the API does with a level a
# model does not support (an HTTP error or a silent fallback) is not verified.
THINKING_LEVELS = ["minimal", "low", "medium", "high", "xhigh"]

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

# --------------------------------------------------------------------------
# Review modes. `code` is SYSTEM_PROMPT and RESPONSE_SCHEMA above, unchanged.
# Every other mode has a rubric of named dimensions. A dimension id is both
# the `category` of a finding and the `dimension` of a coverage item.
# --------------------------------------------------------------------------

DEFAULT_MODE = "code"
COVERAGE_ASSESSMENTS = ["problems_found", "no_problems_found", "not_assessable"]

MODE_DIMENSIONS: dict[str, list[tuple[str, str]]] = {
    "architecture": [
        ("layering", "are the layers and their boundaries clear, and does each thing sit in the right layer"),
        ("responsibilities", "does each component have one clear job, or are jobs split or shared so that ownership blurs"),
        ("coupling", "what depends on what; hidden or circular dependencies; what breaks when one part changes"),
        ("scalability", "what happens when the number of parts, users, contributors or the amount of data grows"),
        ("redundancy", "what is superfluous or duplicated"),
        ("gaps", "what is missing that the requirements or the structure itself call for"),
        ("operability", "can the people who own it run, change, debug and recover it"),
        ("requirements_fit", "does the structure meet the stated requirements and constraints"),
    ],
    "solution": [
        ("requirements_coverage", "is each stated need met, met only partly, or not addressed"),
        ("user_flow", "can the user get through each task from start to end; dead ends and missing steps"),
        ("data_model", "entities, keys, ownership and lifecycle of the data; what is stored where"),
        ("integration", "interfaces to other systems, their contracts, and failure handling across those boundaries"),
        ("security_privacy", "access control, secrets, personal data, and what leaves the owner's control"),
        ("operation_and_cost", "who runs it, monitoring and recovery, and the cost to build and to run"),
        ("simpler_alternative", "is there a smaller or already existing solution that meets the same need"),
        ("delivery_risk", "what can make it late, unbuildable or unusable; dependencies and unknowns"),
    ],
    "product": [
        ("target_user", "is it clear who the product is for, and is that group concrete enough to design for"),
        ("problem", "is the problem stated, real for that user, and worth solving"),
        ("unsupported_assumptions", "claims the proposal rests on that the material gives no support for"),
        ("scope_boundary", "what is in, what is out, and where the line is unclear or will creep"),
        ("value_and_differentiation", "why this, compared with what the user does today or can already get"),
        ("risks", "what can make it fail: market, legal, technical, dependencies"),
        ("success_measure", "how anyone will know it worked, and whether that can be measured"),
    ],
    "design": [
        ("task_support", "does the design support the task the user must do"),
        ("hierarchy", "is the most important thing the first thing the eye meets; grouping and order"),
        ("readability", "can text, numbers and labels be read and understood at the size shown"),
        ("consistency", "are the same things shown the same way: colours, terms, formats, alignment"),
        ("accessibility", "contrast, colour as the only signal, text size"),
        ("data_presentation", "chart choice, labels, units, scales, and whether the numbers can be misread"),
    ],
}

MODES = [DEFAULT_MODE, *MODE_DIMENSIONS]

# Per mode: what is reviewed, the level to review at, how `location` is defined.
_MODE_FRAMING: dict[str, tuple[str, str, str]] = {
    "architecture": (
        "the architecture of a system",
        "structure, that is components, layers, responsibilities and the dependencies between them, "
        "not line-level procedure",
        "the component, layer, file or section the finding is about",
    ),
    "solution": (
        "a proposed app or solution",
        "the solution end to end against the stated need (functions, data, integration, security, "
        "operation and cost), not implementation detail inside one file",
        "the part of the solution, the section of the proposal, or the file the finding is about",
    ),
    "product": (
        "a product proposal",
        "the proposal as a product (who it is for, which problem it solves, what it assumes, where its "
        "scope ends), not its wording or layout",
        "the section or the statement of the proposal the finding is about",
    ),
    "design": (
        "a visual design (a report page, a website or an app screen)",
        "what a user sees and must do with it, that is the screen as a whole and its regions, not the "
        "code behind it",
        "the image label and the screen region or visual (for example `image 1, top-left chart`), or the "
        "file and section for text material",
    ),
}

_MODE_EXTRA_RULES: dict[str, list[str]] = {
    "design": [
        "Judge only what the images and the text show. Do not guess colours, text or data you cannot "
        "see. A dimension you cannot judge because an image is missing, too small or unclear is "
        "not_assessable.",
    ],
}


def _build_mode_prompt(mode: str) -> str:
    """Build the system prompt of a non-code mode from its rubric and framing."""
    subject, level, location = _MODE_FRAMING[mode]
    dimensions = ";\n".join(f"- {name}: {question}" for name, question in MODE_DIMENSIONS[mode])
    extra = "".join(f"- {rule}\n" for rule in _MODE_EXTRA_RULES.get(mode, []))
    return (
        f"You are an independent senior reviewer giving a second opinion on {subject}. You are "
        "adversarial by design: your job is to find what is wrong, missing or risky, "
        "not to reassure. Assume the author is competent but has blind spots.\n"
        "\n"
        f"Review the MATERIAL against the REQUIREMENTS at the level of the material: {level}. "
        "Line-level bugs in a single file are out of scope unless they show a structural problem; "
        "then report the structural problem and use the line as its evidence.\n"
        "\n"
        "Assess each of these dimensions. The id before the colon is the `category` of a finding "
        "and the `dimension` of a coverage item:\n"
        f"{dimensions}.\n"
        "\n"
        "Findings:\n"
        f"- `location` is {location}.\n"
        "- `evidence` is a verbatim quote from the material, or the named element (file, section, "
        "component, page, or a visual and its position in the image) that shows the issue. Only "
        "report findings whose evidence a reader can look up in the material.\n"
        "- If you are unsure, say so in the finding; do not invent certainty.\n"
        "- Do not pad. An empty findings list is a valid answer if the material is sound.\n"
        "- Images, when attached, are listed in the MATERIAL section as `image N: <file name>`. "
        "Refer to an image by that label.\n"
        f"{extra}"
        "\n"
        "Coverage:\n"
        "- Give exactly one coverage item for every dimension, also for a dimension with no findings.\n"
        "- `assessment` is problems_found, no_problems_found or not_assessable. `basis` names what in "
        "the material the assessment rests on, or why the dimension could not be assessed.\n"
        "- not_assessable is a valid and expected answer when the material does not show enough to "
        "judge a dimension. Do not guess to fill it.\n"
        "- The summary must not call anything sound, good or well done unless the coverage item for "
        "that dimension says no_problems_found with a basis.\n"
        "- If a FOCUS is given, answer it in the summary, or say that the material does not let you "
        "answer it.\n"
        "\n"
        "Rules:\n"
        "- You have not seen the author's own review or conclusions. Do not guess them.\n"
        "- Answer in English, as JSON matching the response schema."
    )


def _build_mode_schema(mode: str) -> dict[str, Any]:
    """Build the response schema of a non-code mode.

    Same finding fields as RESPONSE_SCHEMA plus `category` and `evidence`, and
    a top-level `coverage` list. Coverage and findings are ordered before the
    summary and the verdict, so the model writes the conclusion last.
    """
    dimension_ids = [name for name, _ in MODE_DIMENSIONS[mode]]
    return {
        "type": "OBJECT",
        "properties": {
            "coverage": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "dimension": {"type": "STRING", "enum": dimension_ids},
                        "assessment": {"type": "STRING", "enum": COVERAGE_ASSESSMENTS},
                        "basis": {"type": "STRING"},
                    },
                    "required": ["dimension", "assessment", "basis"],
                    "propertyOrdering": ["dimension", "assessment", "basis"],
                },
            },
            "findings": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "severity": {"type": "STRING", "enum": SEVERITIES},
                        "category": {"type": "STRING", "enum": dimension_ids},
                        "location": {"type": "STRING"},
                        "evidence": {"type": "STRING"},
                        "issue": {"type": "STRING"},
                        "why_it_matters": {"type": "STRING"},
                        "suggested_fix": {"type": "STRING"},
                        "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                    },
                    "required": [
                        "severity",
                        "category",
                        "location",
                        "evidence",
                        "issue",
                        "why_it_matters",
                        "suggested_fix",
                    ],
                    "propertyOrdering": [
                        "severity",
                        "category",
                        "location",
                        "evidence",
                        "issue",
                        "why_it_matters",
                        "suggested_fix",
                        "confidence",
                    ],
                },
            },
            "summary": {"type": "STRING"},
            "verdict": {"type": "STRING", "enum": VERDICTS},
        },
        "required": ["coverage", "findings", "summary", "verdict"],
        "propertyOrdering": ["coverage", "findings", "summary", "verdict"],
    }


SYSTEM_PROMPTS: dict[str, str] = {
    DEFAULT_MODE: SYSTEM_PROMPT,
    **{mode: _build_mode_prompt(mode) for mode in MODE_DIMENSIONS},
}
RESPONSE_SCHEMAS: dict[str, dict[str, Any]] = {
    DEFAULT_MODE: RESPONSE_SCHEMA,
    **{mode: _build_mode_schema(mode) for mode in MODE_DIMENSIONS},
}

# --------------------------------------------------------------------------
# Prices. USD per 1 million tokens, paid tier, Standard.
# Source: https://aistudio.google.com/docs/pricing
# Provenance: the page was read through a summarising fetch tool on
# 2026-11-25. The gemini-3.1-pro-preview numbers came from verbatim text. The
# other rows were NOT seen verbatim. Every cost this script prints is an
# estimate from this table, not a number from Google's billing.
# The table is keyed on the RESOLVED model version from the API response
# (`modelVersion`), never on the alias given with --model. Exact match only.
# --------------------------------------------------------------------------

PRICES_AS_OF = "2026-11-25"
TOKENS_PER_PRICE_UNIT = 1_000_000

# Fixed rate, no network call. Source: api.frankfurter.dev, rate of 2026-11-24.
USD_DKK_RATE = 6.8178
USD_DKK_RATE_DATE = "2026-11-24"
USD_DKK_ENV_VAR = "SECOND_OPINION_USD_DKK"


@dataclass(frozen=True)
class PriceTier:
    """One price level. `max_prompt_tokens` None means no upper bound."""

    max_prompt_tokens: int | None
    input_usd: float
    output_usd: float
    label: str


@dataclass(frozen=True)
class PriceRow:
    """The tiers of one model that apply from `effective_from` (inclusive)."""

    effective_from: date
    tiers: tuple[PriceTier, ...]


def _flat(input_usd: float, output_usd: float, effective_from: date = date.min) -> PriceRow:
    return PriceRow(effective_from, (PriceTier(None, input_usd, output_usd, "flat"),))


# gemini-3.6-flash and gemini-3.8-flash: one price up to and including
# 2026-12-31, another from 2027-01-01. The row is picked by the call date.
_FLASH_ROWS = (_flat(0.75, 3.75), _flat(1.50, 7.50, date(2027, 1, 1)))

PRICE_TABLE: dict[str, tuple[PriceRow, ...]] = {
    # The tier is chosen by promptTokenCount and applies to both the input and
    # the output of that call. 200,000 prompt tokens is still the low tier.
    "gemini-3.1-pro-preview": (
        PriceRow(
            date.min,
            (
                PriceTier(200_000, 2.00, 12.00, "<=200k"),
                PriceTier(None, 4.00, 18.00, ">200k"),
            ),
        ),
    ),
    "gemini-3-flash-preview": (_flat(0.50, 3.00),),
    "gemini-3.1-flash-lite": (_flat(0.25, 1.50),),
    "gemini-3.5-flash-lite": (_flat(0.30, 2.50),),
    "gemini-3.6-flash": _FLASH_ROWS,
    "gemini-3.8-flash": _FLASH_ROWS,
}

# --------------------------------------------------------------------------
# Images. PNG, JPEG and WEBP only: the three types on both of Google's lists
# (API reference for generateContent and the image guide, read 2026-11-25).
# The image guide gives 20MB for the whole request with inline image data;
# the decimal reading (20,000,000 bytes) is used because it is the stricter.
# --------------------------------------------------------------------------

IMAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/webp": (".webp",),
}
MAX_REQUEST_BYTES = 20_000_000


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


@dataclass(frozen=True)
class ImagePart:
    """One image to send: its file name, detected MIME type and raw bytes."""

    name: str
    mime_type: str
    data: bytes


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


def refusal_text(path_reasons: Sequence[str], images: Sequence[Path]) -> str:
    """Word a guard refusal: unapproved paths, unapproved images, or both.

    `path_reasons` are the reasons from `check_guard` that no
    --customer-approved covers. `images` are the images that no
    --images-approved covers.
    """
    sections: list[str] = []
    if path_reasons:
        sections.append(
            "Material is not from an owned repo:\n"
            + "\n".join(f"  - {r}" for r in path_reasons)
            + "\nCustomer or unknown material needs Benny's explicit yes for this run; "
            "only then rerun with --customer-approved."
        )
    if images:
        sections.append(
            "Images need Benny's explicit yes for this run, wherever the file lies:\n"
            + "\n".join(f"  - image {i}: {path}" for i, path in enumerate(images, start=1))
            + "\nThe path guard cannot see what a picture shows: a screenshot of a customer's "
            "report saved in an owned repo passes it. Only after his explicit yes to send exactly "
            "these images, rerun with --images-approved."
        )
    return "\n".join(sections)


# --------------------------------------------------------------------------
# Request building and response parsing (pure)
# --------------------------------------------------------------------------


def build_user_prompt(
    requirements: str,
    material: list[tuple[str, str]],
    focus: str | None,
    image_names: Sequence[str] = (),
) -> str:
    """Assemble the user turn: requirements, optional focus, then raw material.

    Images are not text, so the prompt only lists them by label
    (`image 1: <file name>`), in the order their parts follow the text part.
    """
    sections = ["## REQUIREMENTS", requirements.strip() or "(none given)"]
    if focus:
        sections += ["## FOCUS", focus.strip()]
    sections.append("## MATERIAL")
    for label, content in material:
        sections += [f"### {label}", "```", content.rstrip(), "```"]
    if image_names:
        listing = "\n".join(f"image {i}: {name}" for i, name in enumerate(image_names, start=1))
        sections += ["### images (attached after this text, in this order)", listing]
    return "\n\n".join(sections)


def detect_image_type(data: bytes) -> str | None:
    """Return the MIME type from the magic bytes: PNG, JPEG or WEBP, else None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_image(name: str, data: bytes) -> str:
    """Return the MIME type of an image, or raise if it may not be sent.

    The type comes from the magic bytes. The file extension must agree with
    it, so a file is never sent as something other than what its name says.
    """
    mime_type = detect_image_type(data)
    if mime_type is None:
        raise SecondOpinionError(
            f"image {name}: not a PNG, JPEG or WEBP file by its magic bytes (only those three types are sent)"
        )
    suffix = Path(name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS[mime_type]:
        raise SecondOpinionError(
            f"image {name}: the content is {mime_type} but the extension is '{suffix}' "
            f"(expected {' or '.join(IMAGE_EXTENSIONS[mime_type])})"
        )
    return mime_type


def check_request_size(body_bytes: int, limit: int | None = None) -> None:
    """Refuse a request body over the inline-image limit, naming the size."""
    limit = MAX_REQUEST_BYTES if limit is None else limit
    if body_bytes > limit:
        raise SecondOpinionError(
            f"request body is {body_bytes:,} bytes ({body_bytes / 1_000_000:.1f} MB), over the "
            f"{limit:,} byte limit for a request with inline images; send fewer or smaller images"
        )


def build_payload(
    user_prompt: str,
    use_schema: bool,
    thinking_level: str | None = None,
    mode: str = DEFAULT_MODE,
    images: Sequence[ImagePart] = (),
) -> dict[str, Any]:
    """Build the generateContent request body.

    `thinking_level` is one of THINKING_LEVELS. When it is None no
    `thinkingConfig` key is sent at all, so the model's own default applies.
    `mode` selects the system prompt and the response schema. Each image
    becomes an `inlineData` part after the text part, in the order given.
    """
    if mode not in SYSTEM_PROMPTS:
        raise SecondOpinionError(f"unknown mode '{mode}' (choose from: {', '.join(MODES)})")
    generation_config: dict[str, Any] = {"responseMimeType": "application/json"}
    if use_schema:
        generation_config["responseSchema"] = RESPONSE_SCHEMAS[mode]
    if thinking_level is not None:
        if thinking_level not in THINKING_LEVELS:
            raise SecondOpinionError(
                f"unknown thinking level '{thinking_level}' (choose from: {', '.join(THINKING_LEVELS)})"
            )
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level.upper()}
    parts: list[dict[str, Any]] = [{"text": user_prompt}]
    for image in images:
        encoded = base64.b64encode(image.data).decode("ascii")
        parts.append({"inlineData": {"mimeType": image.mime_type, "data": encoded}})
    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPTS[mode]}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
    }


def payload_for_display(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy a request body with image data replaced by a size placeholder.

    Used by --dry-run, so a dry run never dumps megabytes of base64.
    """
    shown = copy.deepcopy(payload)
    for content in shown.get("contents", []):
        for part in content.get("parts", []):
            blob = part.get("inlineData")
            if blob is not None:
                encoded = blob["data"]
                raw_bytes = len(encoded) * 3 // 4 - encoded[-2:].count("=")
                blob["data"] = f"<base64 omitted, {raw_bytes} bytes>"
    return shown


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


def parse_findings(response: dict[str, Any], mode: str = DEFAULT_MODE) -> dict[str, Any]:
    """Parse the model's JSON answer and check it has the expected shape.

    Tolerant on purpose: outside code mode a missing or malformed `coverage`
    becomes an empty list instead of an error.
    """
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
    if mode != DEFAULT_MODE and not isinstance(answer.get("coverage"), list):
        answer["coverage"] = []
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


USAGE_FIELDS = ["promptTokenCount", "thoughtsTokenCount", "candidatesTokenCount", "totalTokenCount"]


def usage_counts(response: dict[str, Any]) -> dict[str, int]:
    """Return the four token counts as integers (0 when the API left one out)."""
    usage = response.get("usageMetadata") or {}
    return {field: int(usage.get(field) or 0) for field in USAGE_FIELDS}


def find_price(
    model_version: str,
    prompt_tokens: int,
    call_date: date,
    table: Mapping[str, tuple[PriceRow, ...]] = PRICE_TABLE,
) -> PriceTier | None:
    """Look up the price tier for a resolved model version on a call date.

    Exact match on the model version; no prefix matching. Returns None when
    the model is not in the table or no row is in effect on `call_date`.
    """
    rows = [row for row in table.get(model_version, ()) if row.effective_from <= call_date]
    if not rows:
        return None
    row = max(rows, key=lambda r: r.effective_from)
    for tier in row.tiers:
        if tier.max_prompt_tokens is None or prompt_tokens <= tier.max_prompt_tokens:
            return tier
    return None


def estimate_cost(
    model_version: str,
    usage: Mapping[str, Any],
    call_date: date,
    usd_dkk_rate: float = USD_DKK_RATE,
    usd_dkk_rate_source: str = f"fixed, {USD_DKK_RATE_DATE}",
    price_override: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Estimate the cost of one call from its usageMetadata.

    Thought tokens are billed at the output price. All prompt tokens are
    priced at the full input price: the cache discount is not modelled, so
    with cached tokens the figure is an upper bound. `price_override` is
    (input, output) in USD per 1M tokens and wins over the table.
    """
    prompt = int(usage.get("promptTokenCount") or 0)
    output = int(usage.get("thoughtsTokenCount") or 0) + int(usage.get("candidatesTokenCount") or 0)
    cached = int(usage.get("cachedContentTokenCount") or 0)
    cost: dict[str, Any] = {
        "usd": None,
        "dkk": None,
        "estimate": True,
        "model_version": model_version,
        "prices_as_of": PRICES_AS_OF,
        "tier": None,
        "usd_dkk_rate": usd_dkk_rate,
        "usd_dkk_rate_source": usd_dkk_rate_source,
        "cached_tokens_at_full_rate": cached > 0,
        "note": "",
    }
    if price_override is not None:
        input_usd, output_usd = price_override
        cost["prices_as_of"] = None
        cost["tier"] = "override"
        notes = [
            f"Prices from --price-in/--price-out ({input_usd:g} in, {output_usd:g} out, "
            "USD per 1M tokens, flat), not from the price table."
        ]
    else:
        tier = find_price(model_version, prompt, call_date)
        if tier is None:
            cost["reason"] = (
                f"price unknown for model version '{model_version}': not in the price table "
                f"as of {PRICES_AS_OF} (exact match only). Pass --price-in and --price-out to price it."
            )
            cost["note"] = cost["reason"]
            return cost
        input_usd, output_usd = tier.input_usd, tier.output_usd
        cost["tier"] = tier.label
        notes = [
            f"Estimate from a price table dated {PRICES_AS_OF} ({input_usd:g} in, {output_usd:g} out, "
            "USD per 1M tokens), not a number from Google's billing."
        ]
    notes.append("Thought tokens are priced at the output price.")
    if cached > 0:
        notes.append(
            f"{cached} cached prompt tokens were priced at the full input rate, so the figure is an upper bound."
        )
    usd = (prompt * input_usd + output * output_usd) / TOKENS_PER_PRICE_UNIT
    cost["usd"] = round(usd, 6)
    cost["dkk"] = round(usd * usd_dkk_rate, 4)
    cost["note"] = " ".join(notes)
    return cost


def cost_line(cost: Mapping[str, Any]) -> str:
    """Format the cost estimate as one stderr line."""
    if cost["usd"] is None:
        return f"cost (estimate): {cost['reason']}"
    if cost["tier"] == "override":
        prices = "prices from --price-in/--price-out (override, flat)"
    else:
        prices = f"prices as of {cost['prices_as_of']} (table), tier {cost['tier']}"
    line = (
        f"cost (estimate): {cost['usd']:.4f} USD = {cost['dkk']:.2f} DKK | {prices} | "
        f"1 USD = {cost['usd_dkk_rate']:g} DKK ({cost['usd_dkk_rate_source']})"
    )
    if cost["cached_tokens_at_full_rate"]:
        line += " | cached tokens priced at the full input rate (upper bound)"
    return line


def parse_positive_number(text: str, allow_zero: bool = False) -> float:
    """Parse a finite number above zero (or from zero); raise ValueError if not."""
    value = float(text)
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"not a usable number: {text!r}")
    return value


def resolve_usd_dkk(flag_value: float | None, env: Mapping[str, str]) -> tuple[float, str]:
    """Pick the USD to DKK rate: the flag, else the env var, else the constant.

    Returns the rate and where it came from. A bad env value raises
    ValueError; it is never replaced by the constant in silence.
    """
    if flag_value is not None:
        return flag_value, "from --usd-dkk"
    env_text = env.get(USD_DKK_ENV_VAR, "").strip()
    if env_text:
        try:
            return parse_positive_number(env_text), f"from env {USD_DKK_ENV_VAR}"
        except ValueError:
            raise ValueError(
                f"environment variable {USD_DKK_ENV_VAR} is not a usable rate: {env_text!r}"
            ) from None
    return USD_DKK_RATE, f"fixed, {USD_DKK_RATE_DATE}"


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


def read_material(
    diff_path: str | None,
    files: list[Path],
    context_path: str | None = None,
    context_label: str | None = None,
    has_images: bool = False,
) -> list[tuple[str, str]]:
    """Read context, diff and files into labelled blocks.

    The diff and the context are a file or '-' for stdin. Context is text
    that is material but not a diff; it is labelled `context: <label>`.
    """
    material: list[tuple[str, str]] = []
    if context_path == "-":
        text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        material.append((f"context: {context_label or 'stdin'}", text))
    elif context_path:
        label = context_label or Path(context_path).name
        material.append((f"context: {label}", Path(context_path).read_text(encoding="utf-8")))
    if diff_path == "-":
        # Read bytes and decode as UTF-8: on Windows a text-mode pipe would use
        # the locale codepage and mangle (or fail on) a UTF-8 git diff.
        material.append(("diff (stdin)", sys.stdin.buffer.read().decode("utf-8", errors="replace")))
    elif diff_path:
        material.append((f"diff: {Path(diff_path).name}", Path(diff_path).read_text(encoding="utf-8")))
    for path in files:
        material.append((f"file: {path.as_posix()}", path.read_text(encoding="utf-8")))
    if not has_images and (not material or not any(content.strip() for _, content in material)):
        raise SecondOpinionError(
            "no material to review (give --diff, --files, --context and/or --images, "
            "and make sure they are not empty)"
        )
    return material


def read_images(paths: Sequence[Path]) -> list[ImagePart]:
    """Read each image and check its type from the magic bytes."""
    images: list[ImagePart] = []
    for path in paths:
        data = path.read_bytes()
        images.append(ImagePart(name=path.name, mime_type=check_image(path.name, data), data=data))
    return images


def _timeout_message(timeout: int) -> str:
    return f"Gemini did not answer within {timeout}s (raise --timeout)"


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
        # A timeout while connecting is wrapped: URLError with a TimeoutError
        # as its reason. Report it like the bare TimeoutError below.
        if isinstance(exc.reason, TimeoutError):
            raise SecondOpinionError(_timeout_message(timeout)) from None
        raise SecondOpinionError(f"network error calling Gemini: {redact(str(exc.reason), api_key)}") from None
    except TimeoutError:
        # Reached when the server accepts the request and then does not answer.
        raise SecondOpinionError(_timeout_message(timeout)) from None


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _rate_argument(text: str) -> float:
    try:
        return parse_positive_number(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a usable rate: {text!r}") from None


def _price_argument(text: str) -> float:
    try:
        return parse_positive_number(text, allow_zero=True)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a usable price: {text!r}") from None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get a second opinion from Gemini. See ../SKILL.md.")
    req = parser.add_mutually_exclusive_group(required=True)
    req.add_argument("--requirements", type=Path, help="file with the requirements text")
    req.add_argument("--requirements-text", help="requirements given inline")
    parser.add_argument("--diff", help="diff file to review, or '-' to read it from stdin")
    parser.add_argument("--files", type=Path, nargs="*", default=[], help="code or design files to review")
    parser.add_argument(
        "--mode",
        choices=MODES,
        default=DEFAULT_MODE,
        help=(
            "kind of review, which selects the system prompt and the response schema "
            f"(default: {DEFAULT_MODE}): code for code and diffs, architecture for how one system is "
            "structured, solution for a proposed app or solution against a stated need, product for a "
            "product proposal, design for a visual design (use --images)"
        ),
    )
    parser.add_argument(
        "--context",
        help="text that is material but not a diff (an overview, a design note, a proposal): a file, or '-' for stdin",
    )
    parser.add_argument("--context-label", help="label for the context block (default: the file name, or 'stdin')")
    parser.add_argument(
        "--images",
        type=Path,
        nargs="+",
        default=[],
        help="PNG, JPEG or WEBP images to send with the text; every run with images needs --images-approved",
    )
    parser.add_argument(
        "--images-approved",
        action="store_true",
        help=(
            "Benny has explicitly approved sending exactly these images, for this run only. "
            "Does not replace --customer-approved"
        ),
    )
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
    parser.add_argument(
        "--thinking-level",
        choices=THINKING_LEVELS,
        default=None,
        help=(
            "cap the model's reasoning depth (sent as generationConfig.thinkingConfig.thinkingLevel); "
            "default: not sent, the model's own default applies. Not validated per model; "
            "what the API does with a level the model does not support is not verified"
        ),
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="HTTP timeout in seconds")
    parser.add_argument("--no-schema", action="store_true", help="do not send responseSchema (JSON is still requested)")
    parser.add_argument("--dry-run", action="store_true", help="run the guard and print the request body; no network call")
    parser.add_argument(
        "--usd-dkk",
        type=_rate_argument,
        default=None,
        metavar="RATE",
        help=(
            f"DKK per USD for the cost estimate (default: env {USD_DKK_ENV_VAR}, "
            f"else the fixed rate {USD_DKK_RATE} of {USD_DKK_RATE_DATE})"
        ),
    )
    parser.add_argument(
        "--price-in",
        type=_price_argument,
        default=None,
        metavar="USD",
        help="input price in USD per 1M tokens; overrides the price table (flat, needs --price-out)",
    )
    parser.add_argument(
        "--price-out",
        type=_price_argument,
        default=None,
        metavar="USD",
        help="output price in USD per 1M tokens, thought tokens included (flat, needs --price-in)",
    )
    args = parser.parse_args(argv)
    if (args.price_in is None) != (args.price_out is None):
        parser.error("--price-in and --price-out must be given together")
    if args.diff == "-" and args.context == "-":
        parser.error("--diff - and --context - cannot both read stdin; give one of them as a file")
    if args.context_label is not None and args.context is None:
        parser.error("--context-label needs --context")
    try:
        args.usd_dkk_rate, args.usd_dkk_rate_source = resolve_usd_dkk(args.usd_dkk, os.environ)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def run(args: argparse.Namespace) -> int:
    input_files = list(args.files)
    if args.requirements:
        input_files.append(args.requirements)
    if args.diff and args.diff != "-":
        input_files.append(Path(args.diff))
    if args.context and args.context != "-":
        input_files.append(Path(args.context))
    image_paths = list(args.images)
    input_files += image_paths

    # Two guards, both default-deny. The path guard asks where the material
    # lies. The image guard asks for a yes on every image run, because a path
    # says nothing about what a picture shows. Neither flag replaces the other.
    reasons = check_guard(args.source_repo, input_files, args.customer_approved)
    unapproved_paths = reasons if not args.customer_approved else []
    unapproved_images = image_paths if not args.images_approved else []
    if unapproved_paths or unapproved_images:
        raise GuardRefusal(refusal_text(unapproved_paths, unapproved_images))
    if reasons:
        print("data guard: overridden by --customer-approved for:", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)

    requirements = (
        args.requirements_text
        if args.requirements_text is not None
        else args.requirements.read_text(encoding="utf-8")
    )
    material = read_material(
        args.diff,
        list(args.files),
        context_path=args.context,
        context_label=args.context_label,
        has_images=bool(image_paths),
    )
    images = read_images(image_paths)
    if images:
        print("data guard: images released by --images-approved (inline data):", file=sys.stderr)
        for number, (path, image) in enumerate(zip(image_paths, images), start=1):
            print(f"  - image {number}: {path} ({len(image.data):,} bytes, {image.mime_type})", file=sys.stderr)
    user_prompt = build_user_prompt(requirements, material, args.focus, [image.name for image in images])
    payload = build_payload(
        user_prompt,
        use_schema=not args.no_schema,
        thinking_level=args.thinking_level,
        mode=args.mode,
        images=images,
    )
    if images:
        check_request_size(len(json.dumps(payload).encode("utf-8")))
    request_line = f"request: model={args.model} mode={args.mode} prompt_chars={len(user_prompt)}"
    if images:
        request_line += f" images={len(images)}"
    if args.thinking_level is not None:
        request_line += f" thinking_level={args.thinking_level}"
    print(request_line, file=sys.stderr)

    if args.dry_run:
        print(json.dumps(payload_for_display(payload), indent=2, ensure_ascii=False))
        print("dry run: no network call made", file=sys.stderr)
        return 0

    api_key = get_api_key()
    response = call_gemini(args.model, payload, api_key, args.timeout)
    for line in usage_lines(response):
        print(line, file=sys.stderr)
    model_version = response.get("modelVersion", "unknown")
    price_override = (args.price_in, args.price_out) if args.price_in is not None else None
    cost = estimate_cost(
        model_version,
        response.get("usageMetadata") or {},
        call_date=datetime.now(timezone.utc).date(),
        usd_dkk_rate=args.usd_dkk_rate,
        usd_dkk_rate_source=args.usd_dkk_rate_source,
        price_override=price_override,
    )
    print(cost_line(cost), file=sys.stderr)
    answer = parse_findings(response, args.mode)
    # Set by the script from API metadata; never part of the responseSchema.
    answer["mode"] = args.mode
    answer["model_version"] = model_version
    answer["usage"] = usage_counts(response)
    answer["cost"] = cost
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
        print(f"data guard: REFUSED, nothing was sent. {exc}", file=sys.stderr)
        return 2
    except SecondOpinionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not read input: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
