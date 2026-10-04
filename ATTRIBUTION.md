# Attribution and licensing

Brain OpenKit is independently implemented. Original Python code, tests,
synthetic examples, and documentation use the [MIT License](LICENSE).
This repository does not bundle third-party application code, weights,
or copied README artwork.

## Design and workflow reference

[AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian/tree/32ac5a02c4e082e4a5628ca810776375e134708e)
at revision `32ac5a02c4e082e4a5628ca810776375e134708e` informed the
source-linked workflow: preserving original passages and references, and
retaining ordinary search results when model processing is unavailable.
Its README also informed presentation of scope, workflow, and contribution.

Brain OpenKit is not a fork and does not copy that implementation. Future
code/template reuse must retain notices from the exact version used.
The referenced [license](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/LICENSE)
and [attribution](https://github.com/AgriciDaniel/claude-obsidian/blob/32ac5a02c4e082e4a5628ca810776375e134708e/ATTRIBUTION.md)
remain separate from this project's license.

## Model integration

- [Laya](https://github.com/NandhaKishorM/laya), published under
  [Apache 2.0](https://github.com/NandhaKishorM/laya/blob/main/LICENSE), runs
  separately. The adapter targets **0.3.26**; HTTP validation was checked against
  [2e4d9c87e8b1621deb344eac7de5c7258f32f849](https://github.com/NandhaKishorM/laya/tree/2e4d9c87e8b1621deb344eac7de5c7258f32f849).
- [Laya multilingual weights](https://huggingface.co/convaiinnovations/laya-multilingual)
  are identified as Apache 2.0 in publisher metadata. The server downloads
  the multilingual checkpoint from the Laya bundle; the tested bundle revision
  and subfolder are
  [7b928d828b7b0e022f929d9bd2e44165aa270148 / multilingual](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148/multilingual).
  Weights are not redistributed with Brain OpenKit.
- [TypeSafe Jev](https://docs.typesafe.ai/introduction/quickstart) is a planned,
  unimplemented hosted provider. Its terms govern API access separately from MIT.

MIT does not relicense external components. Future distributions containing
external material must preserve applicable notices. Model metadata is not
an audit of training-data rights.

## Project names

Names identify integrations, compatibility targets, or inspiration. Brain OpenKit
is not affiliated with or endorsed by Obsidian, Convai Innovations, TypeSafe,
or claude-obsidian maintainers. See [the identity note](docs/project-identity.md)
for the name and initial public checks.
