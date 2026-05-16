# Architecture Context Layer

This note describes the next layer to build on top of graphify for our use case.

The goal is not full architecture generation yet. The goal is to create a stronger intermediate representation that is much closer to architecture than raw `graph.json`, so an agent or later renderer can produce architecture docs, diagrams, and explanations with less guesswork.

## Why This Layer Exists

Graphify already solves the first hard problem: understanding a codebase as a graph instead of as a pile of files.

That gives us:

- entities such as modules, files, classes, functions, doc concepts
- relationships such as imports, calls, references, semantic links
- communities, god nodes, and surprising cross-boundary connections

But that is still not the same thing as architecture.

Architecture usually needs a higher-level view:

- subsystem boundaries
- dependency directions between subsystems
- public interfaces
- key entrypoints
- data or control flows
- cross-cutting concerns
- architecture rationale and uncertainty

So the missing step is an architecture-context layer that converts graph structure into subsystem-level context.

## Design Position

This should be an additive layer on top of stock graphify, not a rewrite of the base graph pipeline.

Keep the existing baseline stable:

- `detect -> extract -> build -> cluster -> analyze -> report -> export`
- same `graph.json` contract
- same code-first extraction pipeline
- same incremental code-only updates

Add one new conceptual stage after `analyze()`:

```text
detect -> extract -> build -> cluster -> analyze -> architecture_context -> export
```

In practice, this means:

- graphify still produces `graph.json`
- the new layer reads `graph.json` and analysis outputs
- the new layer emits architecture-oriented artifacts

This is the safest way to stay compatible with upstream graphify while getting closer to architecture generation.

## Inputs

V1 should use code plus docs-derived context already present in the graph.

Primary inputs:

- graph nodes and edges from `graph.json`
- community assignments from clustering
- god nodes from analysis
- surprising connections from analysis
- doc/rationale nodes extracted into the graph
- source paths and symbol metadata

Optional helpful inputs if available:

- report sections from `GRAPH_REPORT.md`
- community labels
- callflow export hints

The architecture-context layer should still work if docs are weak or missing. Docs are enrichment, not the structural foundation.

## Outputs

V1 should emit both a machine-readable and a human-readable artifact.

Suggested outputs:

- `graphify-out/architecture-context.json`
- `graphify-out/ARCHITECTURE_CONTEXT.md`

### Purpose Of `architecture-context.json`

This is the main intermediate artifact for downstream agents.

It should be optimized for:

- strong architectural context
- evidence-backed summaries
- stable references into the underlying graph
- low need to re-read raw source files

### Purpose Of `ARCHITECTURE_CONTEXT.md`

This is the human-readable companion.

It should help an engineer or agent quickly answer:

- what are the main subsystems?
- how do they relate?
- where are the main boundaries and interfaces?
- what are the key flows?
- what is still ambiguous?

## Proposed Artifact Shape

The exact schema can evolve, but v1 should be centered on these top-level sections:

- `system`
- `subsystems`
- `interfaces`
- `data_flows`
- `cross_cutting_concerns`
- `key_entrypoints`
- `external_dependencies`
- `evidence`
- `open_questions`

### `system`

High-level summary of the codebase:

- project name
- one-paragraph description
- dominant architectural style if inferable
- top-level directories or domains
- overall dependency shape

### `subsystems`

This is the core of the artifact.

Each subsystem should have:

- `id`
- `name`
- `summary`
- `kind`
- `source_paths`
- `key_symbols`
- `responsibilities`
- `depends_on`
- `depended_on_by`
- `public_interfaces`
- `internal_signals`
- `evidence_node_ids`

`kind` should use a small controlled vocabulary such as:

- `service`
- `module`
- `domain`
- `adapter`
- `infrastructure`
- `ui`
- `data_layer`
- `shared_library`

### `interfaces`

Capture explicit or likely boundaries:

- exported APIs
- HTTP routes or handlers
- CLI entrypoints
- service facades
- database access boundaries
- events/messages if detectable

### `data_flows`

Describe major directed flows between subsystems:

- source subsystem
- target subsystem
- relation or flow type
- short summary
- evidence references

These do not need to be runtime-perfect in v1. They do need to be evidence-backed and useful.

### `cross_cutting_concerns`

Surface concerns that span many subsystems, for example:

- auth
- config
- logging
- caching
- error handling
- persistence
- observability
- feature flags

### `key_entrypoints`

List the most important starting points into the system:

- app/server bootstraps
- CLI main commands
- background worker roots
- request handlers or controllers with broad fan-out

### `external_dependencies`

Summarize major dependencies outside the project:

- external packages that appear architecturally central
- databases
- third-party services if inferable
- infrastructure libraries

### `evidence`

This section should preserve traceability back to the underlying graph:

- node IDs
- edge IDs or `(source, relation, target)` references
- source paths
- source locations when available

Every major claim in the architecture-context layer should be traceable.

### `open_questions`

This is required.

The system should not force certainty where the graph is weak. If grouping, naming, or flow inference is weak, record an open question instead of inventing a clean story.

## Inference Strategy

V1 should be hybrid:

- deterministic heuristics first
- LLM-assisted labeling and summarization second

This is important. The model should not invent the architecture from raw files. It should summarize evidence extracted from the graph.

### Deterministic Heuristics

Start from graph structure and filesystem structure.

Recommended signals:

- graph communities
- directory boundaries
- import density between groups
- call density between groups
- shared dependencies
- hub and bridge nodes
- exported/public symbols
- unresolved/external dependency patterns

Recommended grouping flow:

1. Start with communities as candidate subsystem seeds.
2. Compare each community against filesystem/module boundaries.
3. Merge or split groups when graph structure and path structure strongly disagree.
4. Identify subsystem dependencies from aggregated inter-group edges.
5. Identify public interfaces from exported symbols, handlers, entrypoints, and façade-like nodes.
6. Identify likely cross-cutting concerns from nodes with broad multi-community reach.

### LLM-Assisted Summarization

After groups are formed, use a model to:

- name subsystems clearly
- summarize responsibilities
- describe main flows in plain language
- extract a short system summary
- turn raw evidence into concise architecture-context Markdown

The LLM should not choose the grouping from scratch in v1. It should operate on grouped evidence.

## Relationship To Full Architecture Generation

This layer is intentionally one step short of the final architecture product.

It is meant to make final architecture generation much easier by giving a later stage:

- cleaned subsystem boundaries
- summarized dependency structure
- candidate interfaces and entrypoints
- architecture-relevant evidence
- explicit uncertainty

Once this exists, a downstream architecture generator can produce:

- Mermaid diagrams
- subsystem maps
- architecture summaries
- review notes
- dependency or layering observations

That later generator should read `architecture-context.json` first, not raw files first.

## Why This Is The Right Next Step

For our use case, this is the right move because:

- graphify already solves repo understanding
- raw graph outputs are still too low-level for direct architecture generation
- a subsystem-oriented intermediate representation reduces hallucination
- architecture generation becomes more repeatable when it is grounded in evidence-backed context
- it lets us keep upstream graphify compatibility while adding our own higher-level reasoning layer

## V1 Boundaries

What v1 should do:

- summarize the codebase into subsystem/module-level architecture context
- use code and docs already present in the graph
- produce JSON plus Markdown
- prioritize downstream agent consumption

What v1 should not try to do:

- produce perfect runtime architecture
- infer every data flow with certainty
- replace graphify’s base graph model
- become a full architecture decision system

## Recommended Next Implementation Direction

When this is implemented later, the safest path is:

1. Keep `graph.json` untouched.
2. Build a post-processing module that reads the graph and analysis outputs.
3. Emit `architecture-context.json`.
4. Render `ARCHITECTURE_CONTEXT.md` from that JSON.
5. Add architecture-specific exports only after the intermediate layer is stable.
