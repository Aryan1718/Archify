# Archify - Application Architecture Understanding System

## Overview

Archify is a CLI-based architecture understanding system that helps developers generate grounded and factual architecture documentation directly from a source code repository.

The system combines:

- Repository scanning
- Knowledge graph generation
- Documentation understanding
- Structured architecture extraction
- AI-assisted architecture synthesis

The goal is to allow users to invoke a simple skill inside coding agents like Claude Code or Codex and automatically generate:

- `archify_design.md`
- internal grounded design packets in `.archify/`
- prompt-ready design briefs for external model use
- Optional Mermaid diagrams
- System understanding summaries

---

# Core Philosophy

Archify should NEVER ask the LLM to blindly understand an entire repository.

Instead, the system follows:

```text
Codebase
    ↓
Structured Extraction
    ↓
Knowledge Graph + Facts
    ↓
Architecture Context
    ↓
LLM Synthesis
```

The LLM only works on grounded extracted context.

This improves:

- Reliability
- Factual accuracy
- Consistency
- Scalability
- Token efficiency

---

# High-Level Workflow

```text
User installs Archify
        ↓
Archify installs agent skill
        ↓
User invokes skill inside Claude Code / Codex
        ↓
Skill requests permission to run Archify CLI
        ↓
Archify scans repository
        ↓
Archify builds knowledge graph + architecture context
        ↓
Agent reads generated context
        ↓
Agent generates `archify_design.md`
```

---

# User Installation Flow

## Quick Install

```bash
npx archify init
```

This command should:

1. Install required package dependencies
2. Install agent skill templates
3. Ask user where to install skills
4. Create Archify configuration
5. Prepare analysis environment

---

# Skill Installation Modes

## Project-Level Installation

Installs skills only for the current repository.

Example:

```text
.repo/.agent-skills/archify/
```

Use Case:
- Team-specific workflows
- Repository-specific architecture generation
- Shared team setup

---

## Global-Level Installation

Installs skills globally for all repositories.

Example:

```text
~/.agent-skills/archify/
```

Use Case:
- Personal developer setup
- Reusable architecture tooling
- Global coding assistant integration

---

# Agent Workflow

After installation, the user can invoke the skill inside Claude Code or Codex.

Example:

```text
Use the Archify skill on this repository.
```

The skill should then:

1. Ask permission to run Archify CLI
2. Run repository analysis
3. Wait for generated architecture context
4. Generate `archify_design.md`

---

# CLI Commands

## Initialize Archify

```bash
npx archify init
```

## Analyze Repository

```bash
npx archify analyze .
```

## Generate Architecture Context

```bash
npx archify generate .
```

## Clean Generated Files

```bash
npx archify clean
```

---

# Output Directory Structure

Archify should generate a hidden directory:

```text
.archify/
```

Example structure:

```text
.archify/
    graph.json
    facts.json
    modules.json
    routes.json
    database.json
    services.json
    dependencies.json
    docs-summary.json
    architecture-context.md
```

---

# Core Analysis Pipeline

## Stage 1 - Repository Scan

Purpose:
- Discover repository structure
- Identify important files
- Ignore unnecessary files

---

## Stage 2 - File Classification

Purpose:
- Categorize repository files

---

## Stage 3 - Symbol Extraction

Purpose:
- Extract important code symbols

---

## Stage 4 - Relationship Mapping

Purpose:
- Build code relationships

---

## Stage 5 - Knowledge Graph Generation

Purpose:
- Create repository understanding graph

---

## Stage 6 - Documentation Understanding

Purpose:
- Read repository documentation

---

## Stage 7 - Architecture Extraction

Purpose:
- Generate factual architecture understanding

Must distinguish:

```text
Confirmed Facts
vs
Assumptions / Inferences
```

---

# Important Rule

The generated architecture must clearly separate:

## Confirmed From Codebase

Example:

```text
- FastAPI is used as backend framework
- PostgreSQL is used as database
- Redis is used for background queues
```

## Inferred Architecture

Example:

```text
- The system appears to follow service-layer architecture
- The ingestion flow seems asynchronous
```

The system should NEVER present assumptions as facts.

---

# Generated Outputs

## archify_design.md

Prompt-ready design brief that the user can paste directly into ChatGPT or Gemini for diagram generation.

## .archify/design-packet.json

Grounded internal packet for the Archify skill. Not the main user-facing product.

## .archify/design-brief.md

Human-readable helper brief derived from the same grounded packet.

---

# Future Improvements

## MCP Integration

Potential future architecture:

```text
Skill
    ↓
MCP Server
    ↓
Archify Core Engine
```

## Mermaid Diagram Generation

Potential support for automatic Mermaid diagrams.

## Multi-Language Support

Potential support:
- TypeScript
- Python
- Go
- Java
- Rust

## CI/CD Integration

Potential command:

```bash
npx archify analyze --ci
```

---

# Final Product Vision

Archify should become:

```text
"Grounded architecture understanding for any codebase."
```

The system should help developers:

- Understand unfamiliar repositories
- Generate architecture documentation
- Create system diagrams
- Improve onboarding
- Audit software systems
- Analyze large codebases
