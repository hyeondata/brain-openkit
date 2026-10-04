# Contributing to Brain OpenKit

Brain OpenKit is a source-installable alpha. Useful contributions include
retrieval fixes, Korean/English evaluation examples, provider-contract review,
and documentation. English and Korean contributions are welcome.

Read the [README](README.md) for implemented behavior and
[implementation notes](docs/implementation-notes.md) for validation evidence.
The [original design](docs/superpowers/specs/2026-10-04-obsidian-laya-design.md)
also includes future features.

## Develop and test

Use Python 3.11 or newer. From the checkout root:

~~~bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
brain-openkit search "reading journal" --vault examples/vault --json
~~~

The CLI has no third-party runtime dependencies. Tests use temporary vaults
and local HTTP fixtures, without weights, keys, or a running model server.
For actual model validation, follow the separate Laya setup in the README,
run `brain-openkit doctor --probe --timeout 120 --json`, and exercise search/classification.
Report model tests separately from fixture-based tests.

## Propose a change

Describe the task, an example, and expected behavior. Discuss substantial
architectural changes in an issue before a large pull request. Keep changes
focused.

Preserve read-only source access and provider-independent retrieval. Failed
reranking keeps a coherent BM25 order. The current protocol exposes
`choose`; Jev and additional question types remain future work.

Add behavior tests for fixes and boundaries, especially source excerpts,
index invalidation, malformed responses, truncation, and server failures.
Run the whole suite before submitting. Fixture tests do not prove accuracy.

## Contribute evaluation examples

Use synthetic notes or material you may publish. Include query, notes,
expected matches, and label rationale. Retrieval JSONL uses:

~~~json
{"query": "When should I water basil?", "relevant": ["garden.md"]}
~~~

Paths identify existing Markdown files relative to the vault. Category/tag
examples include allowed labels and descriptions. Identify language and
source; exclude private notes, credentials, private paths, and identifying
metadata. Model confidence alone is not a ground-truth label.

Keep prompt-tuning examples separate from held-out evaluation data. Include
dataset, model revision, hardware, and procedure with quality/latency claims.
The [four-query fixture](examples/README.md) only checks the workflow.

## Update documentation

- Keep [README.md](README.md) and [README.ko.md](README.ko.md) aligned.
- Execute changed command examples and distinguish measurements from plans.
- Use relative project links and preserve required third-party notices.
- Keep tokenizer preflight and calibration limitations visible until verified
  changes resolve them.

## License

Original contributions use the [MIT License](LICENSE); contributors retain
copyright. External code, models, and datasets retain their own licenses.
Identify provenance and terms; see [ATTRIBUTION.md](ATTRIBUTION.md).

## 한국어 안내

현재는 소스 설치 알파 버전입니다. Python 3.11 이상에서 설치하고 전체 테스트를 실행합니다.
테스트용 HTTP 서버와 실제 Laya 검증은 구분합니다. 원본 읽기 전용과 모델 실패 시 BM25 순서
유지를 지켜 주세요. 공개할 권리가 있는 자료만 기여하고 출처·라이선스를 밝힙니다.
두 README의 상태·범위·명령을 함께 수정해 주세요.
