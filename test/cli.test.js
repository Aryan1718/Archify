import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

const repoRoot = path.resolve(process.cwd());
const cliPath = path.join(repoRoot, "bin", "archify.js");
const tempDirs = [];

async function makeWorkspace() {
  const workspace = await fs.mkdtemp(path.join(os.tmpdir(), "archify-phase0-"));
  tempDirs.push(workspace);
  return workspace;
}

function runCli(args, { cwd, env } = {}) {
  return spawnSync("node", [cliPath, ...args], {
    cwd,
    env: { ...process.env, ...env },
    encoding: "utf8"
  });
}

function runInit({
  cwd,
  env,
  installMode = "project",
  platform,
  projectPath,
  command = "init"
} = {}) {
  const args = command === "bare" ? [] : [command];
  args.push("--install-mode", installMode);
  const resolvedPlatform = platform ?? (installMode === "project" ? "both" : undefined);
  if (resolvedPlatform) {
    args.push("--platform", resolvedPlatform);
  }
  if (projectPath) {
    args.push("--project-path", projectPath);
  }
  return runCli(args, { cwd, env });
}

function parseStdoutJson(result) {
  return JSON.parse(result.stdout);
}

async function readJson(filePath) {
  const raw = await fs.readFile(filePath, "utf8");
  return JSON.parse(raw);
}

afterEach(async () => {
  await Promise.all(tempDirs.splice(0).map((dir) => fs.rm(dir, { recursive: true, force: true })));
});

test("bare archify runs setup for the current project and installs both Codex and Claude Code skills", async () => {
  const cwd = await makeWorkspace();

  const result = runInit({ cwd, command: "bare", projectPath: "." });
  assert.equal(result.status, 0, result.stderr);

  const config = await readJson(path.join(cwd, "archify.config.json"));
  const resolvedCwd = await fs.realpath(cwd);
  assert.equal(config.skillInstall.mode, "project");
  assert.equal(config.skillInstall.platform, "codex");
  assert.deepEqual(config.skillInstall.platforms, ["codex", "claude-code"]);
  assert.equal(config.skillInstall.version, 1);
  assert.deepEqual(config.skillInstall.target, config.skillInstall.targets[0]);
  assert.deepEqual(config.skillInstall.targets, [
    {
      platform: "codex",
      path: path.join(resolvedCwd, ".agents", "skills", "archify"),
      projectRoot: resolvedCwd
    },
    {
      platform: "claude-code",
      path: path.join(resolvedCwd, ".claude", "skills", "archify"),
      projectRoot: resolvedCwd
    }
  ]);

  const ignore = await fs.readFile(path.join(cwd, ".archifyignore"), "utf8");
  assert.match(ignore, /\.archify\//);

  const codexSkill = await fs.readFile(path.join(cwd, ".agents", "skills", "archify", "SKILL.md"), "utf8");
  assert.match(codexSkill, /^---\nname: archify\ndescription:/);
  assert.match(codexSkill, /Build grounded repository architecture documents/i);
  assert.match(codexSkill, /If setup is missing, ask for permission before starting `npx archify-cli init --install-mode project --project-path \. --platform codex`/i);
  assert.match(codexSkill, /Default to doc type `archify` when the user simply says to use Archify on the repo/i);
  assert.match(codexSkill, /Write one root-level file matching the selected doc type only/i);
  assert.match(codexSkill, /Start by checking `npx archify-cli status --doc-type <type>`/i);
  assert.match(codexSkill, /Defaults to `archify\.md`, and also supports the other Archify doc types through `--doc-type`/i);
  assert.match(codexSkill, /Ask for permission before starting `npx archify-cli analyze \.`/i);
  assert.match(codexSkill, /Treat `\.archify` artifacts as the primary source of confirmed facts/i);
  assert.match(codexSkill, /Keep confirmed findings, inferred notes, and open questions separate/i);
  assert.match(codexSkill, /If the synthesis packet is missing or stale for the selected doc type/i);
  assert.match(codexSkill, /Write one root-level file matching the selected doc type only/i);
  assert.match(codexSkill, /status --doc-type <type>/i);
  assert.match(codexSkill, /generate \. --doc-type <type>/i);
  assert.match(codexSkill, /Read `\.archify\/docs\/<type>\/packet\.json` first/i);
  assert.match(codexSkill, /Read `\.archify\/docs\/<type>\/guide\.json` second/i);
  assert.match(codexSkill, /tech_stack` -> `TECH_STACK\.md/i);
  assert.match(codexSkill, /api_design` -> `API_DESIGN\.md/i);
  assert.match(codexSkill, /If evidence is weak, say that repository evidence is limited instead of guessing/i);

  const claudeSkill = await fs.readFile(path.join(cwd, ".claude", "skills", "archify", "SKILL.md"), "utf8");
  assert.match(claudeSkill, /^---\nname: archify\ndescription:/);
  assert.match(claudeSkill, /Claude Code/i);
  assert.match(claudeSkill, /If setup is missing, ask for permission before starting `npx archify-cli init --install-mode project --project-path \. --platform claude-code`/i);
  assert.match(claudeSkill, /Default to doc type `archify` when the user simply says to use Archify on the repo/i);
  assert.match(claudeSkill, /Write one root-level file matching the selected doc type only/i);
  assert.match(claudeSkill, /Start by checking `npx archify-cli status --doc-type <type>`/i);
  assert.match(claudeSkill, /Defaults to `archify\.md`, and also supports the other Archify doc types through `--doc-type`/i);
  assert.match(claudeSkill, /Ask for permission before starting `npx archify-cli analyze \.`/i);
  assert.match(claudeSkill, /Treat `\.archify` artifacts as the primary source of confirmed facts/i);
  assert.match(claudeSkill, /Keep confirmed findings, inferred notes, and open questions separate/i);
  assert.match(claudeSkill, /Read `\.archify\/docs\/<type>\/packet\.json` first/i);
  assert.match(claudeSkill, /Read `\.archify\/docs\/<type>\/guide\.json` second/i);
  assert.match(claudeSkill, /glossary` -> `GLOSSARY\.md/i);
  assert.match(claudeSkill, /Treat `\.archify` artifacts as the primary source of confirmed facts/i);
  assert.match(claudeSkill, /If the selected output file already exists, ask for permission before overwriting it/i);
  assert.doesNotMatch(claudeSkill, /README\/context subagent/i);
});

test("init supports shared global install mode and is idempotent", async () => {
  const cwd = await makeWorkspace();
  const fakeHome = await makeWorkspace();

  let result = runInit({
    cwd,
    installMode: "global",
    env: { HOME: fakeHome }
  });
  assert.equal(result.status, 0, result.stderr);

  result = runInit({
    cwd,
    installMode: "global",
    env: { HOME: fakeHome }
  });
  assert.equal(result.status, 0, result.stderr);

  const config = await readJson(path.join(cwd, "archify.config.json"));
  const resolvedCwd = await fs.realpath(cwd);
  assert.equal(config.skillInstall.mode, "global");
  assert.equal(config.skillInstall.platform, "shared");
  assert.deepEqual(config.skillInstall.platforms, ["codex", "claude-code"]);
  assert.deepEqual(config.skillInstall.target, config.skillInstall.targets[0]);
  assert.deepEqual(config.skillInstall.target, {
    platform: "shared",
    path: path.join(fakeHome, ".agents", "skills", "archify"),
    projectRoot: resolvedCwd
  });
  assert.deepEqual(config.skillInstall.targets, [config.skillInstall.target]);

  const sharedSkill = await fs.readFile(path.join(fakeHome, ".agents", "skills", "archify", "SKILL.md"), "utf8");
  assert.match(sharedSkill, /^---\nname: archify\ndescription:/);
  assert.match(sharedSkill, /supports the other Archify doc types through `--doc-type`/i);
  assert.match(sharedSkill, /status --doc-type <type>/i);
  assert.match(sharedSkill, /Read `\.archify\/docs\/<type>\/packet\.json` first/i);
  assert.match(sharedSkill, /Read `\.archify\/docs\/<type>\/guide\.json` second/i);
  assert.match(sharedSkill, /test_cases` -> `TEST_CASES\.md/i);
  assert.ok(!(await fs.access(path.join(fakeHome, ".claude", "skills", "archify", "SKILL.md")).then(() => true).catch(() => false)));
});

test("init supports installing into another project path for the selected platform", async () => {
  const launcher = await makeWorkspace();
  const targetProject = await makeWorkspace();

  const result = runInit({
    cwd: launcher,
    installMode: "project",
    platform: "claude-code",
    projectPath: targetProject
  });
  assert.equal(result.status, 0, result.stderr);

  const config = await readJson(path.join(targetProject, "archify.config.json"));
  assert.equal(config.skillInstall.mode, "project");
  assert.equal(config.skillInstall.platform, "claude-code");
  assert.deepEqual(config.skillInstall.platforms, ["claude-code"]);
  assert.equal(config.skillInstall.target.platform, "claude-code");
  assert.equal(await fs.realpath(config.skillInstall.target.projectRoot), await fs.realpath(targetProject));
  assert.equal(await fs.realpath(config.skillInstall.target.path), await fs.realpath(path.join(targetProject, ".claude", "skills", "archify")));
  await fs.access(path.join(targetProject, ".archifyignore"));
  await fs.access(path.join(targetProject, ".claude", "skills", "archify", "SKILL.md"));
  const installedClaudeSkill = await fs.readFile(path.join(targetProject, ".claude", "skills", "archify", "SKILL.md"), "utf8");
  assert.match(installedClaudeSkill, /Start by checking `npx archify-cli status --doc-type <type>`/i);
  assert.match(installedClaudeSkill, /If setup is missing, ask for permission before starting `npx archify-cli init --install-mode project --project-path \. --platform claude-code`/i);
  assert.ok(!(await fs.access(path.join(targetProject, ".agents", "skills", "archify", "SKILL.md")).then(() => true).catch(() => false)));
  assert.ok(!(await fs.access(path.join(launcher, "archify.config.json")).then(() => true).catch(() => false)));
});

test("setup fails clearly in non-interactive mode when required flags are missing or invalid", async () => {
  const cwd = await makeWorkspace();
  const fakeHome = await makeWorkspace();
  const globalEnv = { HOME: fakeHome };

  let result = runCli([], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /INSTALL_MODE_REQUIRED/);

  result = runCli(["--install-mode", "global"], { cwd, env: globalEnv });
  assert.equal(result.status, 0, result.stderr);

  result = runCli(["--install-mode", "global", "--project-path", "."], { cwd, env: globalEnv });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /PROJECT_PATH_UNEXPECTED/);

  result = runCli(["--install-mode", "global", "--platform", "codex"], { cwd, env: globalEnv });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /PLATFORM_UNEXPECTED/);

  result = runCli(["--install-mode", "project"], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /PROJECT_PATH_REQUIRED/);

  result = runCli(["--install-mode", "project", "--project-path", "."], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /PLATFORM_REQUIRED/);

  result = runCli(["init", "--install-mode", "project", "--platform", "codex", "--project-path", "missing-dir"], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /PROJECT_PATH_MISSING/);
});

test("analyze validates config, target path, and writes Phase 1 scan artifacts", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src", "routes"), { recursive: true });
  await fs.mkdir(path.join(cwd, "docs"), { recursive: true });
  await fs.mkdir(path.join(cwd, "migrations"), { recursive: true });
  await fs.mkdir(path.join(cwd, "scripts"), { recursive: true });
  await fs.mkdir(path.join(cwd, "tests"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "main.py"), "print('boot')\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "routes", "api.ts"), "export const route = true;\n", "utf8");
  await fs.writeFile(path.join(cwd, "docs", "architecture.md"), "# Architecture\n", "utf8");
  await fs.writeFile(path.join(cwd, "migrations", "20260513_init.sql"), "create table users();\n", "utf8");
  await fs.writeFile(path.join(cwd, "Dockerfile"), "FROM node:20\n", "utf8");
  await fs.writeFile(path.join(cwd, "package.json"), JSON.stringify({ name: "fixture" }), "utf8");
  await fs.writeFile(path.join(cwd, "tests", "app.test.js"), "test('x', () => {});\n", "utf8");
  await fs.writeFile(path.join(cwd, "scripts", "release"), "#!/usr/bin/env bash\necho ok\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  const result = runCli(["analyze", "."], { cwd });
  assert.equal(result.status, 0, result.stderr);
  const parsedResult = parseStdoutJson(result);
  assert.equal(parsedResult.command, "analyze");
  assert.equal(parsedResult.result.phase, "analyze");
  assert.equal(parsedResult.result.totals.files, 8);
  assert.equal(parsedResult.result.extractedFileCount, 5);
  assert.ok(parsedResult.result.nodeCount > 0);
  assert.ok(parsedResult.result.edgeCount > 0);
  assert.match(parsedResult.result.note, /Phase 6 structured architecture artifacts/);

  const facts = await readJson(path.join(cwd, ".archify", "facts.json"));
  assert.equal(facts.status, "ready");
  assert.equal(facts.phase, "analyze");
  assert.equal(facts.totals.files, 8);
  assert.equal(facts.totals.byFileType.code, 5);
  assert.equal(facts.totals.byFileType.document, 1);
  assert.equal(facts.totals.byFileType.config, 2);
  assert.equal(facts.totals.byArchitectureTag.entrypoint, 2);
  assert.equal(facts.totals.byArchitectureTag.route, 1);
  assert.equal(facts.totals.byArchitectureTag.database, 1);
  assert.equal(facts.totals.byArchitectureTag.migration, 1);
  assert.equal(facts.totals.byArchitectureTag.docs, 1);
  assert.equal(facts.totals.byArchitectureTag.infra, 1);
  assert.equal(facts.totals.byArchitectureTag.dependency_manifest, 1);
  assert.equal(facts.totals.byArchitectureTag.test, 1);
  assert.deepEqual(facts.extractionCandidates, [
    "migrations/20260513_init.sql",
    "scripts/release",
    "src/main.py",
    "src/routes/api.ts",
    "tests/app.test.js"
  ]);
  assert.ok(Array.isArray(facts.confirmedFindings));
  assert.ok(Array.isArray(facts.inferredFindings));
  assert.ok(facts.confirmedFindings.length >= 1);
  assert.ok(facts.confirmedFindings.every((item) => Array.isArray(item.evidence) && item.evidence.length >= 1));

  const releaseScript = facts.inventory.find((item) => item.path === "scripts/release");
  assert.equal(releaseScript.fileType, "code");
  assert.equal(releaseScript.detectionReason, "shebang");
  assert.deepEqual(releaseScript.architectureTags, ["entrypoint"]);

  const routeFile = facts.inventory.find((item) => item.path === "src/routes/api.ts");
  assert.deepEqual(routeFile.architectureTags, ["route"]);

  const manifest = await readJson(path.join(cwd, ".archify", "manifest.json"));
  assert.equal(manifest.status, "ready");
  assert.equal(manifest.phase, "analyze");
  assert.ok(manifest.files["src/main.py"].hash);
  assert.equal(manifest.files["src/routes/api.ts"].fileType, "code");
  assert.equal(manifest.files["src/main.py"].extraction.language, "python");
  assert.equal(manifest.files["src/routes/api.ts"].extraction.language, "typescript");
  assert.ok(manifest.graphSummary.communityCount >= 1);
  assert.ok(manifest.analysisSummary.godNodeCount >= 0);

  const graph = await readJson(path.join(cwd, ".archify", "graph.json"));
  assert.equal(graph.status, "ready");
  assert.equal(graph.phase, "analyze");
  assert.ok(graph.summary.nodeCount > 0);
  assert.ok(graph.summary.edgeCount > 0);
  assert.ok(graph.summary.communityCount >= 1);
  assert.ok(Array.isArray(graph.analysis.godNodes));
  assert.ok(graph.nodes.some((node) => node.label === "src/main.py"));
  assert.ok(graph.nodes.every((node) => Object.hasOwn(node, "community")));
  assert.ok(typeof graph.communities === "object");
  assert.ok(graph.edges.length >= 0);

  const report = await fs.readFile(path.join(cwd, ".archify", "GRAPH_REPORT.md"), "utf8");
  assert.match(report, /## God Nodes/);
  assert.match(report, /## Suggested Questions/);

  const modules = await readJson(path.join(cwd, ".archify", "modules.json"));
  assert.equal(modules.status, "ready");
  assert.ok(modules.modules.length >= 1);
  assert.ok(modules.modules.every((item) => item.evidence.length >= 1));

  const routes = await readJson(path.join(cwd, ".archify", "routes.json"));
  assert.equal(routes.status, "ready");
  assert.ok(Array.isArray(routes.confirmedRoutes));
  assert.ok(Array.isArray(routes.inferredRoutes));

  const database = await readJson(path.join(cwd, ".archify", "database.json"));
  assert.equal(database.status, "ready");
  assert.ok(database.summary.tableCount >= 1);
  assert.ok(database.migrations.length >= 1);

  const services = await readJson(path.join(cwd, ".archify", "services.json"));
  assert.equal(services.status, "ready");
  assert.ok(services.services.length >= 1);

  const dependencies = await readJson(path.join(cwd, ".archify", "dependencies.json"));
  assert.equal(dependencies.status, "ready");
  assert.ok(Array.isArray(dependencies.internalDependencies));
  assert.ok(Array.isArray(dependencies.externalDependencies));

  const docsSummary = await readJson(path.join(cwd, ".archify", "docs-summary.json"));
  assert.equal(docsSummary.status, "ready");
  assert.equal(docsSummary.summary.detectedDocumentCount, 1);
  assert.equal(docsSummary.summary.processedDocumentCount, 0);
  assert.ok(docsSummary.detectedDocs.some((item) => item.path === "docs/architecture.md"));
  assert.deepEqual(docsSummary.confirmedFacts.readmeLikeDocs, []);
});

test("generate fails clearly when required artifacts are incomplete", async () => {
  const cwd = await makeWorkspace();
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  const analyze = runCli(["analyze", "."], { cwd });
  assert.equal(analyze.status, 0, analyze.stderr);

  const docsSummaryPath = path.join(cwd, ".archify", "docs-summary.json");
  const docsSummary = await readJson(docsSummaryPath);
  docsSummary.status = "placeholder";
  await fs.writeFile(docsSummaryPath, `${JSON.stringify(docsSummary, null, 2)}\n`, "utf8");

  const result = runCli(["generate", "."], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /GENERATE_PREREQS_MISSING/);
});

test("generate writes doc-scoped synthesis artifacts from grounded .archify artifacts", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src", "routes"), { recursive: true });
  await fs.mkdir(path.join(cwd, "docs"), { recursive: true });
  await fs.writeFile(path.join(cwd, "README.md"), "# Fixture\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "app.py"), "def run():\n    return 1\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "routes", "api.ts"), "export function handler() { return 1; }\n", "utf8");
  await fs.writeFile(path.join(cwd, "docs", "architecture.md"), "# Architecture\n\nThe runtime starts in `src/app.py`.\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  const analyze = runCli(["analyze", "."], { cwd });
  assert.equal(analyze.status, 0, analyze.stderr);

  const result = runCli(["generate", "."], { cwd });
  assert.equal(result.status, 0, result.stderr);
  const parsed = parseStdoutJson(result);
  assert.match(parsed.result.note, /Synthesis packet and guide generated/i);

  const packet = await readJson(path.join(cwd, ".archify", "docs", "archify", "packet.json"));
  const brief = await fs.readFile(path.join(cwd, ".archify", "docs", "archify", "brief.md"), "utf8");
  const guide = await readJson(path.join(cwd, ".archify", "docs", "archify", "guide.json"));
  const guideBrief = await fs.readFile(path.join(cwd, ".archify", "docs", "archify", "guide.md"), "utf8");

  assert.equal(packet.docType, "archify");
  assert.equal(packet.outputFile, "archify.md");
  assert.equal(packet.status, "ready");
  assert.equal(packet.phase, "generate");
  assert.equal(packet.artifacts.architectureContext, ".archify/architecture-context.json");
  assert.ok(Array.isArray(packet.generationRules.readOrder));
  assert.equal(packet.generationRules.finalOutputFile, "archify.md");
  assert.equal(packet.generationRules.documentShape, "upload_ready_architecture_prompt_pack");
  assert.equal(packet.supportingDocuments.primaryReadme, "README.md");
  assert.deepEqual(packet.supportingDocuments.additionalDocs, []);
  assert.equal(packet.generationRules.readOrder.at(-1), "README.md");
  assert.ok(packet.generationRules.mustSeparate.includes("Confirmed From Codebase"));
  assert.ok(packet.generationRules.requiredSections.includes("System Prompt"));
  assert.ok(packet.generationRules.requiredSections.includes("User Prompt"));
  assert.ok(packet.generationRules.requiredSections.includes("Grounded Repository Context"));
  assert.ok(packet.generationRules.requiredSections.includes("Diagram / Image Generation Instructions"));
  assert.equal(packet.generationRules.promptBehavior.firstResponseMustAskArtifactType, true);
  assert.ok(packet.generationRules.promptBehavior.artifactTypeOptions.includes("high-level architecture"));
  assert.ok(packet.generationRules.promptBehavior.artifactTypeOptions.includes("custom request"));
  assert.equal(packet.generationRules.promptBehavior.firstResponseMustAskVisualStyle, true);
  assert.equal(packet.generationRules.promptBehavior.mustAllowCustomAnswers, true);
  assert.equal(packet.generationRules.promptBehavior.mustWaitForAnswersBeforeFinalOutput, true);
  assert.equal(packet.generationRules.diagramCapabilityPolicy.mustAskForPreferredVisualStyleBeforeGeneratingVisuals, true);
  assert.equal(packet.generationRules.diagramCapabilityPolicy.generateImageWhenAppSupportsIt, true);
  assert.equal(packet.generationRules.diagramCapabilityPolicy.fallbackToRenderReadyDiagramSpecWhenImageGenerationUnavailable, true);
  assert.equal(packet.questionnaireTemplate.sectionTitle, "Questions Before Architecture Generation");
  assert.ok(packet.questionnaireTemplate.questions.length >= 5);
  assert.equal(packet.generationRules.questionnairePolicy.mustAskBeforeFinalArchitecture, true);
  assert.equal(packet.generationRules.questionnairePolicy.readmeMayEnrichWithoutOverridingGroundedEvidence, true);
  assert.ok(packet.confirmedFromCodebase.length >= 2);
  assert.ok(packet.openQuestionsAndUncertainty.length >= 1);
  assert.equal(guide.status, "ready");
  assert.equal(guide.phase, "generate");
  assert.equal(guide.docType, "archify");
  assert.equal(guide.outputFile, "archify.md");
  assert.equal(guide.readOrder[0], ".archify/docs/archify/packet.json");
  assert.equal(guide.readOrder[1], ".archify/docs/archify/guide.json");
  assert.ok(guide.primaryArtifacts.includes(".archify/architecture-context.json"));
  assert.ok(guide.sectionPlan.some((item) => item.section === "Grounded Repository Context"));
  assert.ok(guide.sectionPlan.some((item) => item.section === "Confirmed From Codebase"));
  assert.ok(Array.isArray(guide.draftingWorkflow));
  assert.ok(guide.draftingWorkflow.some((item) => /section by section/i.test(item)));
  const groundedSection = guide.sectionPlan.find((item) => item.section === "Grounded Repository Context");
  assert.ok(groundedSection);
  assert.ok(groundedSection.sourceFields.includes("confirmedFromCodebase"));
  assert.ok(Array.isArray(groundedSection.draftingInstructions));
  assert.ok(groundedSection.draftingInstructions.length >= 1);
  assert.match(groundedSection.missingEvidenceBehavior, /evidence/i);
  assert.ok(Array.isArray(groundedSection.validationChecks));
  assert.ok(groundedSection.validationChecks.length >= 1);
  assert.ok(guide.forbiddenBehaviors.some((item) => /Do not inspect the whole repository/i.test(item)));
  assert.ok(guide.validationChecks.some((item) => /Read `\.archify\/docs\/archify\/guide\.json` before reading repository files/i.test(item)));
  assert.ok(guide.validationChecks.some((item) => /Draft and validate `archify\.md` section by section/i.test(item)));
  assert.match(brief, /archify\.md/);
  assert.match(brief, /primary grounded source of confirmed facts/);
  assert.match(brief, /supportingDocuments\.primaryReadme/);
  assert.match(brief, /README-only claims override grounded `\.archify` evidence/i);
  assert.match(brief, /Write one final file: `archify\.md`/);
  assert.match(brief, /upload-ready multi-role architecture prompt document/i);
  assert.match(brief, /Include explicit `System Prompt` and `User Prompt` sections/i);
  assert.match(brief, /Grounded Repository Context/i);
  assert.match(brief, /Questions Before Architecture Generation/);
  assert.match(brief, /first guided interaction must ask which architecture artifact the user wants/i);
  assert.match(brief, /second guided interaction must ask how the architecture should look visually/i);
  assert.match(brief, /render-ready diagram prompt or specification/i);
  assert.match(guideBrief, /# Archify Guide Brief/);
  assert.match(guideBrief, /Doc type: `archify`/);
  assert.match(guideBrief, /`\.archify\/docs\/archify\/guide\.json`/);
  assert.match(guideBrief, /## Drafting Workflow/);
  assert.match(guideBrief, /Do not inspect the whole repository/i);
  assert.ok(!(await fs.access(path.join(cwd, "architecture.md")).then(() => true).catch(() => false)));
  assert.ok(!(await fs.access(path.join(cwd, "design.md")).then(() => true).catch(() => false)));
  assert.ok(!(await fs.access(path.join(cwd, "archify.md")).then(() => true).catch(() => false)));
  assert.ok(!(await fs.access(path.join(cwd, "archify_design.md")).then(() => true).catch(() => false)));
});

test("generate exposes lowercase root readme separately from optional supporting docs", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "readme.md"), "# Fixture\n", "utf8");
  await fs.writeFile(path.join(cwd, "architecture.md"), "# Architecture\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "app.py"), "def run():\n    return 1\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);
  const result = runCli(["generate", "."], { cwd });
  assert.equal(result.status, 0, result.stderr);

  const packet = await readJson(path.join(cwd, ".archify", "docs", "archify", "packet.json"));
  assert.equal(packet.supportingDocuments.primaryReadme, "readme.md");
  assert.deepEqual(packet.supportingDocuments.additionalDocs, ["architecture.md"]);
  assert.equal(packet.generationRules.readOrder.at(-2), "readme.md");
  assert.equal(packet.generationRules.readOrder.at(-1), "architecture.md");
});

test("generate skips README cleanly when no root readme exists", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "architecture.md"), "# Architecture\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "app.py"), "def run():\n    return 1\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);
  const result = runCli(["generate", "."], { cwd });
  assert.equal(result.status, 0, result.stderr);

  const packet = await readJson(path.join(cwd, ".archify", "docs", "archify", "packet.json"));
  const brief = await fs.readFile(path.join(cwd, ".archify", "docs", "archify", "brief.md"), "utf8");
  assert.equal(packet.supportingDocuments.primaryReadme, null);
  assert.deepEqual(packet.supportingDocuments.additionalDocs, ["architecture.md"]);
  assert.ok(!packet.generationRules.readOrder.includes("README.md"));
  assert.ok(!packet.generationRules.readOrder.includes("readme.md"));
  assert.match(brief, /Skip the README step cleanly/);
});

test("write materializes archify.md from the generated packet and guide with overwrite protection", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "README.md"), "# Fixture\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "app.py"), "def run():\n    return 1\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);
  assert.equal(runCli(["generate", "."], { cwd }).status, 0);

  let result = runCli(["write", "."], { cwd });
  assert.equal(result.status, 0, result.stderr);
  let parsed = parseStdoutJson(result);
  assert.match(parsed.result.note, /archify\.md written/i);
  assert.equal(parsed.overwritten, false);

  const archify = await fs.readFile(path.join(cwd, "archify.md"), "utf8");
  assert.match(archify, /^# Archify/m);
  assert.match(archify, /^## System Prompt$/m);
  assert.match(archify, /^## User Prompt$/m);
  assert.match(archify, /^## Grounded Repository Context$/m);
  assert.match(archify, /^## Confirmed From Codebase$/m);
  assert.match(archify, /^## Inferred Architecture$/m);
  assert.match(archify, /^## Questions Before Architecture Generation$/m);
  assert.match(archify, /^## Diagram \/ Image Generation Instructions$/m);
  assert.match(archify, /^## Open Questions \/ Uncertainty$/m);
  assert.match(archify, /Treat `\.archify` artifacts as the primary source of confirmed facts/i);
  assert.match(archify, /Primary README: `README\.md`/);
  assert.match(archify, /Wait for those answers before finalizing the architecture response/i);

  result = runCli(["write", "."], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /OUTPUT_DOCUMENT_EXISTS/);

  result = runCli(["write", ".", "--force"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  parsed = parseStdoutJson(result);
  assert.equal(parsed.overwritten, true);
});

test("generate and write support alternate doc types with scoped outputs", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "README.md"), "# Fixture\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "app.py"), "def run():\n    return 1\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);

  let result = runCli(["generate", ".", "--doc-type", "tech_stack"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  let parsed = parseStdoutJson(result);
  assert.equal(parsed.docType, "tech_stack");

  const packet = await readJson(path.join(cwd, ".archify", "docs", "tech_stack", "packet.json"));
  const guide = await readJson(path.join(cwd, ".archify", "docs", "tech_stack", "guide.json"));
  assert.equal(packet.docType, "tech_stack");
  assert.equal(packet.outputFile, "TECH_STACK.md");
  assert.equal(guide.docType, "tech_stack");
  assert.equal(guide.outputFile, "TECH_STACK.md");
  assert.equal(guide.readOrder[0], ".archify/docs/tech_stack/packet.json");

  result = runCli(["write", ".", "--doc-type", "tech_stack"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  parsed = parseStdoutJson(result);
  assert.equal(parsed.docType, "tech_stack");

  const techStack = await fs.readFile(path.join(cwd, "TECH_STACK.md"), "utf8");
  assert.match(techStack, /^# TECH STACK$/m);
  assert.match(techStack, /^## Overview$/m);
  assert.match(techStack, /^## Confirmed Stack$/m);
  assert.match(techStack, /^## Inferred Stack Notes$/m);
  assert.match(techStack, /^## Open Questions \/ Uncertainty$/m);
  assert.ok(!(await fs.access(path.join(cwd, "API_DESIGN.md")).then(() => true).catch(() => false)));
});

test("status is doc-type aware for synthesis and final document freshness", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('v1')\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);

  let result = runCli(["status", "--doc-type", "flows"], { cwd });
  let parsed = parseStdoutJson(result);
  assert.equal(parsed.docType, "flows");
  assert.equal(parsed.recommendedAction, "generate");

  assert.equal(runCli(["generate", ".", "--doc-type", "flows"], { cwd }).status, 0);
  result = runCli(["status", "--doc-type", "flows"], { cwd });
  parsed = parseStdoutJson(result);
  assert.equal(parsed.generatedPacketReady, true);
  assert.equal(parsed.finalDocumentExists, false);
  assert.equal(parsed.recommendedAction, "write");
  assert.match(parsed.summary, /FLOWS\.md has not been written yet/i);

  assert.equal(runCli(["write", ".", "--doc-type", "flows"], { cwd }).status, 0);
  result = runCli(["status", "--doc-type", "flows"], { cwd });
  parsed = parseStdoutJson(result);
  assert.equal(parsed.finalDocumentExists, true);
  assert.equal(parsed.recommendedAction, "reuse");
});

test("analyze enables docs-first semantic enrichment when configured", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.mkdir(path.join(cwd, "docs"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "app.py"), "def run():\n    return 1\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "worker.py"), "from app import run\n\n\ndef start():\n    return run()\n", "utf8");
  await fs.writeFile(path.join(cwd, "docs", "architecture.md"), [
    "# Architecture",
    "",
    "The runtime lives in `src/app.py` and exposes `run()`.",
    "",
    "## Flow",
    "",
    "The worker at `src/worker.py` starts the system."
  ].join("\n"), "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  const configPath = path.join(cwd, "archify.config.json");
  const config = await readJson(configPath);
  config.analysis.semantic.enabled = true;
  await fs.writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");

  const result = runCli(["analyze", "."], { cwd });
  assert.equal(result.status, 0, result.stderr);
  const parsed = parseStdoutJson(result);
  assert.equal(parsed.result.semanticDocumentCount, 1);
  assert.match(parsed.result.note, /Phase 7 docs-first enrichment completed/);

  const graph = await readJson(path.join(cwd, ".archify", "graph.json"));
  const docsSummary = await readJson(path.join(cwd, ".archify", "docs-summary.json"));
  const manifest = await readJson(path.join(cwd, ".archify", "manifest.json"));
  const architectureContext = await readJson(path.join(cwd, ".archify", "architecture-context.json"));

  assert.equal(graph.semantic.backend, "none");
  assert.ok(graph.nodes.some((node) => node.file_type === "document" && node.kind === "doc_section"));
  assert.ok(graph.edges.some((edge) => edge.relation === "references" && edge.source_file === "docs/architecture.md"));
  assert.equal(docsSummary.status, "ready");
  assert.equal(docsSummary.summary.processedDocumentCount, 1);
  assert.ok(docsSummary.confirmedFacts.processedDocuments.some((item) => item.path === "docs/architecture.md"));
  assert.deepEqual(docsSummary.confirmedFacts.readmeLikeDocs, []);
  assert.ok(docsSummary.inferredAlignments.docToSubsystem.length >= 1);
  assert.equal(manifest.files["docs/architecture.md"].semantic.status, "ready");
  assert.ok(architectureContext.summary.processedDocumentCount >= 1);
});

test("clean removes generated artifacts but preserves config and ignore files", async () => {
  const cwd = await makeWorkspace();
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);

  const result = runCli(["clean"], { cwd });
  assert.equal(result.status, 0, result.stderr);

  const entries = await fs.readdir(path.join(cwd, ".archify"));
  assert.deepEqual(entries, []);

  await fs.access(path.join(cwd, "archify.config.json"));
  await fs.access(path.join(cwd, ".archifyignore"));
});

test("status explains setup state before and after analysis", async () => {
  const cwd = await makeWorkspace();

  let result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  let parsed = parseStdoutJson(result);
  assert.equal(parsed.installed, false);
  assert.match(parsed.nextStep, /npx archify-cli init/i);

  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  parsed = parseStdoutJson(result);
  assert.equal(parsed.installed, true);
  assert.equal(parsed.analysisReady, false);
  assert.equal(parsed.recommendedAction, "analyze");
  assert.match(parsed.summary, /not been built yet/i);

  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);

  result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  parsed = parseStdoutJson(result);
  assert.equal(parsed.installed, true);
  assert.equal(parsed.analysisReady, true);
  assert.equal(parsed.knowledgeStale, false);
  assert.equal(parsed.recommendedAction, "generate");
  assert.ok(parsed.availableArtifacts.includes("manifest.json"));

  assert.equal(runCli(["generate", "."], { cwd }).status, 0);

  result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  parsed = parseStdoutJson(result);
  assert.equal(parsed.generatedPacketReady, true);
  assert.equal(parsed.finalDocumentExists, false);
  assert.equal(parsed.recommendedAction, "write");

  assert.equal(runCli(["write", "."], { cwd }).status, 0);

  result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  parsed = parseStdoutJson(result);
  assert.equal(parsed.finalDocumentExists, true);
  assert.equal(parsed.finalDocumentStale, false);
  assert.equal(parsed.recommendedAction, "reuse");
});

test("status reports stale knowledge after repository files change", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('v1')\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);

  await new Promise((resolve) => setTimeout(resolve, 20));
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('v2')\n", "utf8");

  const result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  const parsed = parseStdoutJson(result);
  assert.equal(parsed.analysisReady, true);
  assert.equal(parsed.knowledgeStale, true);
  assert.equal(parsed.recommendedAction, "analyze");
  assert.equal(parsed.freshness.newestWorkspaceChange.path, "src/app.py");
});

test("status reports stale design packet after analysis is refreshed", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('v1')\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);
  assert.equal(runCli(["generate", "."], { cwd }).status, 0);

  await new Promise((resolve) => setTimeout(resolve, 20));
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('v2')\n", "utf8");
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);

  const result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  const parsed = parseStdoutJson(result);
  assert.equal(parsed.analysisReady, true);
  assert.equal(parsed.generatedPacketReady, true);
  assert.equal(parsed.knowledgeStale, false);
  assert.equal(parsed.designPacketStale, true);
  assert.equal(parsed.recommendedAction, "generate");
});

test("status reports stale archify.md after the design packet is regenerated", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('v1')\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);
  assert.equal(runCli(["generate", "."], { cwd }).status, 0);
  assert.equal(runCli(["write", "."], { cwd }).status, 0);

  await new Promise((resolve) => setTimeout(resolve, 20));
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('v2')\n", "utf8");
  assert.equal(runCli(["analyze", "."], { cwd }).status, 0);
  assert.equal(runCli(["generate", "."], { cwd }).status, 0);

  const result = runCli(["status"], { cwd });
  assert.equal(result.status, 0, result.stderr);
  const parsed = parseStdoutJson(result);
  assert.equal(parsed.generatedPacketReady, true);
  assert.equal(parsed.finalDocumentExists, true);
  assert.equal(parsed.finalDocumentStale, true);
  assert.equal(parsed.recommendedAction, "write");
});

test("analyze honors .archifyignore, skips sensitive files, and reports real counts deterministically", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.mkdir(path.join(cwd, "docs"), { recursive: true });
  await fs.mkdir(path.join(cwd, "ignored"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "app.py"), "print('ok')\n", "utf8");
  await fs.writeFile(path.join(cwd, "docs", "readme.md"), "# Readme\n", "utf8");
  await fs.writeFile(path.join(cwd, "ignored", "skip.py"), "print('skip')\n", "utf8");
  await fs.writeFile(path.join(cwd, "auth.secret"), "value\n", "utf8");
  await fs.writeFile(path.join(cwd, ".hidden.py"), "print('hidden')\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);
  await fs.appendFile(path.join(cwd, ".archifyignore"), "ignored/\n", "utf8");

  const first = runCli(["analyze", "."], { cwd });
  const firstGraph = await readJson(path.join(cwd, ".archify", "graph.json"));
  const second = runCli(["analyze", "."], { cwd });
  assert.equal(first.status, 0, first.stderr);
  assert.equal(second.status, 0, second.stderr);

  const firstFacts = await readJson(path.join(cwd, ".archify", "facts.json"));
  const secondGraph = await readJson(path.join(cwd, ".archify", "graph.json"));
  const secondFacts = parseStdoutJson(second).result.totals;

  assert.equal(firstFacts.totals.files, 2);
  assert.equal(firstFacts.skipped.ignored, 1);
  assert.equal(firstFacts.skipped.sensitive, 1);
  assert.equal(firstFacts.skipped.hidden, 1);
  assert.deepEqual(firstFacts.inventory.map((item) => item.path), [
    "docs/readme.md",
    "src/app.py"
  ]);
  assert.deepEqual(secondFacts, firstFacts.totals);
  assert.deepEqual(firstGraph.summary, secondGraph.summary);
  assert.deepEqual(firstGraph.nodes.map((node) => node.id), secondGraph.nodes.map((node) => node.id));
});

test("invalid config and invalid target path surface deterministic errors", async () => {
  const cwd = await makeWorkspace();
  await fs.writeFile(path.join(cwd, "archify.config.json"), "{\n", "utf8");

  let result = runCli(["analyze", "."], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /CONFIG_INVALID/);

  await fs.writeFile(path.join(cwd, "archify.config.json"), JSON.stringify({
    defaults: { outputDir: ".archify" },
    skillInstall: { mode: "project", platform: "codex", platforms: ["codex"], installedAt: null, version: 1, target: null, targets: [] }
  }), "utf8");

  result = runCli(["analyze", "missing-dir"], { cwd });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /TARGET_MISSING/);
});

test("analyze extracts Python, JS/TS, and SQL structure with deterministic graph output", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.mkdir(path.join(cwd, "db"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "util.py"), "def helper():\n    return 1\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "app.py"), "from util import helper\n\nclass Service:\n    def run(self):\n        return helper()\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "dep.ts"), "export function dep() { return 1; }\n", "utf8");
  await fs.writeFile(path.join(cwd, "src", "api.ts"), "import { dep } from './dep';\nexport function handler() { return dep(); }\n", "utf8");
  await fs.writeFile(path.join(cwd, "db", "001_init.sql"), "create table users(id int primary key);\nselect * from users;\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  const first = runCli(["analyze", "."], { cwd });
  const firstGraph = await readJson(path.join(cwd, ".archify", "graph.json"));
  const second = runCli(["analyze", "."], { cwd });
  assert.equal(first.status, 0, first.stderr);
  assert.equal(second.status, 0, second.stderr);

  const graph = await readJson(path.join(cwd, ".archify", "graph.json"));
  assert.equal(graph.summary.warningCount, 0);
  assert.ok(graph.nodes.some((node) => node.label === "helper()"));
  assert.ok(graph.nodes.some((node) => node.label === "handler()"));
  assert.ok(graph.nodes.some((node) => node.label === "users"));
  assert.ok(graph.edges.some((edge) => edge.relation === "imports" && edge.confidence === "INFERRED"));
  assert.ok(graph.edges.some((edge) => edge.relation === "calls"));

  assert.deepEqual(firstGraph.summary, graph.summary);
  assert.deepEqual(firstGraph.nodes.map((node) => node.id), graph.nodes.map((node) => node.id));
});

test("analyze records extraction warnings for malformed supported files without crashing", async () => {
  const cwd = await makeWorkspace();
  await fs.mkdir(path.join(cwd, "src"), { recursive: true });
  await fs.writeFile(path.join(cwd, "src", "broken.py"), "def broken(:\n    pass\n", "utf8");
  assert.equal(runInit({ cwd, projectPath: "." }).status, 0);

  const result = runCli(["analyze", "."], { cwd });
  assert.equal(result.status, 0, result.stderr);

  const graph = await readJson(path.join(cwd, ".archify", "graph.json"));
  const manifest = await readJson(path.join(cwd, ".archify", "manifest.json"));
  assert.equal(graph.summary.warningCount, 1);
  assert.equal(graph.warnings[0].path, "src/broken.py");
  assert.equal(manifest.files["src/broken.py"].extraction.status, "warning");
  assert.equal(manifest.graphSummary.warningCount, 1);
});

test("schema helpers validate required fields and stable IDs", () => {
  const script = `
from archify_engine.schema import make_file_id, make_symbol_id, validate_extraction

payload = {
    "nodes": [{"id": "n1", "label": "node", "file_type": "code", "source_file": "src/app.py"}],
    "edges": [{"source": "n1", "target": "n2", "relation": "calls", "confidence": "BAD", "source_file": "src/app.py"}],
    "hyperedges": [],
}
print(make_file_id("src/app.py"))
print(make_symbol_id("src/app.py", "function", "run"))
print(validate_extraction(payload))
`;
  const pythonCommand = process.platform === "win32" ? "python" : "python3";
  const result = spawnSync(pythonCommand, ["-c", script], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONPATH: path.join(repoRoot, "python")
    },
    encoding: "utf8"
  });

  assert.equal(result.status, 0, result.stderr);
  const lines = result.stdout.trim().split(/\r?\n/);
  assert.equal(lines[0], "file_src_app_py");
  assert.equal(lines[1], "symbol_src_app_py_function_run");
  assert.match(lines[2], /invalid confidence/);
  assert.match(lines[2], /does not match a node id/);
});
