# Attribution and licensing

Brain OpenKit is independently implemented. Original Python code, tests,
synthetic examples and benchmarks, skills, and documentation use the
[MIT License](LICENSE). This repository does not bundle third-party
application code, weights, or copied README artwork.

## Design and workflow reference

[AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian/tree/32ac5a02c4e082e4a5628ca810776375e134708e)
at revision `32ac5a02c4e082e4a5628ca810776375e134708e` informed
source-linked knowledge workflows, preserving passages and references,
ordinary-search fallback, and portable agent skill packaging.
Its README also informed presentation of scope, workflow, and contribution.

Brain OpenKit is not a fork and does not copy that implementation or its
templates. Future code/template reuse must retain notices from the exact
version used. The referenced
[license](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/LICENSE)
and [attribution](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/ATTRIBUTION.md)
remain separate from this project's license.

## Model and service integrations

- [Laya](https://github.com/NandhaKishorM/laya), published under
  [Apache 2.0](https://github.com/NandhaKishorM/laya/blob/main/LICENSE), runs
  separately. The adapter targets **0.3.26**; HTTP validation was checked against
  [2e4d9c87e8b1621deb344eac7de5c7258f32f849](https://github.com/NandhaKishorM/laya/tree/2e4d9c87e8b1621deb344eac7de5c7258f32f849).
- [Laya multilingual weights](https://huggingface.co/convaiinnovations/laya-multilingual)
  are identified as Apache 2.0 in publisher metadata. The tested runtime
  downloads the bundle at
  [7b928d828b7b0e022f929d9bd2e44165aa270148 / multilingual](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148/multilingual).
  This revision belongs to `convaiinnovations/laya`, not the standalone
  `laya-multilingual` repository. Weights are not redistributed here.
- [TypeSafe Jev](https://docs.typesafe.ai/introduction/quickstart) is an
  optional hosted provider with an independently implemented adapter.
  Its request/response contract was checked against the
  [official API documentation](https://docs.typesafe.ai/api),
  [OpenAPI schema](https://api.typesafe.ai/openapi.json), and
  `typesafe-sdk-python` **0.7.2**, revision
  `f078f1e208a0d885154dc758344ae4fce77ac168`.
  These references are also recorded in [the adapter](src/brain_openkit/jev.py).
  Contract fixtures do not establish live-service compatibility; actual-key
  inference remains unverified. API terms and charges are separate from MIT.

MIT does not relicense external components. Distributions containing external
material must preserve applicable notices. Publisher metadata is not an audit
of model training-data rights.

## Host integration references

Original skills and manifests follow the official
[Claude plugin format](https://code.claude.com/docs/en/plugins-reference),
[Claude installation commands](https://code.claude.com/docs/en/plugins/cli-reference),
and [Codex plugin packaging guide](https://developers.openai.com/plugins/build/plugins).
Host applications, subscriptions, models, and service access are not included
in this repository's MIT grant. See the [integration guide](docs/agent-integration.md)
for supported installation routes and validation boundaries.

## Project names

Names identify integrations, compatibility targets, or inspiration. Brain OpenKit
is not affiliated with or endorsed by Obsidian, Convai Innovations, TypeSafe,
Anthropic, OpenAI, or claude-obsidian maintainers. See
[the identity note](docs/project-identity.md) for the name and initial public checks.
