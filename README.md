# Archify

```text
    _              _     _  __       
   / \   _ __ ___| |__ (_)/ _|_   _ 
  / _ \ | '__/ __| '_ \| | |_| | | |
 / ___ \| | | (__| | | | |  _| |_| |
/_/   \_\_|  \___|_| |_|_|_|  \__, |
                              |___/ 
```

```bash
npx archify init
```
Archify prepares a repository for architecture understanding. It sets up project configuration, builds grounded repository artifacts, and installs the Archify skill for the local workflow.

## Quick Start

From the root of the repository:

Then use Archify from your assistant:

```text
Use Archify on this repo
```

## How It Helps

- Builds a grounded repository knowledge base inside `.archify/`
- Reuses existing artifacts when they are already fresh
- Refreshes analysis only when the repository has changed
- Prepares a design packet used to create `archify.md`

## Flow

1. Run `npx archify init` once in the repository.
2. Ask your assistant to use Archify.
3. Archify decides what to do next:
   - initialize if setup is missing
   - analyze if knowledge is missing or stale
   - generate if the design packet is missing or stale
   - reuse existing artifacts if everything is fresh

## Commands

| Command | Purpose |
| --- | --- |
| `npx archify init` | Set up Archify in the current repository |
| `npx archify status` | Show setup state, artifact freshness, and the next recommended action |
| `npx archify analyze .` | Build or refresh the grounded repository knowledge in `.archify/` |
| `npx archify generate .` | Build the design packet used for `archify.md` |
| `npx archify clean` | Remove generated artifacts from `.archify/` |

## Project Files

After setup, the repository will contain:

```text
.
├── archify.config.json
├── .archifyignore
├── .agents/
│   └── skills/
│       └── archify/
│           └── SKILL.md
├── .claude/
│   └── skills/
│       └── archify/
│           └── SKILL.md
└── .archify/
    ├── graph.json
    ├── GRAPH_REPORT.md
    ├── facts.json
    ├── modules.json
    ├── routes.json
    ├── database.json
    ├── services.json
    ├── dependencies.json
    ├── docs-summary.json
    ├── architecture-context.json
    ├── architecture-context.md
    ├── manifest.json
    ├── design-packet.json
    └── design-brief.md
```

Notes:
- `.agents/.../SKILL.md` is created for Codex project installs.
- `.claude/.../SKILL.md` is created for Claude Code project installs.
- `.archify/` is created when analysis or generation runs.

## Main Outputs

| File | Purpose |
| --- | --- |
| `archify.config.json` | Project-level Archify configuration |
| `.archifyignore` | Ignore rules for repository scanning |
| `.archify/manifest.json` | Analysis state and freshness metadata |
| `.archify/graph.json` | Repository graph output |
| `.archify/architecture-context.json` | Grounded architecture-facing context |
| `.archify/design-packet.json` | Input packet used to author `archify.md` |
| `archify.md` | Final architecture prompt pack written by the skill |

## Repository Coverage

Archify analyzes repository structure and documentation, including:

- source files
- routes and entrypoints
- dependencies
- database and migration files
- README and supporting architecture documents

## Usage Notes

- `init` is the main setup command.
- `status` is the main inspection command.
- `analyze` and `generate` are available for manual workflows, but the installed skill is designed to run them when needed.
- Supporting docs such as `README.md` can be gathered alongside analysis, but grounded `.archify/` artifacts remain the primary source of confirmed facts.
