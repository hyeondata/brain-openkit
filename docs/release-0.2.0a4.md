# Release verification: 0.2.0a4

English | [한국어](release-0.2.0a4.ko.md)

This document records the archive contract and verified working-source checks.
See the [GitHub prerelease](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a4)
and its [verification report](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/verification-report.json)
for final packaged-artifact checks, CI results and the exact tested revisions.

## What changes

`0.2.0a4` adds opt-in local Markdown conversation archives for supported
Claude Code and Codex CLI callbacks. Archiving is off by default. Enabling it
for a selected vault authorizes the recorder to maintain its session notes
under `Inbox/Conversations/`; it does not authorize editing other notes.
Existing selected-knowledge workflows retain their preview/apply behavior.

The recorder makes no model or network calls. It keeps visible user/assistant
text and, when explicitly enabled, inline tool output. It excludes internal
reasoning, injected context, tool-call arguments and binary attachments. It
does not create an AI summary. The host's ordinary model usage and original
conversation-log storage continue independently.

The default archive budget is 100 MiB, with a 2 MiB limit per session note.
A reached limit, edited archive or incompatible history preserves existing
content and reports the reason. Atomic replacement can temporarily require
up to another 2 MiB. Retention defaults to zero and automatic pruning is off;
only explicitly authorized pruning may remove old, unchanged managed notes.
The budget does not control or delete Claude/Codex's own logs.

Use the [conversation archive guide](conversation-archive.md) for configuration,
limits, pause/resume behavior and host setup. The [agent integration guide](agent-integration.md)
distinguishes the eight reviewed skills from the optional archive hooks.

## Verification status

| Evidence category | Current status and scope |
| --- | --- |
| Core and CLI fixtures | The working-source suite ran 247 tests in each of Python `3.11.13` and `3.13.1`: 243 passed, with four platform-specific skips and no failures. |
| Claude Code callback | Actual native capture was exercised in Claude Code `2.1.220` with the source plugin: OFF created no vault files; ON saved two messages; resuming the same session preserved four messages, including repeated text, in the same archive. Replaying the final snapshot returned unchanged. `Stop` and `SessionEnd` events were observed; the result stream directly reported Stop execution. |
| Codex CLI callback | Actual native capture was exercised in CLI `0.149.0` with plugin `0.2.0a4`: OFF created no vault files; ON saved two messages; resuming the same session produced four messages in the same archive; replaying the Stop snapshot returned unchanged. This is a working-source check, not final packaged-artifact verification. |
| Codex Desktop | Automatic archive behavior has not been verified. |
| Release packaging | The release verification report records wheel/source builds, archive contents, relocated hooks and integrity checks for the packaged revision. |
| Cross-platform CI | Consult the release verification report for results on the final release commit. CLI test coverage does not establish native host-hook coverage. |

Native event detection, plugin discovery, transcript parsing, actual automatic
capture and packaged-release execution are separate evidence. A successful
manual transcript import does not establish that a host invoked the hook.
Both CLI exercises used synthetic input and verified the captured messages
against the actual input and replies, including preservation of the earlier
message prefix. Each exercise requested three ordinary host-model replies;
the recorder itself makes no model or network calls.

The native exercises used working-source plugins. After the final transcript
reader and callback-timeout adjustments, existing synthetic payloads were
replayed locally; those checks did not generate new host replies. The report
distinguishes native execution from final-adapter replay, including the final
three-second SessionEnd timeout.

The release verification report identifies tested host versions, callback and
runner origin, explicit vault selection, archive content and source hashes.
Lifecycle checks also cover disabling without deleting existing files, blocked
or delayed capture without blocking the host, and retention preserving edited
and unmanaged files. Final counts and exceptions belong to the tested revision
rather than an earlier build.

## Distribution and historical evidence

The wheel installs the Python CLI, including manual archive commands.
Host callbacks require the complete source distribution or tagged checkout,
with `hooks/`, `scripts/`, `src/`, `skills/` and the host manifests kept together.
PyPI and public plugin-directory publication are outside this release scope.
Verify downloaded assets against the release's `SHA256SUMS`.

The [0.2.0a3 release report](release-0.2.0a3.md), its dated
[Claude follow-up](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a3/claude-host-verification-2026-10-05.json),
and the [native Obsidian app checks](obsidian-app-verification-2026-10-05.md)
remain historical evidence for their own scope. They do not establish archive
behavior in `0.2.0a4`. Earlier Laya/Kev/Jev evidence is also unchanged; the
archive does not call those providers.

## Limits

Only synthetic, disposable conversations and vaults are suitable for public
verification artifacts. Raw host logs, credentials, account identifiers and
personal paths must not be included. Published examples and hashes can show
that the tested archive operation preserved content; they do not establish
research factual accuracy, model quality parity, cost savings or reliability
at production scale.

The first archive version does not copy binary attachments or read external
tool-output sidecars. Transcript compaction or changed host formats can block
updates to preserve earlier content. A session at its per-note limit needs a
new host session; it is not silently truncated or split. Consult the release
verification report for tested platforms and remaining host-specific limitations.
