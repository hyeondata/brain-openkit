---
name: brain-research
description: Research a bounded topic with the host's search tools and optionally file a cited dossier in a selected vault. Use for research-and-save requests.
---

Read the [runtime contract](../references/runtime.md) first. Respect the user's
topic, source restrictions and existing authorization to browse. State a bounded
plan: by default at most three search rounds and ten opened sources. Use tighter
user limits. Ask only when required scope or permission is missing; do not ask
again after the user has requested public-web research.

Use the host's actual search/browser tools, preferring primary sources. A public
query should contain topic terms, not private vault excerpts or credentials.
If web tools are unavailable, use supplied sources/vault and state that limit.
Search existing knowledge when a vault is selected. Stop when the question is
supported, the budget is used, sources repeat, or the user stops.

Record source title, URL, retrieval date, specific evidence, and uncertainty.
Compare contradictory evidence rather than selecting only supporting results.
Return a cited answer and coverage gaps. Research alone does not authorize
saving or expanding unrelated canonical notes.

For an authorized research-and-save task, draft the dossier to a temporary
UTF-8 file outside the vault, keeping source URLs alongside supported claims.
Use brain-save's CLI flow:

```bash
python3 "$BRAIN_RUNNER" save "$BRAIN_DRAFT" --path "Notes/research-dossier.md" --vault "$BRAIN_VAULT" --plan "$BRAIN_PLAN" --json
```

Add repeated --source values for actual supporting vault notes. Inspect the
complete plan and apply within the requested scope using the runtime sequence.
Report citations, limitations, saved paths, and transaction ID. The host did
the research and prose generation; Laya/Jev did not generate the dossier.
