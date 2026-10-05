# Brain OpenKit v0.2.0a3 release

English | [한국어](release-0.2.0a3.ko.md)

This alpha release distributes the CLI and the complete Claude Code/Codex plugin
source through [GitHub Releases](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a3).
Python 3.11 or newer is required. PyPI and public plugin-directory publication
are not part of this release.

## Download and install

Download the following files from the release page into one directory:

- `brain_openkit-0.2.0a3-py3-none-any.whl`: CLI installation.
- `brain_openkit-0.2.0a3.tar.gz`: complete source, eight skills, host manifests,
  bundled runner, examples and documentation.
- `release-verification.json`: source, artifact, test and host execution evidence.
- `SHA256SUMS`: checksums of the release assets.

Check the files before installation. On macOS:

```bash
shasum -a 256 -c SHA256SUMS
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ./brain_openkit-0.2.0a3-py3-none-any.whl
brain-openkit --version
```

Linux can use `sha256sum -c SHA256SUMS`. On Windows, use
`Get-FileHash -Algorithm SHA256` to compare the downloaded files with
`SHA256SUMS`, and `.venv\Scripts\Activate.ps1` to activate the environment.

For host plugins, extract the source archive, keep its whole tree together, and
follow the [Claude Code/Codex guide](agent-integration.md). A wheel installation
does not register a host plugin. Store the product outside your Obsidian vault.
A tagged checkout is an alternative:

```bash
git clone --branch v0.2.0a3 --depth 1 https://github.com/hyeondata/brain-openkit.git
```

## What this version provides

Local BM25 search returns note paths, line numbers and exact source excerpts.
Eight host skills support initialization, search, capture, saving, organization,
lint, extractive folding and cited research. Writes use a preview plan, explicit
plan ID and transaction journal; undo verifies the expected contents.
Classification defaults to Kev, whose bundled launcher selects pinned Hugging
Face Kev 0.8B weights. Laya and TypeSafe Jev remain selectable providers. Search
and evaluation default to BM25 without a model service.

See the [local-model guide](local-models.md) for the separate model environments.
Hosted Claude/Codex sessions still require their own authentication and model
access. Running a local decision model does not make those sessions offline.

## Verification and limits

Release packaging and host execution are checked separately from the historical
model and native-app runs. The release's `release-verification.json` asset records
the exact source commit, artifact checksums, installation checks and host results.
It is the reference for checks performed on the distributed artifacts.

Existing evidence includes [Kev 0.8B](kev-08-verification-2026-10-05.md),
[Laya and Kev 0.5B](model-verification-2026-10-05.md), and
[native Obsidian app verification](obsidian-app-verification-2026-10-05.md).
The native app run checked Korean/English rendering, search, properties, links,
backlinks, graph updates and exact file restoration after fold undo.

These are bounded functional checks on synthetic vaults, not a production-scale
quality or cost comparison. Model tag errors remain documented; no quality parity
with Claude/Codex is claimed. Live TypeSafe Jev inference is unverified. The CLI
and host skills do not install a native Obsidian plugin UI. Plans and transaction
journals contain note contents and should remain private with the vault.
