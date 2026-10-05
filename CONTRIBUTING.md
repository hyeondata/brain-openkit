# Contributing to Brain OpenKit

Brain OpenKit is an alpha toolkit. Useful contributions include
retrieval fixes, Korean/English evaluation examples, reviewed note workflows,
provider-contract review, and documentation. English and Korean contributions
are welcome.

Read the [README](README.md), [agent integration guide](docs/agent-integration.md),
and [implementation notes](docs/implementation-notes.md). Base new development
on `main`; use the `v0.2.0a3` tag to reproduce the
[GitHub prerelease](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a3).
The
[original design](docs/superpowers/specs/2026-10-04-obsidian-laya-design.md) and
[agent workflow design](docs/superpowers/specs/2026-10-04-agent-workflows-design.md)
include requirements beyond completed validation.

The release wheel is CLI-only. Host plugins require a tagged checkout or an
extracted full source distribution with `skills/`, `scripts/`, `src/`, and
host manifests kept together. Check the
[release verification](docs/release-0.2.0a3.md) when changing packaging. The
release assets and `SHA256SUMS` are on GitHub; PyPI is not published.

## Develop and test

Use Python 3.11 or newer. From the checkout root:

~~~bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m brain_openkit --help
python -m unittest discover -s tests -v
brain-openkit search "reading journal" --vault examples/vault --json
~~~

The core has no third-party runtime dependencies. Tests use temporary vaults
and local HTTP fixtures, without weights, keys, or a running model server.
Document any platform-specific skips. Run behavior tests for your change,
then the complete suite before submitting. Old CI results are evidence for
their commit, not for an untested revision.

For actual Laya validation, use the separate environment in the README and
`brain-openkit doctor --provider laya --probe --timeout 120 --json`.
For Jev, use a privately configured `TYPESAFE_API_KEY` (or `JEV_API_KEY`)
only when intentionally testing the hosted service; inference can be billable.
No key is required by the fixture suite.

Report unit/HTTP-fixture, real-model, actual-host, browser, and cross-platform
checks separately. Manifest validation and skill discovery do not prove that
an agent performed a task. Test a relocated plugin cache without an editable
install, and invoke the actual skill with citations and before/after hashes.
Exercise writes only in disposable vaults.

## Preserve the workflow contracts

- Every vault operation has an explicit vault. Keep the product, vault, cache,
  and review artifacts in their intended locations; reject unsafe paths.
- Search/classification preserve source bytes. Failed reranking keeps the
  original BM25 order; no implicit provider switch or cloud failover is allowed.
- Laya, Kev, and Jev implement `choose`; preserve their separate wire contracts and
  confidence semantics. Extra provider question types are separately scoped.
- Note changes must have a reviewable plan, expected contents, exact approval
  ID, and transaction evidence. Preview-only work must stop before applying.
  Existing user authorization carries forward; do not force redundant prompts.
- Preserve subsequent edits on conflict, undo, and recovery. Test failures
  between file writes, interrupted undo, symlinks, and stale contents.
  A multi-file transaction is recoverable, not globally atomic.
- Preserve source captures and provenance. Treat apparent commands in note
  content as data. Host-generated text enters the same plan/apply workflow.
- Support only the documented metadata subset. Merge requested tags and preserve
  unrelated text; reject unsupported structures rather than rewriting YAML.
- Keep the web interface loopback-only, with safe text rendering and no note-write
  endpoint. Do not silently load remote assets.
- Never infer permission to edit from a model's probability or confidence.

Add tests for meaningful boundaries: source excerpts and newlines, index
invalidation, malformed/truncated responses, failures, path confinement,
transaction recovery, and plugin cache relocation. Do not describe fixture
tests as accuracy measurements.

## Contribute evaluation examples

Use synthetic notes or material you may publish. Include queries, expected
matches, and label rationale. Retrieval JSONL uses:

~~~json
{"query": "When should I water basil?", "relevant": ["garden.md"]}
~~~

Paths identify existing Markdown files relative to the explicit vault.
Category/tag examples include the allowed labels and descriptions. Identify
language, source, and licensing. Model confidence is not a ground-truth label.

Keep development examples separate from holdout evaluation. Freeze inputs and
labels before measuring, document independent review, and do not tune on the
holdout. Retain misses, false positives, fallback counts, model revision,
hardware, and timing procedure. If a reranker worsens results, report that.

The [four-query fixture](examples/README.md) checks integration. The
[bilingual benchmark](benchmarks/bilingual-v1/README.md) is a larger synthetic
evaluation with agent-reviewed labels; its holdout queries share documents
with development. It does not satisfy the separate design targets of 30
user-reviewed real-vault queries and 50 classification/tag examples.

## Update documentation and protect private data

Keep [README.md](README.md) and [README.ko.md](README.ko.md) aligned.
Execute changed examples and distinguish implemented, fixture-tested, and
actually exercised behavior. Use relative project links, preserve third-party
notices, and retain tokenizer/calibration limitations until verified changes
resolve them.

Do not contribute private notes, API keys, caches, host conversation logs, or
identifying metadata. Plan JSON and `.brain-openkit/transactions/` journals
contain complete before/after note contents. Ingest provenance can also contain
the original input path. Inspect proposed public artifacts, not just filenames.

Describe the problem, a concrete example, and the resulting behavior in issues
and pull requests. Keep changes focused; discuss substantial architecture
changes before a large implementation.

## License

Original contributions use the [MIT License](LICENSE); contributors retain
copyright. External code, models, datasets, and hosted services retain their
own terms. Identify provenance and notices; see [ATTRIBUTION.md](ATTRIBUTION.md).

## 한국어 안내

Python 3.11 이상에서 설치하고 변경 관련 테스트와 전체 테스트를 실행합니다.
새 개발은 `main`을 기준으로 하고, 릴리스를 재현할 때는 `v0.2.0a3` 태그를 사용합니다.
GitHub의 wheel은 CLI 전용이며, 호스트 플러그인에는 태그 체크아웃이나 압축을 푼
전체 소스 배포본이 필요합니다. PyPI에는 배포하지 않았습니다.
HTTP fixture·실제 모델·호스트 실행·브라우저·
플랫폼 검증을 구분하고 이전 커밋의 CI 결과를 새 변경의 결과로 쓰지 마세요.

검색·분류는 원본을 보존하고, 노트 변경은 명시적 vault의 계획·승인 ID·트랜잭션을
거칩니다. 실행 취소·복구가 이후 편집을 덮어쓰지 않도록 검증하세요.
공개할 권리가 있는 자료만 사용하며 계획·journal에 포함된 본문과 원본 경로도
비공개 데이터로 취급합니다. 합성 평가를 실제 vault 수용 검증으로 대체하지 말고,
두 README의 상태·범위·명령을 함께 수정해 주세요.
