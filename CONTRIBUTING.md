# Contributing to Brain OpenKit

Brain OpenKit is in the design stage. Contributions that clarify the first CLI
release are especially useful: realistic retrieval tasks, Korean/English
examples, provider-contract review, and documentation improvements.

Read the [README](README.md) and
[design specification (Korean)](docs/superpowers/specs/2026-10-04-obsidian-laya-design.md)
before proposing a feature. English and Korean contributions are welcome.

## Propose a change

Describe the task a person is trying to complete, a small concrete example, and
what a successful result would look like. Explain how it fits the first CLI
release or why it belongs in a later milestone.

For larger architectural changes, discuss the approach in an issue before
preparing a large pull request. Keep each pull request focused on one change.

## Contribute evaluation examples

Use synthetic notes or material you have permission to publish. A useful
retrieval example contains a query, a small note collection, the expected
matching note or passage, and an explanation of that match. Category and tag
examples should include the allowed labels and their descriptions.

Identify the example's language and source. Keep personal notes, credentials,
private paths, and identifying metadata out of submitted fixtures. Do not use
model confidence alone as the ground-truth label.

## Update documentation

- Keep [README.md](README.md) and [README.ko.md](README.ko.md) aligned on scope,
  status, commands, and provider support.
- Label proposed commands and unimplemented capabilities explicitly.
- Use repository-relative links for project files.
- Attribute third-party material and preserve required license notices.
- Describe measured results with the dataset, model version, hardware, and
  procedure needed to reproduce them.

## Development status

Application code, dependency manifests, and a test runner have not been added.
There are currently no project installation or test commands to run. The first
implementation contribution should add reproducible setup and validation
instructions alongside the feature it introduces.

The planned implementation keeps vault access, retrieval, and provider adapters
separate. Prefer tests that cover source locations, index updates, malformed
responses, and model-server failures. Label mock-provider results separately
from tests against actual model weights.

## License

By contributing original material, you agree to license it under the project's
[MIT License](LICENSE). You retain your copyright. Third-party code, model
weights, and datasets retain their own licenses; identify their provenance and
terms before including them. See [ATTRIBUTION.md](ATTRIBUTION.md).

## 한국어 안내

현재는 설계 단계입니다. 검색 사례, 한국어·영어 합성 노트와 정답, 제공자 계약 검토,
문서 개선을 환영합니다. 큰 구조 변경은 먼저 이슈로 논의하고, 문서 수정 시 두 README의
상태와 범위를 맞춰 주세요. 공개할 권리가 있는 자료만 기여하고 원문·라이선스를 밝혀 주세요.
