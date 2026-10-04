# Brain OpenKit Agent Workflows Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or
> superpowers:executing-plans to implement and review each deliverable.

**Goal:** Execute the existing roadmap and make evidence-grounded knowledge
workflows usable from both Claude Code and Codex.

**Architecture:** One Python CLI, shared portable skills, separate decision
adapters and an auditable preview/apply/undo layer. Host models write drafts;
the core preserves sources and validates changes.

**Tech Stack:** Python >=3.11 standard library, SQLite, JSON, Markdown, portable
Agent Skills, Claude/Codex plugin manifests.

**Spec:** [Agent workflows design](../specs/2026-10-04-agent-workflows-design.md)

Implementation task status is supported by the
[verification record](../../implementation-notes.md) and
[roadmap evidence matrix](../../roadmap-evidence.md). A checked conditional Jev
verification task records the missing live key; it does not claim live inference.
The original real-vault quality targets (30 user-reviewed retrieval queries and
50 classification/tag examples) remain separate, unmet acceptance work.

## Global constraints

- No mandatory third-party runtime dependencies; Python >=3.11.
- UTF-8 output and source preservation on Windows, macOS and Linux.
- Explicit vault, provider opt-in, environment-only credentials.
- All changes previewed and hash-checked; external edits survive recovery.
- No copied reference implementation; distinguish actual-host and fixture tests.

## Review focus

- Paths redirected by symlinks between preview and apply must not escape vault.
- Second-file failures must not strand an unreported partial change.
- Undo must refuse stale postimages, including newly created files edited later.
- Plugin caches and paths with spaces must work without editable installation.
- Non-ASCII and HTML-looking source text must survive CLI and browser rendering.

## 1. Change journal

Files: `src/brain_openkit/changes.py`, `tests/test_changes.py`.

Interfaces: `make_plan(vault, changes, label)->dict`,
`apply_plan(vault, plan, expected_id)->dict`, `undo(vault, transaction_id)->dict`.
Changes are `{"path": "Notes/note.md", "content": "# Note\n"}` records.

- [x] Add failing tests for create/update, two-file preflight conflicts, symlink
  escape, interrupted apply and stale undo. Example:
  `plan=make_plan(vault,[{"path":"n.md","content":"new\n"}],"save")`;
  alter `n.md`; assert apply raises and all original files are unchanged.
- [x] Implement bounded serializable preimages, SHA-256 plan IDs, diffs, atomic
  individual writes, exclusive journal lock and deterministic recovery.
- [x] Run `python -m unittest discover -s tests -p test_changes.py -v` and review.

## 2. Wiki workflows

Files: `src/brain_openkit/notes.py`, `tests/test_notes.py`.

Interfaces: plan constructors consume change journal; read-only `lint(vault)`.
`plan_init(vault)`, `plan_ingest(vault,source,title,draft=None,source_url=None)`,
`plan_save(vault,path,content,sources=None)`,
`plan_organize(vault,note,category=None,tags=None,links=None)`,
`plan_fold(vault,notes,path,title)` all return a preview plan.

- [x] Test exact CRLF source capture, existing-vault adoption, duplicate import,
  source-linked notes/index, safe frontmatter and missing/ambiguous wikilinks.
- [x] Implement deterministic extractive defaults and host-supplied prose via
  the same save path; keep children when folding.
- [x] Test init→apply→ingest→apply→search→organize→apply→lint→undo.

## 3. Replaceable providers

Files: adapter module, `providers.py`, `workflows.py`, provider tests; CLI wiring
is owned by the integration task to avoid concurrent edits.

- [x] Record official Jev API endpoint, auth, model and response contract.
- [x] Write local HTTP-fixture tests for auth, valid choice, malformed
  probabilities, oversized data, errors and secret-free diagnostics.
- [x] Implement Jev with explicit provider identity and no automatic failover.
- [x] Verify missing-key behavior and a live synthetic request if a key exists;
  otherwise record the live-service dependency explicitly.

## 4. Shared host integration

Files: `skills/**`, `scripts/brain-openkit.py`, host manifests/catalog,
`tests/test_packaging.py`, `docs/agent-integration.md`.

- [x] Write original shared init/search/organize/ingest/save/lint/fold/research
  skills with exact CLI contracts and source-as-data instructions.
- [x] Add root-relative standard-library runner and Claude/Codex manifests.
- [x] Validate both Claude manifest files individually and actual skill
  discovery; install Codex catalog in an isolated home and inspect discovery.
- [x] Execute real host search and write/undo loops on temporary vaults;
  independently inspect files, citations and read-only hashes. Interrupted
  transaction recovery is covered separately by core tests.

## 5. Broader evaluation

Files: `benchmarks/**`, evaluator additions and tests as needed.

- [x] Write a bilingual corpus and independent held-out relevance labels
  before measuring or changing ranking. Preserve development/holdout separation.
- [x] Measure BM25 and actual Laya, retain raw outputs, checkpoint/version,
  cold/warm timing context, false matches and misses. Do not tune on holdout.
- [x] Add classification/tag metrics with fixed labels if available and record
  unsupported generalizations rather than declaring quality from smoke checks.

## 6. CLI and local UI

Files: `cli.py`, `web.py`, `tests/test_cli.py`, `tests/test_web.py`.

- [x] Expose plan commands with `--plan FILE`, apply with `--approve PLAN_ID`,
  undo by transaction ID, and provider-specific settings without secrets.
- [x] Add loopback-only `web` with read-only search, request bounds, safe DOM
  text rendering and host/origin checks; no remote scripts or write endpoints.
- [x] Verify installed CLI and browser searches, JSON errors, Korean output,
  fallback and source preservation.

## 7. Release evidence

Files: READMEs, implementation notes, attribution, CI, roadmap.

- [x] Run complete Python 3.11/3.13 tests and host validations: each local suite
  reported 159 tests, OK with four Windows-only skips; both hosts completed
  cited search and write/undo flows.
- [x] Build distributions and verify a clean offline wheel installation in a
  new Python 3.13 environment: 17 CLI commands, five transactions reversed, and
  original Markdown hashes restored. Inspect all eight skills, shared runtime,
  runner, and four host manifests in the source distribution.
- [x] Obtain independent full-diff review and resolve actionable findings.
- [x] Update each roadmap item with implementation and verification evidence;
  leave unmet requirements explicitly open.
- [x] Publish branch and attach [draft PR #1](https://github.com/hyeondata/brain-openkit/pull/1);
  all six [CI jobs at `33d3a42`](https://github.com/hyeondata/brain-openkit/actions/runs/37210403995)
  passed. The earlier `9075acb` matrix remains historical evidence only.
- [x] Audit implementation and acceptance evidence, including clean installation,
  publication/CI, and both hosts' actual workflows. Live Jev and user-reviewed
  real-vault quality remain explicitly open follow-up requirements; no production
  quality or model-superiority claim is made.
