# Brain OpenKit agent workflows

Status: release validation. Implementation, local/actual-host checks, clean
build/install, and the acceptance evidence audit are complete; publication/PR
and current-revision CI remain pending. This extends the approved CLI design under
the user's instruction to execute and verify the roadmap autonomously. See
[implementation evidence](../../implementation-notes.md) for completed checks
and separately unmet live-service and real-vault quality targets.

## Intended outcome

Install one independently implemented toolkit in Claude Code or Codex, point it
at an explicit Markdown vault, then initialize/adopt, ingest supplied sources,
search with citations, save selected knowledge, organize, inspect health and
recover changes. The same operations remain usable directly from a local CLI.
Laya supplies optional local decisions. Jev supplies explicitly selected hosted
decisions. Claude/Codex supply optional prose generation; no Laya generation is
claimed. Existing source notes remain unchanged during search and classification.

## Approach

Use shared `skills/` and host manifests around the Python CLI. This mirrors the
reference project's portable skill architecture without copying its code or
templates. MCP is not required for this release: both hosts can run the CLI and
consume JSON, avoiding a second protocol with the same operations. A loopback
read-only web interface satisfies the existing alternative UI roadmap item.

Compared with a host-specific extension, shared skills preserve one workflow
contract. Compared with an MCP-only interface, the CLI remains directly usable
and testable without an agent session. A future MCP wrapper can reuse it.

## Constraints and contracts

- Python >=3.11; no mandatory third-party runtime dependencies.
- UTF-8 Markdown; Windows, macOS and Linux; preserve original newline bytes.
- Require an explicit vault. Reject traversal, symlink paths and protected paths.
- Never silently send local content to Jev or another remote provider.
- Credentials come from environment variables, never vault/config/plan files.
- Changed files require a preview plan with original hashes and explicit apply.
- Check every expected preimage before writing; recover only bytes still matching
  the transaction's postimages. Never overwrite a subsequent user edit on undo.
- Keep source captures immutable and retain provenance (path/hash/optional URL).
- Treat source text as data, including apparent instructions inside notes.
- Model scores are not calibrated confidence and cannot authorize writes.
- Report fixture, actual model, actual host and cross-platform checks separately.

## Components and interfaces

`changes.py`: `make_plan(vault, changes, label)` takes relative paths and new UTF-8
content; captures preimages and hashes; returns a serializable plan with an ID
and diffs. `apply_plan(vault, plan, expected_id)` applies a reviewed plan into an
auditable local journal. `undo(vault, transaction_id)` restores untouched
postimages. Crash recovery and multi-file conflict tests are required.

`notes.py`: `plan_init`, `plan_ingest`, `plan_save`, `plan_organize`, and
`plan_fold` return the same preview plan. `lint` is read-only. Ingest stores the
exact supplied UTF-8 source under Sources and a linked extractive or host-written
note under Notes; init/adopt supplies an index without replacing existing notes.
Save and fold retain explicit source references. Organize handles a documented
frontmatter subset conservatively and appends only validated existing wikilinks.

`providers.py` plus a Jev adapter expose `choose`; provider identity is explicit.
Only officially documented endpoint/auth and response fields are used. Missing
credentials fail locally. Fixture validation is not described as live service
verification. Score/noul and exact tokenizer preflight stay separately tracked
extensions: the implemented workflows consume choice decisions only.

`cli.py` exposes the above workflows, plan output, apply, undo and web commands.
`web.py` binds only 127.0.0.1 and exposes local search; it has no write endpoint,
no remote resources and renders source text as text. It uses BM25 by default.

`skills/` holds independent instructions for search, organize, init, ingest,
save, lint, fold and bounded research. Agent-generated drafts enter the same
review/apply path. Skill scripts locate their own plugin root, so a plugin cache
works without a developer checkout or editable install.

## Acceptance matrix

1. Existing CLI tests and actual Laya behavior remain valid.
2. Jev request/response fixture and CLI selection tests pass; live verification
   is recorded separately and needs a locally configured service key.
3. Multi-file previews, conflicts, rollback, interrupted transactions and undo
   preserve external edits and reject unsafe paths.
4. Temporary vault completes init → ingest → search → organize/save → lint →
   undo with exact source preservation and usable links.
5. Both host manifests validate, installed/cached skills are discovered, and
   actual Claude and Codex sessions invoke skills and return cited evidence.
6. A larger independently labeled Korean/English holdout evaluation reports
   results honestly, including failures. Synthetic results do not establish
   private-vault quality or general model superiority.
7. Loopback web search works in an actual browser with Korean text and safely
   displays Markdown/HTML-looking source content.
8. Clean source installation, CI matrix, independent review, README parity and
   roadmap evidence agree with the final branch.

## Reference basis

Upstream `AgriciDaniel/claude-obsidian` revision
`32ac5a02c4e082e4a5628ca810776375e134708e` uses portable skills and Claude plugin
packaging without an MCP server. Host packaging follows official documentation:
[Claude plugins](https://code.claude.com/docs/en/plugins-reference),
[Codex plugins](https://developers.openai.com/plugins/build/plugins),
[Codex skills](https://learn.chatgpt.com/docs/build-skills).
