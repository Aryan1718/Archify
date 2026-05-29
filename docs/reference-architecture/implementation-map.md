# Archify Build Map

This document turns the reference architecture notes plus the Archify architecture plan into an implementation map for this repository.

Scope rule:

- Build Archify in the repository root.
- Use the reference implementation only as a behavioral and source reference.
- Do not implement inside the upstream reference codebase.

---

## Product Goal

Archify is not just a graph generator. It is an architecture-understanding system that uses a reference extraction pipeline to produce grounded architecture artifacts.

Target flow:

```text
Repository
  -> structured extraction
  -> graph + facts
  -> architecture context
  -> LLM synthesis
  -> architecture/design outputs
```

Primary product outputs:

- `.archify/graph.json`
- `.archify/facts.json`
- `.archify/modules.json`
- `.archify/routes.json`
- `.archify/database.json`
- `.archify/services.json`
- `.archify/dependencies.json`
- `.archify/docs-summary.json`
- `.archify/architecture-context.md`
- `.archify/design-packet.json`
- `.archify/design-brief.md`
- generated `archify.md`
- optional Mermaid diagrams

Primary product references:

- [Archify plan](./archify_architecture_plan.md)
- [Architecture context layer](./architecture-context-layer.md)

---

## Build Boundary

### Keep Stable From The Reference Implementation

These are the safest parts to mirror closely in v1:

- pipeline shape: `detect -> extract -> build -> cluster -> analyze -> report -> export`
- shared extraction schema
- graph-level confidence tags: `EXTRACTED`, `INFERRED`, `AMBIGUOUS`
- deterministic code-first extraction
- incremental code-only update path
- durable graph artifact plus human-readable summary

Reference:

- [Customization points](./customization-points.md)
- [Pipeline overview](./pipeline-overview.md)
- architecture notes from the reference implementation

### Archify-Specific Additions

These are new layers on top of the reference baseline:

- `.archify/` output contract instead of `reference-out/`
- architecture-specific structured artifacts such as `modules.json` and `services.json`
- architecture-context layer after graph analysis
- agent skill workflow for Claude Code / Codex
- final prompt-ready design document synthesis
- optional Mermaid generation

Reference:

- [Archify plan](./archify_architecture_plan.md)
- [Architecture context layer](./architecture-context-layer.md)

---

## Implementation Phases

## Phase 0 - Repo Skeleton And Contracts

Purpose:

- establish the Archify package and CLI shape
- define output directory and artifact contracts before extraction work starts

Deliverables:

- root-level Archify package and CLI entrypoint
- `.archify/` output directory contract
- extraction schema definitions
- config file format
- ignore file strategy

Decisions for this phase:

- `npx archify init`
- `npx archify analyze .`
- `npx archify generate .`
- `npx archify clean`
- whether implementation is Node CLI + Python engine, pure Node, or pure Python behind `npx`

Reference:

- [Archify plan](./archify_architecture_plan.md)
- reference CLI orchestration
- reference package layout

Recommended output contract for v1:

```text
.archify/
  graph.json
  GRAPH_REPORT.md
  facts.json
  modules.json
  routes.json
  database.json
  services.json
  dependencies.json
  docs-summary.json
  architecture-context.json
  architecture-context.md
```

Status:

- required before coding the pipeline

---

## Phase 1 - Repository Scan And Classification

Purpose:

- discover the repository safely
- classify files before extraction

What to copy closely from the reference implementation:

- extension-based classification
- shebang detection for extensionless scripts
- ignore and sensitive-file skipping
- clear separation between intake and extraction

Archify adaptation:

- configuration-driven file scope
- `.archifyignore` or Archify-specific ignore strategy
- early tagging of likely architecture-relevant files such as routes, config, migrations, infra, docs

Outputs:

- categorized file inventory
- repository stats
- manifest for later incremental updates

Reference:

- [Code extraction notes: discovery and classification](./code-extraction.md)
- [Pipeline overview: detect stage](./pipeline-overview.md)
- reference detect stage

Acceptance criteria:

- stable repository scan across repeated runs
- supported code files are classified correctly
- ignored and sensitive files are skipped consistently

---

## Phase 2 - Deterministic Code Extraction

Purpose:

- produce grounded graph fragments from source code without model calls

What to copy closely from the reference implementation:

- shared extraction schema: `nodes`, `edges`, optional `hyperedges`
- stable IDs
- per-language extraction architecture
- confidence tagging on edges
- validation boundary before graph build

Archify adaptation:

- start with the languages needed for this repo scope
- add architecture-relevant symbol categories where useful
- preserve compatibility with the reference graph fragment contract

Outputs:

- extraction fragments per file
- validated nodes and edges with confidence metadata

Reference:

- [Code extraction](./code-extraction.md)
- [Pipeline overview: extract stage](./pipeline-overview.md)
- reference extract stage
- reference validation boundary

Acceptance criteria:

- stable IDs across repeated runs
- structural edges preserve direction
- direct syntax relationships are marked `EXTRACTED`
- weaker resolved relationships are marked `INFERRED` or `AMBIGUOUS`

---

## Phase 3 - Graph Build, Dedup, And Clustering

Purpose:

- merge extraction fragments into one navigable repository graph

What to copy closely from the reference implementation:

- graph build as an explicit stage
- normalization before merge
- explicit dedup subsystem
- community detection after graph assembly
- stable community ordering

Archify adaptation:

- keep graph export compatible enough for downstream analysis
- add metadata needed by architecture-specific consumers

Outputs:

- merged repository graph
- community assignments
- deduplicated entities

Reference:

- [Graph assembly and analysis](./graph-assembly-and-analysis.md)
- [Pipeline overview: build and cluster stages](./pipeline-overview.md)
- reference build stage
- reference cluster stage

Acceptance criteria:

- repeated runs on unchanged code produce stable graph size and community structure
- dangling internal edges are handled predictably
- communities are available as graph metadata

---

## Phase 4 - Graph Analysis And Report Layer

Purpose:

- turn the graph into useful repository understanding before architecture synthesis

What to copy closely from the reference implementation:

- god-node analysis
- surprising-connection ranking
- suggested-question generation
- human-readable report as a navigation layer

Archify adaptation:

- report should still serve both engineers and agents
- report may emphasize architecture-relevant hubs, boundaries, and uncertainty

Outputs:

- `.archify/GRAPH_REPORT.md`
- analysis metadata for later architecture context generation

Reference:

- [Graph assembly and analysis](./graph-assembly-and-analysis.md)
- [Pipeline overview: analyze and report stages](./pipeline-overview.md)
- reference analyze stage
- reference report stage

Acceptance criteria:

- report surfaces main hubs, cross-boundary relationships, and ambiguity
- report remains useful without any LLM synthesis

---

## Phase 5 - Archify Architecture Context Layer

Purpose:

- transform graph structure into subsystem-level architecture context

This is the main Archify-specific stage.

Pipeline position:

```text
detect -> extract -> build -> cluster -> analyze -> architecture_context -> export
```

What this stage should do:

- identify subsystems
- infer dependency directions between subsystems
- surface interfaces and entrypoints
- summarize key flows
- capture cross-cutting concerns
- preserve evidence for every major claim
- record open questions where certainty is weak

Primary outputs:

- `.archify/architecture-context.json`
- `.archify/architecture-context.md`

Suggested top-level sections:

- `system`
- `subsystems`
- `interfaces`
- `data_flows`
- `cross_cutting_concerns`
- `key_entrypoints`
- `external_dependencies`
- `evidence`
- `open_questions`

Reference:

- [Architecture context layer](./architecture-context-layer.md)
- [Archify plan](./archify_architecture_plan.md)
- reference graph export contract

Acceptance criteria:

- subsystem summaries are traceable back to graph evidence
- interface and flow claims distinguish fact from inference
- missing certainty becomes open questions, not invented certainty

---

## Phase 6 - Structured Architecture Artifacts

Purpose:

- break architecture understanding into machine-readable domain artifacts

Archify-specific outputs:

- `.archify/facts.json`
- `.archify/modules.json`
- `.archify/routes.json`
- `.archify/database.json`
- `.archify/services.json`
- `.archify/dependencies.json`
- `.archify/docs-summary.json`

How to derive them:

- `facts.json`: normalized confirmed findings with evidence and confidence
- `modules.json`: subsystem/module inventory from graph + clustering + context layer
- `routes.json`: extracted HTTP or CLI entrypoints where detectable
- `database.json`: models, queries, migrations, schema boundaries where detectable
- `services.json`: service classes, adapters, integrations, background jobs
- `dependencies.json`: internal and external dependency summaries
- `docs-summary.json`: distilled repository docs aligned to code structure

Reference:

- [Archify plan](./archify_architecture_plan.md)
- [Architecture context layer](./architecture-context-layer.md)
- [Semantic extraction](./semantic-extraction.md)

Acceptance criteria:

- each artifact has clear evidence provenance
- confirmed facts are separable from inferred summaries
- artifacts reduce the need to reread raw source files

---

## Phase 7 - Semantic And Documentation Extraction

Purpose:

- enrich the code graph with non-code context after the code-first baseline works

What to copy closely from the reference implementation:

- semantic extraction is a layer, not the foundation
- conversion of complex formats into normalized text sidecars
- merged output still uses the same graph schema

Archify adaptation:

- prioritize repository docs first
- keep media, Office, PDFs, and Google Workspace as later capability unless required
- focus prompts and extraction policy on architecture rationale and system understanding

Outputs:

- enriched graph nodes and edges
- `docs-summary.json`
- stronger architecture context quality

Reference:

- [Semantic extraction](./semantic-extraction.md)
- [Pipeline overview](./pipeline-overview.md)
- how-it-works documentation from the reference implementation

Acceptance criteria:

- doc extraction enriches, but does not replace, code structure
- code-only runs do not require this stage
- semantic fragments still validate against the same graph schema

---

## Phase 8 - Incremental Updates

Purpose:

- make Archify usable in active development without full rebuilds

What to copy closely from the reference implementation:

- code-only partial rebuilds
- preserve semantic graph state when docs did not change
- remove deleted-file nodes
- rerun build, cluster, analyze, context, and export on partial updates

Archify adaptation:

- incremental refresh must also regenerate architecture-context artifacts
- later, allow artifact-level invalidation such as routes-only or docs-only refresh

Outputs:

- stable `.archify/` refresh behavior
- manifest and lock support

Reference:

- [Incremental update and outputs](./incremental-update-and-outputs.md)
- [Pipeline overview: update mode](./pipeline-overview.md)
- reference incremental update path

Acceptance criteria:

- unchanged input gives stable outputs
- changed code updates only affected graph fragments
- code-only updates avoid semantic extraction work

---

## Phase 9 - Final Synthesis And Agent Workflow

Purpose:

- connect the generated Archify artifacts to coding-agent workflows

What this phase includes:

- skill installation flow
- project-level and global-level skill installation
- skill invocation pattern for Claude Code and Codex
- permissioned CLI execution from the skill
- final `archify.md` generation from `.archify/` artifacts

Target outputs:

- `.archify/design-packet.json`
- `.archify/design-brief.md`
- `archify.md`
- optional Mermaid diagrams

Reference:

- [Archify plan](./archify_architecture_plan.md)
- reference skill orchestration
- shared skill reference

Acceptance criteria:

- the agent does not inspect the whole repository blindly
- the agent reads grounded Archify artifacts first
- generated docs cite facts, evidence, and uncertainty clearly

---

## Phase 10 - Optional Consumers And Polish

Purpose:

- add optional outputs after the core system is reliable

Optional features:

- HTML visualization
- wiki pages
- call-flow pages
- cross-repository graph merging
- benchmark and freshness metadata

Reference:

- [Incremental update and outputs](./incremental-update-and-outputs.md)
- [Customization points](./customization-points.md)
- reference export stage
- reference wiki layer
- reference callflow export

---

## Recommended Build Order

Build in this order:

1. Phase 0: contracts and CLI skeleton
2. Phase 1: repository scan and classification
3. Phase 2: deterministic code extraction
4. Phase 3: graph build, dedup, and clustering
5. Phase 4: analysis and report
6. Phase 5: architecture context layer
7. Phase 6: structured architecture artifacts
8. Phase 8: incremental updates
9. Phase 9: agent workflow and final synthesis
10. Phase 7: semantic extraction
11. Phase 10: optional consumers and polish

Reason for this order:

- Archify's core value is grounded architecture generation from code first
- semantic extraction improves quality, but should not block a useful v1
- the architecture-context layer is the first major Archify-specific differentiator

---

## What Comes From The Reference System Vs Archify

### Copy Closely

- file detection and intake model
- deterministic AST extraction structure
- shared graph fragment schema
- build, dedup, and clustering pattern
- analysis model for hubs and cross-boundary links
- report as a navigation artifact
- incremental code-only update strategy

Primary references:

- reference architecture
- reference detect stage
- reference extract stage
- reference build stage
- reference cluster stage
- reference analyze stage
- reference report stage
- reference export stage
- reference update path

### Adapt For Archify

- output directory from `reference-out/` to `.archify/`
- report shape toward architecture use
- supported file policy based on architecture needs
- ontology tuned for modules, interfaces, routes, services, data flows

Primary references:

- [Customization points](./customization-points.md)
- [Semantic extraction](./semantic-extraction.md)

### Build New

- architecture-context stage
- architecture-specific machine-readable artifacts
- architecture and design document synthesis
- agent-install workflow
- diagram prompt generation

Primary references:

- [Archify plan](./archify_architecture_plan.md)
- [Architecture context layer](./architecture-context-layer.md)

---

## V1 Definition

Archify v1 should be considered complete when it can:

- scan a repository deterministically
- extract supported code into a validated graph
- build and cluster that graph
- generate a useful human-readable report
- generate `architecture-context.json` and `architecture-context.md`
- emit architecture-oriented structured artifacts in `.archify/`
- separate confirmed facts from inferred claims
- regenerate incrementally for code-only changes
- support an agent workflow that produces grounded `archify.md`

V1 does not require:

- full media extraction parity
- Google Workspace support
- wiki export
- callflow HTML
- cross-repository graph features

---

## Reference Index

Core planning docs in this repo:

- [README.md](./README.md)
- [archify_architecture_plan.md](./archify_architecture_plan.md)
- [pipeline-overview.md](./pipeline-overview.md)
- [code-extraction.md](./code-extraction.md)
- [graph-assembly-and-analysis.md](./graph-assembly-and-analysis.md)
- [architecture-context-layer.md](./architecture-context-layer.md)
- [incremental-update-and-outputs.md](./incremental-update-and-outputs.md)
- [semantic-extraction.md](./semantic-extraction.md)
- [customization-points.md](./customization-points.md)

Primary reference docs:

- architecture documentation
- project README
- how-it-works documentation

Primary reference modules:

- CLI orchestration
- detect
- extract
- validate
- build
- cluster
- analyze
- report
- export
- wiki
- update
- callflow export

Behavioral test references:

- pipeline tests
- incremental tests
- update-path tests
- wiki tests
