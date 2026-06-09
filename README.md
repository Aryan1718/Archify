<div align="center">

<pre>
    _              _     _  __
   / \   _ __ ___| |__ (_)/ _|_   _
  / _ \ | '__/ __| '_ \| | |_| | | |
 / ___ \| | | (__| | | | |  _| |_| |
/_/   \_\_|  \___|_| |_|_|_|  \__, |
                              |___/
</pre>

<p><strong>Grounded codebase documentation</strong></p>

<p><code>npx archify init</code></p>

</div>

Archify extracts grounded architecture and codebase context from a repository so it is easier to study, understand, and build similar systems.

## Quick Start

From the root of the repository:

```bash
npx archify init
```

Then use Archify from your assistant:

```text
Use Archify on this repo
```

## What It Does

- Builds a grounded repository knowledge base inside `.archify/`
- Reuses existing artifacts when they are already fresh
- Refreshes analysis only when the repository has changed
- Generates synthesis packets and guide artifacts used to study the codebase and write the selected output document

## How It Works

1. Run `npx archify init` once in the repository.
2. Ask your assistant to use Archify.
3. Archify checks status and decides what to do next.

What Archify does next:
- initialize if setup is missing
- analyze if knowledge is missing or stale
- generate if the design packet or guide artifacts are missing or stale
- write if the selected final document is missing or stale
- reuse existing artifacts if everything is fresh

## Commands

| Command | Purpose |
| --- | --- |
| `npx archify init` | Set up Archify in the current repository |
| `npx archify status [--doc-type <type>]` | Show setup state, doc-specific artifact freshness, and the next recommended action |
| `npx archify analyze .` | Build or refresh the grounded repository knowledge in `.archify/` |
| `npx archify generate . [--doc-type <type>]` | Build the synthesis packet and guide artifacts for the selected document type |
| `npx archify write . [--doc-type <type>]` | Write the selected root-level document from the generated synthesis artifacts |
| `npx archify clean` | Remove generated artifacts from `.archify/` |

## Generated Files

Archify adds:

- `archify.config.json` for project configuration
- `.archifyignore` for scan exclusions
- project skill files for Codex or Claude Code installs
- `.archify/` for analysis, synthesis, and guide artifacts

## Core Artifacts

| File | Purpose |
| --- | --- |
| `archify.config.json` | Project-level Archify configuration |
| `.archifyignore` | Ignore rules for repository scanning |
| `.archify/manifest.json` | Analysis state and freshness metadata |
| `.archify/graph.json` | Repository graph output |
| `.archify/architecture-context.json` | Grounded architecture context |
| `.archify/docs/<docType>/packet.json` | Doc-scoped synthesis packet used to author the selected root document |
| `.archify/docs/<docType>/guide.json` | Section-by-section guide for generating the selected root document |
| `.archify/docs/<docType>/brief.md` | Human-readable synthesis brief for the selected document type |
| `.archify/docs/<docType>/guide.md` | Human-readable guide brief for the selected document type |
| Root document output | `archify.md` by default, or the file mapped from `--doc-type` |

## Available Documents

Archify supports these document types today:

| `--doc-type` value | Output file |
| --- | --- |
| `archify` | `archify.md` |
| `tech_stack` | `TECH_STACK.md` |
| `api_design` | `API_DESIGN.md` |
| `data_model` | `DATA_MODEL.md` |
| `conventions` | `CONVENTIONS.md` |
| `glossary` | `GLOSSARY.md` |
| `flows` | `FLOWS.md` |
| `test_cases` | `TEST_CASES.md` |

If `--doc-type` is omitted, Archify defaults to `archify` and writes `archify.md`.

Examples:

```bash
npx archify status --doc-type tech_stack
npx archify generate . --doc-type api_design
npx archify write . --doc-type flows
```

## Repository Understanding

Archify analyzes repository structure and documentation, including:

- source files
- routes and entrypoints
- dependencies
- database and migration files
- README and supporting architecture documents

Documentation generation is guide-driven:

- `analyze` produces grounded `.archify` artifacts
- `generate` produces a doc-scoped synthesis packet plus a doc-scoped guide
- `write` materializes the selected root document from those artifacts
- the installed skill reads the selected doc type's packet and guide before drafting that document

## Notes

- `init` is the main setup command.
- `status` is the main inspection command.
- `analyze`, `generate`, and `write` are available for manual workflows, but the installed skill is designed to run them when needed.
- Supporting docs such as `README.md` can be gathered alongside analysis, but grounded `.archify/` artifacts remain the primary source of confirmed facts.
