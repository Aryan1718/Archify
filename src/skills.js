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

const SUPPORTED_DOCS = [
  "`archify` -> `archify.md`",
  "`tech_stack` -> `TECH_STACK.md`",
  "`api_design` -> `API_DESIGN.md`",
  "`data_model` -> `DATA_MODEL.md`",
  "`conventions` -> `CONVENTIONS.md`",
  "`glossary` -> `GLOSSARY.md`",
  "`flows` -> `FLOWS.md`",
  "`test_cases` -> `TEST_CASES.md`"
].join("\n- ");

function buildTemplate({ agentName, platform, shared }) {
  const initPlatform = shared ? "both" : platform;
  return `---
name: archify
description: Build grounded repository architecture documents for the current repository. Defaults to \`archify.md\`, and also supports the other Archify doc types through \`--doc-type\`.
---

# archify

Version: ${SKILL_TEMPLATE_VERSION}

Use this skill when the user wants grounded repository architecture documentation in ${agentName}.

Supported documents:
- ${SUPPORTED_DOCS}

Workflow:
1. Default to doc type \`archify\` when the user simply says to use Archify on the repo.
2. If the user clearly asks for another supported document, select that doc type and use \`--doc-type <type>\` on \`status\`, \`generate\`, and \`write\`.
3. Start by checking \`npx archify-cli status --doc-type <type>\`.
4. If setup is missing, ask for permission before starting \`npx archify-cli init --install-mode ${shared ? "global" : "project"}${shared ? "" : " --project-path ."} --platform ${initPlatform}\`.
5. If repository knowledge is missing or stale, ask for permission before starting \`npx archify-cli analyze .\`.
6. If the synthesis packet is missing or stale for the selected doc type, ask for permission before starting \`npx archify-cli generate . --doc-type <type>\`.
7. After \`generate\`, run \`npx archify-cli status --doc-type <type>\` again and only continue if the synthesis packet is ready and not stale.
8. Read \`.archify/docs/<type>/packet.json\` first.
9. Read \`.archify/docs/<type>/guide.json\` second and follow its read order, section plan, fact policy, and validation checks before inspecting anything else.
10. Read the referenced \`.archify/\` artifacts next. These are the mandatory primary grounding.
11. Write one root-level file matching the selected doc type only.

Rules:
- \`archify\` remains the default doc type for existing workflows.
- Treat \`.archify\` artifacts as the primary source of confirmed facts.
- Keep confirmed findings, inferred notes, and open questions separate.
- If evidence is weak, say that repository evidence is limited instead of guessing.
- Do not write a different output file than the one mapped to the selected doc type.
- If the selected output file already exists, ask for permission before overwriting it.
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
    const template = buildTemplate({
      agentName: installMode === "global" ? "shared agents" : (platform === "claude-code" ? "Claude Code" : "Codex"),
      platform,
      shared: installMode === "global"
    });
    await fs.writeFile(skillPath, template, "utf8");
    targets.push({
      platform,
      targetDir,
      skillPath
    });
  }

  return targets;
}

