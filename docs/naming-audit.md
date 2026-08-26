# EvalTrim 1.0 naming audit

Public conflict search performed on 2026-08-26. **Trademark/domain legal clearance is not established.** A 404 is not clearance.

**Decision: keep EvalTrim.** No candidate was clearly more memorable, distinctive, and worth a post-1.0 CLI/package migration.

## Chosen name

**EvalTrim** — already the 1.0.0 product, PyPI/module/CLI name, and GitHub repo slug.

## Candidates

| Name | Fit | GitHub | PyPI | npm | Product Hunt | Web | Pronounce / spell | Dev-tool fit | Extensibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **EvalTrim** | Describes suite maintenance (trim what is redundant; keep witnesses) | This project: `lowjieseng1810/evaltrim`. Adjacent: `tooltrim` (LLM tool-output compression, different job) | No live `evaltrim` package found in public search (PyPI HTML challenge). Crowded `eval*` namespace (evalcore, evalrun, evalytic) | Search blocked by CDN challenge; no known eval-harness named evaltrim | No Product Hunt hit found for an eval-suite product named EvalTrim | “Eval” is generic in LLM tooling | Easy / easy | Strong CLI name | “Trim” is narrower than “control plane”; still covers maintenance |
| Keepplane | Control-plane vibe | **keeplane** (agentsurf credential control plane). **Plane** (makeplane/plane, 57k★ PM tool) | Unchecked exact; Plane adjacency is the issue | Unchecked | Unchecked | Strong “Plane” adjacency | Easy / Keep-plane vs keeplane | Weak: looks like PM/infra | Broad, but collision-heavy |
| Suitewit | Witness + suite | **Suitest** (QA platform). **suitewright** (Google Workspace CLI) | suitewright exists | Unchecked | Unchecked | Easy to hear as Suitest | Medium / high (wit vs wright vs test) | OK | Witness-centric, less “control plane” |
| Mastline | Distinct coinage | **Mastra** (27k★ TypeScript agent framework) is a close look-alike | Unchecked | @mastra/* is large | Unchecked | Mast / Mastra confusion | Medium | Weak next to Mastra | Broad but risky |

Additional candidates considered (none recommended):

| Name | Why rejected |
| --- | --- |
| Witkeep | Invented; less searchable; “wit” spelling risk |
| Coverline | Generic; airline/insurance adjacency |
| Evalkeep | Still EvalX; weaker than EvalTrim |
| Suiteline | Suitest adjacency |
| Keepwit | Hard to spell; cute over credible |
| Trimline | Cisco Trimline / telephony adjacency |
| Witnessplane | Too long; “plane” collisions |

## Why EvalTrim won

1. The 1.0 CLI, import path, and GitHub remote already use it.
2. Alternatives have **stronger** public adjacency (Plane/keeplane, Suitest, Mastra) than EvalTrim’s overlap with the crowded `eval*` prefix.
3. `tooltrim` is a real but **different** product (compress tool results, not maintain eval suites). Document the distinction; do not rename to dodge it.
4. A rename after 1.0.0 would split GitHub stars, pip installs, and muscle memory without a material brand gain.

Public conflict search performed; trademark/domain legal clearance not established.
