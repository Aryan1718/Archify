import fs from "node:fs/promises";
import path from "node:path";

import {
  getSharedGlobalSkillDir,
  PROJECT_CLAUDE_SKILL_DIR,
  PROJECT_SKILL_DIR,
  SHARED_INSTALL_PLATFORM,
  SKILL_TEMPLATE_VERSION
} from "./constants.js";
import { ensureDir } from "./fs-utils.js";

function sharedGlobalSkillTemplate() {
  return `---
name: archify
description: Build a grounded upload-ready architecture prompt pack for the current repository. Use when the user wants repository architecture understanding, a system overview, or a reusable \`archify.md\`.
---

# archify

Version: ${SKILL_TEMPLATE_VERSION}

Use this shared Archify skill when the user wants a grounded upload-ready architecture prompt pack for the current repository.

Triggering:
- Use this skill when the user wants repository architecture understanding, an upload-ready architecture prompt pack, or a grounded \`archify.md\`.
- Do not use this skill for generic code edits, debugging, or non-architecture tasks.

End-user flow:
1. The user runs \`npx archify init\` once in the repository they want to work on, or uses a shared global install if they manage Archify centrally.
2. After installation, the user invokes this \`archify\` skill instead of manually calling Archify subcommands.
3. This skill checks Archify status first, runs only the missing or stale internal steps, and then writes \`archify.md\`.

Agent detection:
1. First determine whether the current agent is Codex or Claude Code by inspecting the current agent environment, system instructions, and tool conventions.
2. If the current agent is clearly Codex, follow the Codex workflow below.
3. If the current agent is clearly Claude Code, follow the Claude Code workflow below.
4. If agent detection is unclear, follow the generic fallback workflow and do not assume Codex-specific or Claude-specific subagent behavior.

Codex workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Start by checking \`npx archify status\` so you can decide whether to initialize, analyze, generate, or reuse existing artifacts.
3. If setup is missing, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform codex\`.
4. After initialization, run \`npx archify status\` again before deciding the next step.
5. If repository knowledge is missing or stale, warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Before running \`analyze\`, start one bounded README/context pass in parallel with the analysis step. That pass should read the root \`README.md\` when present plus a small set of similar top-level docs such as \`readme.md\`, \`docs/architecture.md\`, \`architecture.md\`, or \`docs/overview.md\` when they exist, summarize product intent, usage claims, and architectural claims, and mark every conclusion as supporting-doc context rather than confirmed code facts.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. Do not block on the README/context pass before \`analyze\` finishes.
11. After \`analyze\` completes, run \`npx archify status\` again and only continue if knowledge is now ready.
12. If the design packet is missing or stale, ask for permission before starting \`npx archify generate .\`.
13. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
14. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
15. After \`generate\`, run \`npx archify status\` again and only continue if the design packet is ready and not stale.
16. If status already says the knowledge and design packet are fresh, reuse them and do not rerun \`analyze\` or \`generate\`.
17. Read \`.archify/design-packet.json\` first.
18. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
19. After \`generate\` or reuse, reconcile the README/context pass summary with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet. Resolve conflicts in favor of grounded \`.archify\` evidence.
20. Write one root-level file: \`archify.md\`.

Claude Code workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Start by checking \`npx archify status\` so you can decide whether to initialize, analyze, generate, or reuse existing artifacts.
3. If setup is missing, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform claude-code\`.
4. After initialization, run \`npx archify status\` again before deciding the next step.
5. If repository knowledge is missing or stale, warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Before running \`analyze\`, read the root \`README.md\` when present plus a small set of similar top-level docs such as \`readme.md\`, \`docs/architecture.md\`, \`architecture.md\`, or \`docs/overview.md\` in parallel with the analysis step, but treat them as supporting context only.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. After \`analyze\` completes, run \`npx archify status\` again and only continue if knowledge is now ready.
11. If the design packet is missing or stale, ask for permission before starting \`npx archify generate .\`.
12. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
13. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
14. After \`generate\`, run \`npx archify status\` again and only continue if the design packet is ready and not stale.
15. If status already says the knowledge and design packet are fresh, reuse them and do not rerun \`analyze\` or \`generate\`.
16. Read \`.archify/design-packet.json\` first.
17. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
18. Reconcile the earlier supporting-doc context with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet after \`generate\` or reuse.
19. Write one root-level file: \`archify.md\`.

Generic fallback workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Start by checking \`npx archify status\` so you can decide whether to initialize, analyze, generate, or reuse existing artifacts.
3. If setup is missing, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform both\`.
4. After initialization, run \`npx archify status\` again before deciding the next step.
5. If repository knowledge is missing or stale, warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Before running \`analyze\`, read the root \`README.md\` when present plus a small set of similar top-level docs such as \`readme.md\`, \`docs/architecture.md\`, \`architecture.md\`, or \`docs/overview.md\` in parallel with the analysis step, but treat them as supporting context only and do not start agent-specific subagents when detection is unclear.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. After \`analyze\` completes, run \`npx archify status\` again and only continue if knowledge is now ready.
11. If the design packet is missing or stale, ask for permission before starting \`npx archify generate .\`.
12. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
13. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
14. After \`generate\`, run \`npx archify status\` again and only continue if the design packet is ready and not stale.
15. If status already says the knowledge and design packet are fresh, reuse them and do not rerun \`analyze\` or \`generate\`.
16. Read \`.archify/design-packet.json\` first.
17. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
18. Reconcile any README or supporting-document context gathered in parallel after \`generate\` or reuse, while keeping grounded \`.archify\` evidence as the source of confirmed facts.
19. Write one root-level file: \`archify.md\`.

Writing rules:
- Always start from \`.archify/design-packet.json\`.
- Make \`archify.md\` an upload-ready architecture prompt artifact for AI apps such as ChatGPT or Claude.
- Include explicit \`System Prompt\`, \`User Prompt\`, \`Grounded Repository Context\`, \`Questions Before Architecture Generation\`, and \`Diagram / Image Generation Instructions\` sections.
- Keep \`Confirmed From Codebase\`, \`Inferred Architecture\`, README-only or supporting claims, and \`Open Questions / Uncertainty\` separate.
- Ask the listed questionnaire before finalizing architecture, diagrams, boundaries, naming, deliverable type, or visual style.
- Make the first response ask which architecture artifact the user wants, offer high-level architecture, low-level architecture, component breakdown, user flow diagram, sequence or interaction view, and a custom option.
- Ask how the architecture should look visually before generating visuals, offer diagram or image style choices plus a custom option, and wait for the user's answers before generating the final result.
- If the AI app supports image generation, generate the requested architecture image or diagram. If it does not, return a render-ready diagram prompt or specification instead.
- Treat \`.archify\` artifacts as the primary source of confirmed facts.
- Treat README or other docs as supporting context only.
- When analysis is needed and the agent supports it, gather the README and a small set of similar top-level docs in parallel with \`analyze\` to pick up product context sooner.
- Always check \`npx archify status\` before deciding whether to initialize, analyze, generate, or reuse existing artifacts.
- If setup is missing, initialize. If knowledge is missing or stale, analyze. If the design packet is missing or stale, generate. If everything is fresh, reuse it.
- If \`archify.config.json\` is missing, initialize the current project automatically before analysis instead of asking the user to run \`archify init\` manually.
- Do not let README-only claims override grounded evidence unless you mark them as inferred or uncertain.
- Do not present inferred items as confirmed facts.
- Do not ask the user to manually run \`init\`, \`analyze\`, or \`generate\`; this skill should handle those internal steps.
- Do not create \`archify_design.md\`, \`architecture.md\`, or \`design.md\` as the primary output.
- If \`archify.md\` already exists, ask for permission before overwriting it.
`;
}

function projectSkillTemplate(platform) {
  const agentName = platform === "claude-code" ? "Claude Code" : "Codex";
  if (platform === "claude-code") {
    return `---
name: archify
description: Build a grounded upload-ready architecture prompt pack for the current repository. Use when the user wants repository architecture understanding, a system overview, or a reusable \`archify.md\`.
---

# archify

Version: ${SKILL_TEMPLATE_VERSION}

Use this skill when the user wants a grounded upload-ready architecture prompt pack for the current repository in ${agentName}.

Triggering:
- Use this skill when the user wants repository architecture understanding, an upload-ready architecture prompt pack, or a grounded \`archify.md\`.
- Do not use this skill for generic code edits, debugging, or non-architecture tasks.

End-user flow:
1. The user runs \`npx archify init\` once in this repository and installs this skill for ${agentName}.
2. After installation, the user invokes this \`archify\` skill instead of manually calling Archify subcommands.
3. This skill checks Archify status first, runs only the missing or stale internal steps, and then writes \`archify.md\`.

Workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Start by checking \`npx archify status\` so you can decide whether to initialize, analyze, generate, or reuse existing artifacts.
3. If setup is missing, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform claude-code\`.
4. After initialization, run \`npx archify status\` again before deciding the next step.
5. If repository knowledge is missing or stale, warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Before running \`analyze\`, read the root \`README.md\` when present plus a small set of similar top-level docs such as \`readme.md\`, \`docs/architecture.md\`, \`architecture.md\`, or \`docs/overview.md\` in parallel with the analysis step, but treat them as supporting context only.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. After \`analyze\` completes, run \`npx archify status\` again and only continue if knowledge is now ready.
11. If the design packet is missing or stale, ask for permission before starting \`npx archify generate .\`.
12. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
13. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
14. After \`generate\`, run \`npx archify status\` again and only continue if the design packet is ready and not stale.
15. If status already says the knowledge and design packet are fresh, reuse them and do not rerun \`analyze\` or \`generate\`.
16. Read \`.archify/design-packet.json\` first.
17. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
18. Reconcile the earlier supporting-doc context with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet after \`generate\` or reuse.
19. Write one root-level file: \`archify.md\`.

Writing rules:
- Always start from \`.archify/design-packet.json\`.
- Make \`archify.md\` an upload-ready architecture prompt artifact for AI apps such as ChatGPT or Claude.
- Include explicit \`System Prompt\`, \`User Prompt\`, \`Grounded Repository Context\`, \`Questions Before Architecture Generation\`, and \`Diagram / Image Generation Instructions\` sections.
- Keep \`Confirmed From Codebase\`, \`Inferred Architecture\`, README-only or supporting claims, and \`Open Questions / Uncertainty\` separate.
- Ask the listed questionnaire before finalizing architecture, diagrams, boundaries, naming, deliverable type, or visual style.
- Make the first response ask which architecture artifact the user wants, offer high-level architecture, low-level architecture, component breakdown, user flow diagram, sequence or interaction view, and a custom option.
- Ask how the architecture should look visually before generating visuals, offer diagram or image style choices plus a custom option, and wait for the user's answers before generating the final result.
- If the AI app supports image generation, generate the requested architecture image or diagram. If it does not, return a render-ready diagram prompt or specification instead.
- Treat \`.archify\` artifacts as the primary source of confirmed facts.
- Treat README or other docs as supporting context only.
- Use the root README as supporting context when present, and skip it cleanly when it is absent.
- When analysis is needed and the agent supports parallel work, gather the README and a small set of similar top-level docs in parallel with \`analyze\`.
- Use additional supporting docs only as optional context, not as a replacement for \`.archify/design-packet.json\` and the referenced artifacts.
- Always check \`npx archify status\` before deciding whether to initialize, analyze, generate, or reuse existing artifacts.
- If setup is missing, initialize. If knowledge is missing or stale, analyze. If the design packet is missing or stale, generate. If everything is fresh, reuse it.
- If \`archify.config.json\` is missing, initialize the current project automatically before analysis instead of asking the user to run \`archify init\` manually.
- Do not let README-only claims override grounded evidence unless you mark them as inferred or uncertain.
- Do not present inferred items as confirmed facts.
- Do not ask the user to manually run \`init\`, \`analyze\`, or \`generate\`; this skill should handle those internal steps.
- Do not create \`archify_design.md\`, \`architecture.md\`, or \`design.md\` as the primary output.
- If \`archify.md\` already exists, ask for permission before overwriting it.
`;
  }

  return `---
name: archify
description: Build a grounded upload-ready architecture prompt pack for the current repository. Use when the user wants repository architecture understanding, a system overview, or a reusable \`archify.md\`.
---

# archify

Version: ${SKILL_TEMPLATE_VERSION}

Use this skill when the user wants a grounded upload-ready architecture prompt pack for the current repository in ${agentName}.

Triggering:
- Use this skill when the user wants repository architecture understanding, an upload-ready architecture prompt pack, or a grounded \`archify.md\`.
- Do not use this skill for generic code edits, debugging, or non-architecture tasks.

End-user flow:
1. The user runs \`npx archify init\` once in this repository and installs this skill for ${agentName}.
2. After installation, the user invokes this \`archify\` skill instead of manually calling Archify subcommands.
3. This skill checks Archify status first, runs only the missing or stale internal steps, and then writes \`archify.md\`.

Workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Start by checking \`npx archify status\` so you can decide whether to initialize, analyze, generate, or reuse existing artifacts.
3. If setup is missing, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform codex\`.
4. After initialization, run \`npx archify status\` again before deciding the next step.
5. If repository knowledge is missing or stale, warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Before running \`analyze\`, start one bounded README/context pass in parallel with the analysis step. That pass should read the root \`README.md\` when present plus a small set of similar top-level docs such as \`readme.md\`, \`docs/architecture.md\`, \`architecture.md\`, or \`docs/overview.md\` when they exist, summarize product intent, usage claims, and architectural claims, and mark every conclusion as supporting-doc context rather than confirmed code facts.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. Do not block on the README/context pass before \`analyze\` finishes.
11. After \`analyze\` completes, run \`npx archify status\` again and only continue if knowledge is now ready.
12. If the design packet is missing or stale, ask for permission before starting \`npx archify generate .\`.
13. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
14. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
15. After \`generate\`, run \`npx archify status\` again and only continue if the design packet is ready and not stale.
16. If status already says the knowledge and design packet are fresh, reuse them and do not rerun \`analyze\` or \`generate\`.
17. Read \`.archify/design-packet.json\` first.
18. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
19. After \`generate\` or reuse, reconcile the README/context pass summary with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet. Resolve conflicts in favor of grounded \`.archify\` evidence.
20. Write one root-level file: \`archify.md\`.

Writing rules:
- Always start from \`.archify/design-packet.json\`.
- Make \`archify.md\` an upload-ready architecture prompt artifact for AI apps such as ChatGPT or Claude.
- Include explicit \`System Prompt\`, \`User Prompt\`, \`Grounded Repository Context\`, \`Questions Before Architecture Generation\`, and \`Diagram / Image Generation Instructions\` sections.
- Keep \`Confirmed From Codebase\`, \`Inferred Architecture\`, README-only or supporting claims, and \`Open Questions / Uncertainty\` separate.
- Ask the listed questionnaire before finalizing architecture, diagrams, boundaries, naming, deliverable type, or visual style.
- Make the first response ask which architecture artifact the user wants, offer high-level architecture, low-level architecture, component breakdown, user flow diagram, sequence or interaction view, and a custom option.
- Ask how the architecture should look visually before generating visuals, offer diagram or image style choices plus a custom option, and wait for the user's answers before generating the final result.
- If the AI app supports image generation, generate the requested architecture image or diagram. If it does not, return a render-ready diagram prompt or specification instead.
- Treat \`.archify\` artifacts as the primary source of confirmed facts.
- Treat README or other docs as supporting context only.
- Use the README/context pass output only as supporting context and never as a replacement for grounded evidence.
- When analysis is needed and the agent supports parallel work, gather the README and a small set of similar top-level docs in parallel with \`analyze\`.
- Use additional supporting docs only as optional context, not as a replacement for \`.archify/design-packet.json\` and the referenced artifacts.
- Always check \`npx archify status\` before deciding whether to initialize, analyze, generate, or reuse existing artifacts.
- If setup is missing, initialize. If knowledge is missing or stale, analyze. If the design packet is missing or stale, generate. If everything is fresh, reuse it.
- If \`archify.config.json\` is missing, initialize the current project automatically before analysis instead of asking the user to run \`archify init\` manually.
- Do not let README-only claims override grounded evidence unless you mark them as inferred or uncertain.
- Do not present inferred items as confirmed facts.
- Do not ask the user to manually run \`init\`, \`analyze\`, or \`generate\`; this skill should handle those internal steps.
- Do not create \`archify_design.md\`, \`architecture.md\`, or \`design.md\` as the primary output.
- If \`archify.md\` already exists, ask for permission before overwriting it.
`;
}

function resolveTargetDir({ repoRoot, installMode, platform }) {
  if (installMode === "global") {
    return getSharedGlobalSkillDir();
  }

  return platform === "claude-code"
    ? path.join(repoRoot, PROJECT_CLAUDE_SKILL_DIR)
    : path.join(repoRoot, PROJECT_SKILL_DIR);
}

export async function installSkillTemplates(repoRoot, { installMode, platforms }) {
  const targets = [];
  const requestedPlatforms = installMode === "global" ? [SHARED_INSTALL_PLATFORM] : platforms;

  for (const platform of requestedPlatforms) {
    const targetDir = resolveTargetDir({ repoRoot, installMode, platform });
    await ensureDir(targetDir);

    const skillPath = path.join(targetDir, "SKILL.md");
    const template = installMode === "global"
      ? sharedGlobalSkillTemplate()
      : projectSkillTemplate(platform);
    await fs.writeFile(skillPath, template, "utf8");
    targets.push({
      platform,
      targetDir,
      skillPath
    });
  }

  return targets;
}
