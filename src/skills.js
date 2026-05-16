import fs from "node:fs/promises";
import path from "node:path";

import {
  PROJECT_CLAUDE_SKILL_DIR,
  PROJECT_SKILL_DIR,
  SHARED_GLOBAL_SKILL_DIR,
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
1. The user runs \`npx archify\` once and installs this shared skill globally.
2. After installation, the user invokes this \`archify\` skill instead of manually calling Archify subcommands.
3. This skill handles the internal Archify CLI steps needed to prepare grounding and write \`archify.md\`.

Agent detection:
1. First determine whether the current agent is Codex or Claude Code by inspecting the current agent environment, system instructions, and tool conventions.
2. If the current agent is clearly Codex, follow the Codex workflow below.
3. If the current agent is clearly Claude Code, follow the Claude Code workflow below.
4. If agent detection is unclear, follow the generic fallback workflow and do not assume Codex-specific or Claude-specific subagent behavior.

Codex workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Check whether \`archify.config.json\` exists in the current project before starting analysis.
3. If the project is not initialized yet, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform codex\`.
4. Run project initialization automatically when \`archify.config.json\` is missing so the user does not need to bootstrap the repo manually.
5. Warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Before running \`analyze\`, start one bounded README/context subagent in parallel with the analysis step. That subagent should only read the root \`README.md\` when present, summarize product intent, usage claims, and architectural claims, and mark every conclusion as README-only context rather than confirmed code facts.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. Do not block on the README/context subagent before \`analyze\` finishes.
11. Only proceed after \`analyze\` completes successfully and the required \`.archify/\` artifacts exist. If required artifacts are missing or incomplete, stop and report the missing prerequisite instead of improvising.
12. Ask for permission before starting \`npx archify generate .\`.
13. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
14. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
15. Verify that \`.archify/design-packet.json\` exists after \`generate\`. If \`generate\` fails because artifacts are incomplete, report that and do not continue into synthesis.
16. Read \`.archify/design-packet.json\` first.
17. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
18. After \`generate\`, reconcile the README/context subagent summary with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet. Resolve conflicts in favor of grounded \`.archify\` evidence.
19. Write one root-level file: \`archify.md\`.

Claude Code workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Check whether \`archify.config.json\` exists in the current project before starting analysis.
3. If the project is not initialized yet, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform claude-code\`.
4. Run project initialization automatically when \`archify.config.json\` is missing so the user does not need to bootstrap the repo manually.
5. Warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Read the root \`README.md\` first when it is present so you have product and usage context before synthesis, but treat it as supporting context only.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. Only proceed after \`analyze\` completes successfully and the required \`.archify/\` artifacts exist. If required artifacts are missing or incomplete, stop and report the missing prerequisite instead of improvising.
11. Ask for permission before starting \`npx archify generate .\`.
12. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
13. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
14. Verify that \`.archify/design-packet.json\` exists after \`generate\`. If \`generate\` fails because artifacts are incomplete, report that and do not continue into synthesis.
15. Read \`.archify/design-packet.json\` first.
16. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
17. Reconcile the earlier root README context with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet after \`generate\`.
18. Write one root-level file: \`archify.md\`.

Generic fallback workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Check whether \`archify.config.json\` exists in the current project before starting analysis.
3. If the project is not initialized yet, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform both\`.
4. Run project initialization automatically when \`archify.config.json\` is missing so the user does not need to bootstrap the repo manually.
5. Warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Read the root \`README.md\` when present as supporting context only, but do not start agent-specific subagents or parallel branches when detection is unclear.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. Only proceed after \`analyze\` completes successfully and the required \`.archify/\` artifacts exist. If required artifacts are missing or incomplete, stop and report the missing prerequisite instead of improvising.
11. Ask for permission before starting \`npx archify generate .\`.
12. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
13. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
14. Verify that \`.archify/design-packet.json\` exists after \`generate\`. If \`generate\` fails because artifacts are incomplete, report that and do not continue into synthesis.
15. Read \`.archify/design-packet.json\` first.
16. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
17. Reconcile any README or supporting-document context after \`generate\`, while keeping grounded \`.archify\` evidence as the source of confirmed facts.
18. Write one root-level file: \`archify.md\`.

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
1. The user runs \`npx archify\` once and installs this skill for ${agentName}.
2. After installation, the user invokes this \`archify\` skill instead of manually calling Archify subcommands.
3. This skill handles the internal Archify CLI steps needed to prepare grounding and write \`archify.md\`.

Workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Check whether \`archify.config.json\` exists in the current project before starting analysis.
3. If the project is not initialized yet, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform claude-code\`.
4. Run project initialization automatically when \`archify.config.json\` is missing so the user does not need to bootstrap the repo manually.
5. Warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Read the root \`README.md\` first when it is present so you have product and usage context before synthesis, but treat it as supporting context only.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. Only proceed after \`analyze\` completes successfully and the required \`.archify/\` artifacts exist. If required artifacts are missing or incomplete, stop and report the missing prerequisite instead of improvising.
11. Ask for permission before starting \`npx archify generate .\`.
12. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
13. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
14. Verify that \`.archify/design-packet.json\` exists after \`generate\`. If \`generate\` fails because artifacts are incomplete, report that and do not continue into synthesis.
15. Read \`.archify/design-packet.json\` first.
16. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
17. Reconcile the earlier root README context with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet after \`generate\`.
18. Write one root-level file: \`archify.md\`.

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
- Use additional supporting docs only as optional context, not as a replacement for \`.archify/design-packet.json\` and the referenced artifacts.
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
1. The user runs \`npx archify\` once and installs this skill for ${agentName}.
2. After installation, the user invokes this \`archify\` skill instead of manually calling Archify subcommands.
3. This skill handles the internal Archify CLI steps needed to prepare grounding and write \`archify.md\`.

Workflow:
1. Start by confirming that this skill will handle the full Archify flow itself instead of pushing command execution back to the user.
2. Check whether \`archify.config.json\` exists in the current project before starting analysis.
3. If the project is not initialized yet, ask for permission before starting \`npx archify init --install-mode project --project-path . --platform codex\`.
4. Run project initialization automatically when \`archify.config.json\` is missing so the user does not need to bootstrap the repo manually.
5. Warn that building \`.archify/\` can take time on larger repositories and that silence during the run does not imply failure.
6. Before running \`analyze\`, start one bounded README/context subagent in parallel with the analysis step. That subagent should only read the root \`README.md\` when present, summarize product intent, usage claims, and architectural claims, and mark every conclusion as README-only context rather than confirmed code facts.
7. Ask for permission before starting \`npx archify analyze .\`.
8. Prefer \`npx archify analyze .\` from the repository root. If \`npx\` hangs or is unreliable in a local checkout, fall back to \`node ./bin/archify.js analyze .\`.
9. Tell the user which command is being run, communicate progress while waiting, and poll or wait through long-running work instead of assuming a hang immediately.
10. Do not block on the README/context subagent before \`analyze\` finishes.
11. Only proceed after \`analyze\` completes successfully and the required \`.archify/\` artifacts exist. If required artifacts are missing or incomplete, stop and report the missing prerequisite instead of improvising.
12. Ask for permission before starting \`npx archify generate .\`.
13. Prefer \`npx archify generate .\`. If \`npx\` is unreliable in a local checkout, fall back to \`node ./bin/archify.js generate .\`.
14. Tell the user which command is being run, keep communicating progress during long-running steps, and only proceed after \`generate\` completes successfully.
15. Verify that \`.archify/design-packet.json\` exists after \`generate\`. If \`generate\` fails because artifacts are incomplete, report that and do not continue into synthesis.
16. Read \`.archify/design-packet.json\` first.
17. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
18. After \`generate\`, reconcile the README/context subagent summary with \`supportingDocuments.primaryReadme\` and any \`supportingDocuments.additionalDocs\` listed in the design packet. Resolve conflicts in favor of grounded \`.archify\` evidence.
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
- Use the README/context subagent output only as supporting context and never as a replacement for grounded evidence.
- Use additional supporting docs only as optional context, not as a replacement for \`.archify/design-packet.json\` and the referenced artifacts.
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
    return SHARED_GLOBAL_SKILL_DIR;
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
