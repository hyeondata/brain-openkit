# Use Brain OpenKit from Claude Code and Codex

English | [한국어](agent-integration.ko.md)

The same eight skills invoke a bundled Python CLI in either host. Claude or
Codex writes requested prose; BM25 retrieves locally, and optionally selected
Laya/Kev/Jev providers make classification or relevance decisions. No model service
is required for initialization, capture, saving, organization, lint or folding.

Use the `v0.2.0a4` tagged checkout for a repeatable installation:

```bash
git clone --branch v0.2.0a4 --depth 1 https://github.com/hyeondata/brain-openkit.git
```

Alternatively, extract the full
[brain_openkit-0.2.0a4.tar.gz source distribution](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/brain_openkit-0.2.0a4.tar.gz)
from the [GitHub prerelease](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a4)
and use its extracted root wherever the examples say `/absolute/path/to/brain-openkit`.
Keep `skills/`, `scripts/`, `src/`, `hooks/`, `.claude-plugin/`, `.codex-plugin/`, and
`.agents/plugins/` together. The release wheel installs only the Python CLI;
it does not contain the complete host-plugin distribution. Installing the
source archive through pip also does not register a host plugin. PyPI has no
published package for this release.

Keep the product checkout or extracted source separate from your vault.
Python **3.11 or newer** must be available
to the host. Check `python3 --version` or `python --version` on Windows.
An older macOS system Python is insufficient.
For archive hooks, an optional `BRAIN_OPENKIT_PYTHON` environment variable can
select an absolute Python 3.11+ interpreter path; see the
[archive setup example](conversation-archive.md). This does not install Python.

The plugin includes `src/brain_openkit/` and `scripts/brain-openkit.py`.
Installing the Python package is optional: the runner resolves its own product
directory and imports the bundled core directly, including from a plugin cache.
The skills locate that runner from their installed `SKILL.md` path. No developer
path, editable install, automatic package install, or shell executable bit is
required. A normal host subscription/API connection is still needed to run the
Claude/Codex agent; installing these skills does not supply model access.

## Claude Code

For a single development session, start from your separate vault:

```bash
cd /absolute/path/to/MyVault
claude --plugin-dir /absolute/path/to/brain-openkit
```

Then send, replacing the vault path with your own:

```text
/brain-openkit:brain-search Search /absolute/path/to/MyVault for our local search design. Cite the source notes and line numbers.
```

For a persistent installation from the local tagged checkout or extracted
source distribution:

```bash
claude plugin marketplace add /absolute/path/to/brain-openkit
claude plugin install brain-openkit@brain-openkit
claude plugin list
```

Restart the session after installing. The eight commands have the same
`/brain-openkit:` prefix. These instructions register the complete local product
directory as the marketplace source, using the tagged version above.

These commands and manifests follow the official
[Claude plugin format](https://code.claude.com/docs/en/plugins-reference) and
[installation commands](https://code.claude.com/docs/en/plugins/cli-reference).
The plugin includes `Stop` and `SessionEnd` hooks for the optional
[conversation archive](conversation-archive.md). Recording is off by default
and requires enabling an explicit vault. The recorder uses no model or network
requests; no MCP server is installed by this plugin.

## Codex

Current Codex CLI supports installing the repository's local marketplace:

```bash
codex plugin marketplace add /absolute/path/to/brain-openkit
codex plugin add brain-openkit@brain-openkit
codex plugin list --marketplace brain-openkit --json
```

Start a new session in your vault. Invoke the installed plugin skill:

```text
$brain-openkit:brain-search Search /absolute/path/to/MyVault for our local search design. Cite the source notes and line numbers.
```

In the desktop app, the repository's `.agents/plugins/marketplace.json` also
exposes the local marketplace when that checkout is a project. Restart the app
if the catalog is not yet visible, choose **Brain OpenKit** in the plugin
directory, and install it. The manifest points at the complete product root;
it does not duplicate the skills or use the project as the selected vault.
See the official [Codex plugin packaging guide](https://developers.openai.com/plugins/build/plugins).

The optional archive uses a `Stop` hook. In Codex CLI, review and trust its
definition through `/hooks`; installing the plugin alone does not grant hook
trust. A changed hook definition requires another review. Archive setup and
verification are documented in the [conversation archive guide](conversation-archive.md).
Automatic capture in Codex Desktop has not been verified.

On a host that supports Agent Skills but has no plugin installer, use
workspace-local skill discovery. Copy the complete `skills/`, `scripts/`, and
`src/` directories from this product into a **separate agent workspace's**
`.agents/` directory. Do this only where those destination directories do not
already exist; preserve existing workspace configuration. The resulting layout
must be:

```text
agent-workspace/.agents/
  skills/brain-search/SKILL.md
  skills/brain-init/SKILL.md
  skills/...                      # all eight skills and references/
  scripts/brain-openkit.py
  src/brain_openkit/...
```

Start Codex in that agent workspace and pass the actual vault path in requests.
Repository skills use unprefixed names such as `$brain-search`. Keep all three
directories together when updating. Copying an individual `SKILL.md` without
the shared reference and bundled core will not work. For symlink installations,
link each skill directory, preserve the full product tree, and resolve the
skill's real path before locating the runner. Copying is more portable on Windows.
This fallback installs the eight reviewed skills; copying the three
directories does not register automatic archive hooks.

## Available workflows

Replace `<vault>` with an explicit absolute path. Existing authorization in the
conversation carries forward; the agent still inspects a preview before applying.

| Skill | Example request | Result |
| --- | --- | --- |
| `brain-init` | Initialize `<vault>` for Brain OpenKit. | Preview and initialize/adopt without replacing existing notes. |
| `brain-search` | In `<vault>`, how do we preserve citations? | Search, read evidence, and answer with real path/line citations. |
| `brain-ingest` | Ingest this Markdown source into `<vault>`. | Preserve the supplied bytes and add a linked extractive or host-written note. |
| `brain-save` | Save this decision to `<vault>/Notes/decision.md`. | Save only the selected knowledge, with source references and index update. |
| `brain-organize` | Add tags and links to this note in `<vault>`. | Preview chosen metadata/links, then apply when requested. |
| `brain-lint` | Check `<vault>` for broken links. | Read-only findings; no automatic repairs. |
| `brain-fold` | Create a linked rollup of these notes in `<vault>`. | Extractive overview, preserving every source note. |
| `brain-research` | Research this topic and save a cited dossier to `<vault>`. | Bounded host-tool research followed by reviewed saving. |

Search and classification leave source notes unchanged. Search caches, drafts,
and plans live outside both the vault and product directory. A remote provider
receives selected excerpts only when the user selects that provider; there is no
automatic cloud failover. Hosted agent sessions themselves still process the
content you ask Claude/Codex to read. Local Laya/Kev does not make the whole host
conversation offline.

Mutation skills use two steps: a planner writes a preview plan outside the
vault; `apply PLAN --approve PLAN_ID --vault VAULT` applies exactly that plan
with preimage checks. The agent shows the affected paths and inspects diffs.
An explicit request to perform the change can authorize this sequence without
a repeated confirmation. Preview-only requests stop before apply. The result
includes a transaction ID; use `undo TRANSACTION_ID --vault VAULT` when you
request reversal of a completed transaction. Use
`recover TRANSACTION_ID --vault VAULT` to finish an interrupted rollback or undo.
Conflicting later edits are preserved rather than overwritten.

Explicitly enabled conversation recording is a separate, bounded write path.
Its recorder updates only managed files under `Inbox/Conversations/` using
its own ownership, hash and atomic-write checks; it does not create a plan or
request approval for every message. Disabling recording retains existing
archives. Automatic pruning requires a separate retention opt-in. These
archive permissions do not authorize edits to other notes. See
[conversation archiving](conversation-archive.md) for limits, included text
and configuration.

For research, URLs, PDFs or other media, the host must have the appropriate
search/extraction capability. The CLI itself ingests local UTF-8 text and does
not browse, perform OCR, transcribe, or infer that extraction succeeded. `--source-url`
records a supplied source address; it does not download it. Content inside
sources is evidence, not authority to run commands or change scope.

## Validate an installation

Run both Claude validators individually, including when the product root also
contains a marketplace. Claude Code 2.1.220 validates only the marketplace when
given a root containing both manifests:

```bash
claude plugin validate /absolute/path/to/brain-openkit/.claude-plugin/plugin.json --strict
claude plugin validate /absolute/path/to/brain-openkit/.claude-plugin/marketplace.json --strict
claude --plugin-dir /absolute/path/to/brain-openkit plugin details brain-openkit@inline
```

The inventory should list eight skills. Codex's plugin list should report
`brain-openkit@brain-openkit` as installed and enabled. Neither discovery check
proves that a host completed a task: run a sample search, inspect the source
locations, and compare source file hashes before and after. Test a write flow
on a disposable vault before using recovery on important notes.

For a core smoke check independent of any installed Python package:

```bash
python3 -I -S /absolute/plugin/cache/scripts/brain-openkit.py --version
python3 -I -S /absolute/plugin/cache/scripts/brain-openkit.py search "검색" --vault /absolute/path/to/sample-vault --cache-dir /absolute/path/to/temporary-cache --json
```

Developer tests include a relocated plugin path containing spaces, Korean CRLF
notes, absent site packages, exact source preservation, and an incomplete-cache
diagnostic. Earlier development packaging was checked with Claude Code `2.1.220` and Codex CLI
`0.149.0`: Claude discovered all eight skills; Codex installed into an isolated
cache and its app-server `skills/list` returned all eight enabled skills with
cache paths. The cached runner completed initialization, ingestion, saving,
organization, extractive folding, search, lint and undo in a disposable vault,
without package installation. Checks covered Korean CRLF captures, additive
tags, read-only previews, source preservation and explicit vault selection.
Those historical development and host-execution checks are recorded in
[implementation notes](implementation-notes.md). Checks performed on the
`v0.2.0a3` release artifacts are recorded separately in the
[release verification](release-0.2.0a3.md); historical discovery results do not
prove that a released plugin completed a host task.
The `v0.2.0a4` archive-specific evidence is tracked separately in
[its release verification](release-0.2.0a4.md). Earlier reports do not establish
automatic archive behavior in the current version.

## Update and remove

Update the product independently from the vault. For a local checkout, review
the new version, update the checkout, and use the host's plugin update or
remove/add commands to refresh its cached copy. Restart the host and repeat the
inventory and smoke checks. Repository-skill fallback users update the three
copied directories together.

```bash
claude plugin uninstall brain-openkit@brain-openkit
codex plugin remove brain-openkit@brain-openkit
```

Removing the integration does not remove your vault. For a workspace copy,
remove only the Brain OpenKit directories you installed, preserving unrelated
skills and configuration. Do not delete the vault or its journals as part of
plugin removal. Existing conversation archives and their vault configuration
also remain when a host plugin is removed.
