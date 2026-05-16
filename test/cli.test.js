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
  assert.match(codexSkill, /invokes this `archify` skill instead of manually calling Archify subcommands/i);
  assert.match(codexSkill, /Check whether `archify\.config\.json` exists in the current project before starting analysis/i);
  assert.match(codexSkill, /If the project is not initialized yet, ask for permission before starting `npx archify init --install-mode project --project-path \. --platform codex`/i);
  assert.match(codexSkill, /Run project initialization automatically when `archify\.config\.json` is missing/i);
  assert.match(codexSkill, /Ask for permission before starting `npx archify analyze \.`/i);
  assert.match(codexSkill, /building `?\.archify\/`? can take time on larger repositories/i);
  assert.match(codexSkill, /start one bounded README\/context subagent in parallel with the analysis step/i);
  assert.match(codexSkill, /Do not block on the README\/context subagent before `analyze` finishes/i);
  assert.match(codexSkill, /If `npx` hangs or is unreliable in a local checkout, fall back to `node \.\/bin\/archify\.js analyze \.`/i);
  assert.match(codexSkill, /If `npx` is unreliable in a local checkout, fall back to `node \.\/bin\/archify\.js generate \.`/i);
  assert.match(codexSkill, /Verify that `\.archify\/design-packet\.json` exists after `generate`/i);
  assert.match(codexSkill, /Always start from `\.archify\/design-packet\.json`/i);
  assert.match(codexSkill, /upload-ready architecture prompt pack/i);
  assert.match(codexSkill, /Include explicit `System Prompt`, `User Prompt`, `Grounded Repository Context`, `Questions Before Architecture Generation`, and `Diagram \/ Image Generation Instructions` sections/i);
  assert.match(codexSkill, /Make the first response ask which architecture artifact the user wants/i);
  assert.match(codexSkill, /Ask how the architecture should look visually before generating visuals/i);
  assert.match(codexSkill, /If the AI app supports image generation, generate the requested architecture image or diagram\. If it does not, return a render-ready diagram prompt or specification instead/i);
  assert.match(codexSkill, /Treat `\.archify` artifacts as the primary source of confirmed facts/i);
  assert.match(codexSkill, /README-only or supporting claims/i);
  assert.match(codexSkill, /If `archify\.md` already exists, ask for permission before overwriting it/i);
  assert.match(codexSkill, /Do not ask the user to manually run `init`, `analyze`, or `generate`/i);
  assert.match(codexSkill, /`archify\.md`/i);

  const claudeSkill = await fs.readFile(path.join(cwd, ".claude", "skills", "archify", "SKILL.md"), "utf8");
  assert.match(claudeSkill, /^---\nname: archify\ndescription:/);
  assert.match(claudeSkill, /Claude Code/i);
  assert.match(claudeSkill, /Check whether `archify\.config\.json` exists in the current project before starting analysis/i);
  assert.match(claudeSkill, /If the project is not initialized yet, ask for permission before starting `npx archify init --install-mode project --project-path \. --platform claude-code`/i);
  assert.match(claudeSkill, /Run project initialization automatically when `archify\.config\.json` is missing/i);
  assert.match(claudeSkill, /Ask for permission before starting `npx archify analyze \.`/i);
  assert.match(claudeSkill, /Read the root `README\.md` first when it is present/i);
  assert.match(claudeSkill, /supportingDocuments\.primaryReadme/i);
  assert.match(claudeSkill, /Always start from `\.archify\/design-packet\.json`/i);
  assert.match(claudeSkill, /upload-ready architecture prompt pack/i);
  assert.match(claudeSkill, /System Prompt/i);
  assert.match(claudeSkill, /User Prompt/i);
  assert.match(claudeSkill, /Make the first response ask which architecture artifact the user wants/i);
  assert.match(claudeSkill, /Ask how the architecture should look visually before generating visuals/i);
  assert.match(claudeSkill, /Treat `\.archify` artifacts as the primary source of confirmed facts/i);
  assert.match(claudeSkill, /If `archify\.md` already exists, ask for permission before overwriting it/i);
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
  assert.match(sharedSkill, /First determine whether the current agent is Codex or Claude Code/i);
  assert.match(sharedSkill, /Codex workflow:/i);
  assert.match(sharedSkill, /Claude Code workflow:/i);
  assert.match(sharedSkill, /Generic fallback workflow:/i);
  assert.match(sharedSkill, /Check whether `archify\.config\.json` exists in the current project before starting analysis/i);
  assert.match(sharedSkill, /If the project is not initialized yet, ask for permission before starting `npx archify init --install-mode project --project-path \. --platform codex`/i);
  assert.match(sharedSkill, /If the project is not initialized yet, ask for permission before starting `npx archify init --install-mode project --project-path \. --platform claude-code`/i);
  assert.match(sharedSkill, /If the project is not initialized yet, ask for permission before starting `npx archify init --install-mode project --project-path \. --platform both`/i);
  assert.match(sharedSkill, /Run project initialization automatically when `archify\.config\.json` is missing/i);
  assert.match(sharedSkill, /start one bounded README\/context subagent in parallel with the analysis step/i);
  assert.match(sharedSkill, /Do not block on the README\/context subagent before `analyze` finishes/i);
  assert.match(sharedSkill, /Read the root `README\.md` first when it is present/i);
  assert.match(sharedSkill, /do not start agent-specific subagents or parallel branches when detection is unclear/i);
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
  assert.match(installedClaudeSkill, /Check whether `archify\.config\.json` exists in the current project before starting analysis/i);
  assert.match(installedClaudeSkill, /Run project initialization automatically when `archify\.config\.json` is missing/i);
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

test("generate writes an internal design packet from grounded .archify artifacts", async () => {
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
  assert.match(parsed.result.note, /Phase 9 design packet/i);
  assert.match(parsed.result.note, /prompt-pack authoring/i);

  const packet = await readJson(path.join(cwd, ".archify", "design-packet.json"));
  const brief = await fs.readFile(path.join(cwd, ".archify", "design-brief.md"), "utf8");

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
  assert.match(brief, /Start from `\.archify\/design-packet\.json`/);
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

  const packet = await readJson(path.join(cwd, ".archify", "design-packet.json"));
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

  const packet = await readJson(path.join(cwd, ".archify", "design-packet.json"));
  const brief = await fs.readFile(path.join(cwd, ".archify", "design-brief.md"), "utf8");
  assert.equal(packet.supportingDocuments.primaryReadme, null);
  assert.deepEqual(packet.supportingDocuments.additionalDocs, ["architecture.md"]);
  assert.ok(!packet.generationRules.readOrder.includes("README.md"));
  assert.ok(!packet.generationRules.readOrder.includes("readme.md"));
  assert.match(brief, /Skip the README step cleanly/);
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
  const result = spawnSync("python3", ["-c", script], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONPATH: path.join(repoRoot, "python")
    },
    encoding: "utf8"
  });

  assert.equal(result.status, 0, result.stderr);
  const lines = result.stdout.trim().split("\n");
  assert.equal(lines[0], "file_src_app_py");
  assert.equal(lines[1], "symbol_src_app_py_function_run");
  assert.match(lines[2], /invalid confidence/);
  assert.match(lines[2], /does not match a node id/);
});
