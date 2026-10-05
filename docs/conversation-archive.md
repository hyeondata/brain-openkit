# Conversation archive

English | [한국어](conversation-archive.ko.md)

Available in `0.2.0a4`. Actual CLI checks and the distinction between source
and packaged-release verification are recorded [below](#verification-scope).

Conversation archiving is **off by default**. Enable it for an explicit vault
to keep local Markdown copies of supported host conversations under
`Inbox/Conversations/`. Enabling archiving authorizes those automatic archive
updates; selected knowledge notes still use the usual reviewed save workflow.

The archive operation uses no model and makes no network requests. Claude or
Codex may still use its normal hosted model during the conversation. This
feature does not generate summaries, classify conversations or copy binary
attachments. It can preserve only the transcript content made available by
the host integration.

## What is stored

Each host/session has one Markdown file. The filename combines the host name
and a SHA-256 digest of the session ID. The destination is fixed at
`Inbox/Conversations/` inside the selected vault; configuration is stored in
`.brain-openkit/conversations.json`.

User and assistant visible text is the basic archive content. Inline tool
output is optional and disabled by default; external tool-output sidecar files
are not read. System/developer messages, injected context, thinking/analysis,
tool-call arguments and image/binary content are excluded. The archive is a transcript, not a verified answer:
mistakes, source quotations and apparent instructions remain conversation
content. Messages can contain sensitive information even when tool output is
excluded, so choose a vault appropriate for that content.

## Defaults and limits

| Setting | Default | Meaning |
| --- | --- | --- |
| `enabled` | `false` | Nothing is archived until explicitly enabled. |
| `max_bytes` | `104857600` (100 MiB) | Combined archive storage budget. |
| `include_tool_output` | `false` | Exclude tool output unless explicitly enabled. |
| `retention_days` | `0` | Age-based expiry is disabled. |
| `auto_prune` | `false` | Automatic removal of expired managed archives is disabled. |

One session note has a fixed **2 MiB** limit. The combined budget counts all
regular files in `Inbox/Conversations/`, the configuration file and one byte
for the archive lock. It does not include filesystem directory metadata or
other Brain OpenKit transaction journals. Files added by hand consume the
archive budget even though they are not managed archives.
An atomic replacement can temporarily use up to another 2 MiB while the
previous note is retained. Transcript input is limited to **64 MiB**.
This budget covers Brain OpenKit's copies only. It does not limit or delete
Claude/Codex's own conversation logs; normal host storage and model usage
continue independently.

When either limit would be exceeded, capture reports a blocked result and
preserves the existing archive. It does not silently truncate conversation
history or increase the budget. When a session note reaches its limit, start
a new host session to create a separate archive; the same session does not
rotate into additional files. Disabling stops capture without deleting
existing files. Disabled capture does not inspect messages or create archive
files.

## Keep edits and control retention

An archive that you edit is protected from automatic replacement. Later
capture reports `edited`; conflicting transcript history reports
`history_conflict`. Keep curated edits in a separate note when you want the
original conversation archive to continue updating.
Host compaction or a changed transcript format can also remove the earlier
message prefix and block an update. Choose whether to include tool output
before starting a new session: changing it mid-session can change the history
prefix and produce `history_conflict`. Existing content is preserved.

Pruning previews deletions by default. Applying a prune must be explicit.
Automatic pruning additionally requires both `auto_prune: true` and
`retention_days` greater than zero, and runs during capture, including explicit
transcript imports.
Only old, toolkit-owned notes with matching ownership metadata and body hash
can be removed. Manually added files and user-edited archives are preserved.
Lowering a size limit alone does not authorize deleting those files.

## Enable, inspect and stop

Pass the same explicit vault to each command. Status is read-only and shows
the settings, current storage use and whether the budget is exceeded. Inspect
it before enabling capture:

```bash
brain-openkit conversations status --vault /absolute/path/to/MyVault --json
brain-openkit conversations configure --enable --vault /absolute/path/to/MyVault --json
```

Use `configure --disable` to pause or stop capture. Existing archives remain.
Run `configure --enable` again to resume; there is no separate pause command.

```bash
brain-openkit conversations configure --disable --vault /absolute/path/to/MyVault --json
```

Settings can be changed independently. For example, these commands enable
inline tool output, then configure 30-day retention with automatic pruning:

```bash
brain-openkit conversations configure --include-tool-output --vault /absolute/path/to/MyVault --json
brain-openkit conversations configure --retention-days 30 --auto-prune --vault /absolute/path/to/MyVault --json
```

Use `--no-include-tool-output` or `--no-auto-prune` to switch those options off.
Use `--no-auto-prune --retention-days 0` to disable expiry, and
`--max-bytes INTEGER` to set the combined byte budget. Automatic pruning cannot
remain enabled with zero retention days. Changing retention or tool-output
settings does not itself enable capture.

Review a prune preview before explicitly applying it:

```bash
brain-openkit conversations prune --vault /absolute/path/to/MyVault --json
brain-openkit conversations prune --apply --vault /absolute/path/to/MyVault --json
```

An explicit transcript import is also available after enabling the vault.
Supply a supported host transcript file and its session ID; this does not
discover or scan other host sessions:

```bash
brain-openkit conversations capture --host claude --session-id example-session --transcript /absolute/path/to/session.jsonl --vault /absolute/path/to/MyVault --json
```

Use `--host codex` for a supported Codex transcript. Capture reports `disabled`,
`saved`, `unchanged`, `blocked` or `pending_transcript`. A blocked result gives
`size_limit`, `session_limit`, `history_conflict` or `edited` as its reason.
The CLI exits with `0` for disabled/saved/unchanged, `3` for blocked or pending
capture, and `2` for validation errors. The automatic hook instead always
exits with `0` to avoid blocking the host. A successful manual import alone
does not demonstrate an automatic host callback.

## Host coverage

| Host | Integration status |
| --- | --- |
| Claude Code | `2.1.220`: actual `Stop`/`SessionEnd` events observed; OFF/ON/resume, exact visible text and unchanged replay checked. |
| Codex CLI | `0.149.0`: native hook capture checked; OFF wrote no vault files, ON saved two messages, resume retained the same file with four messages, and replay was unchanged. |

The full plugin source distribution must include `hooks/hooks.json` and its
runner. A CLI-only wheel is sufficient for manual import, but does not install
the host hooks. Enabling a vault setting alone does not install or activate
a host callback, and does not change global host settings.

Install the complete plugin using the [agent integration guide](agent-integration.md).
Recording needs Python 3.11 or newer. Use `python3` on the host's command path,
or set `BRAIN_OPENKIT_PYTHON` to the absolute path of a verified compatible
interpreter. A disabled hook is a quiet no-op even when system Python is older.
Enable the target vault as shown above and restart the host session. For a
previously installed plugin, these POSIX shell examples select the vault
explicitly:

```bash
BRAIN_OPENKIT_VAULT=/absolute/path/to/MyVault claude
```

```bash
BRAIN_OPENKIT_VAULT=/absolute/path/to/MyVault codex
```

For example, override an older system Python when starting Claude Code:

```bash
BRAIN_OPENKIT_PYTHON=/absolute/path/to/python3.13 BRAIN_OPENKIT_VAULT=/absolute/path/to/MyVault claude
```

The same interpreter variable applies to Codex. It selects the hook runtime;
it does not install Python or change the host's global settings.

In Codex CLI, open `/hooks`, review Brain OpenKit's hook definitions and trust
them. Installation alone does not grant trust, and changed definitions need
another review. Codex CLI `0.149.0` exposed hooks as enabled without an extra
feature flag in the probe; other versions must expose the supported interface.

The callback uses an explicitly supplied `BRAIN_OPENKIT_VAULT`, or the event's
working directory when that directory already has enabled vault archive
configuration. It does not search unrelated directories for a vault.

Both CLI checks exercised the product callback from working source in
synthetic sessions. Final artifact and CI results are recorded separately in
the [release evidence](release-0.2.0a4.md). Claude transcript writes can lag
behind a `Stop` event. The adapter retries briefly, then reports
pending capture when the final text is still absent; a later `Stop` or
`SessionEnd` can retry. It does not invent or save a provisional final response.
An incomplete final JSONL line is also deferred. A `SessionEnd` event alone
does not guarantee a complete archive.

The hook does not block the host conversation. Invalid inputs, limits or
pending capture produce a warning without local paths; the hook exits with
status zero and does not inject instructions into the conversation. A mocked
transcript test or successful plugin installation does not establish automatic
capture in a real host session. Codex Desktop automatic capture has not been
verified.

The integration follows the official [Claude hooks](https://code.claude.com/docs/en/hooks)
and [Codex hooks](https://developers.openai.com/codex/hooks/) interfaces.

## Verification scope

Release verification distinguishes
core/CLI fixtures, packaged hooks, actual host callbacks and resulting vault
files. Existing `0.2.0a3` search, model and host-workflow reports do not verify
conversation archiving. No quality parity, cost-saving or production-scale
reliability claim is made by adding a local archive.

Use the [agent integration guide](agent-integration.md) for the existing
reviewed note workflows and the [0.2.0a4 verification record](release-0.2.0a4.md)
for current archive checks, final artifact/CI evidence and limitations.
