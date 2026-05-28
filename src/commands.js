import fs from "node:fs/promises";
import path from "node:path";

import {
  ALL_ANALYSIS_ARTIFACTS,
  OPERATIONAL_ARTIFACTS,
  OUTPUT_DIR,
  REQUIRED_GENERATE_ARTIFACTS,
  RESERVED_ARTIFACTS
} from "./constants.js";
import { ensureConfig, ensureIgnoreFile, ensureOutputDir, loadConfig } from "./config.js";
import { ArchifyError } from "./errors.js";
import { pathExists, removeContents } from "./fs-utils.js";
import { resolveSetupOptions } from "./prompt.js";
import { runPythonEngine } from "./python.js";
import { installSkillTemplates } from "./skills.js";

function resolveTargetPath(repoRoot, inputPath) {
  const targetPath = path.resolve(repoRoot, inputPath ?? ".");
  return targetPath;
}

async function validateTargetPath(targetPath) {
  const exists = await pathExists(targetPath);
  if (!exists) {
    throw new ArchifyError(`Target path does not exist: ${targetPath}`, {
      code: "TARGET_MISSING",
      exitCode: 2
    });
  }
}

async function validateGenerateArtifacts(repoRoot, outputDir) {
  const missing = [];

  for (const artifact of REQUIRED_GENERATE_ARTIFACTS) {
    const artifactPath = path.join(repoRoot, outputDir, artifact);
    if (!(await pathExists(artifactPath))) {
      missing.push(artifact);
      continue;
    }

    if (artifact.endsWith(".json")) {
      const raw = await fs.readFile(artifactPath, "utf8");
      const parsed = JSON.parse(raw);
      if (parsed.status !== "ready") {
        missing.push(`${artifact} (status=${parsed.status ?? "unknown"})`);
      }
    }
  }

  if (missing.length > 0) {
    throw new ArchifyError(
      `Generate requires completed analysis artifacts in ${outputDir}. Missing or incomplete: ${missing.join(", ")}.`,
      { code: "GENERATE_PREREQS_MISSING", exitCode: 2 }
    );
  }
}

const STALE_CHECK_IGNORED_DIRS = new Set([
  ".git",
  ".archify",
  ".agents",
  ".claude",
  "node_modules",
  "dist",
  "build"
]);

async function collectNewestWorkspaceChange(rootDir, currentDir = rootDir) {
  const entries = await fs.readdir(currentDir, { withFileTypes: true });
  let newest = null;

  for (const entry of entries) {
    if (entry.name === "archify.md") {
      continue;
    }

    const fullPath = path.join(currentDir, entry.name);
    const relativePath = path.relative(rootDir, fullPath) || entry.name;

    if (entry.isDirectory()) {
      if (STALE_CHECK_IGNORED_DIRS.has(entry.name)) {
        continue;
      }

      const nestedNewest = await collectNewestWorkspaceChange(rootDir, fullPath);
      if (nestedNewest && (!newest || nestedNewest.mtimeMs > newest.mtimeMs)) {
        newest = nestedNewest;
      }
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }

    const stats = await fs.stat(fullPath);
    const candidate = {
      path: relativePath.split(path.sep).join("/"),
      mtimeMs: stats.mtimeMs,
      modifiedAt: stats.mtime.toISOString()
    };

    if (!newest || candidate.mtimeMs > newest.mtimeMs) {
      newest = candidate;
    }
  }

  return newest;
}

function parseTimestamp(value) {
  if (!value) {
    return null;
  }

  const time = Date.parse(value);
  return Number.isNaN(time) ? null : time;
}

export async function initCommand(repoRoot, options) {
  const setup = await resolveSetupOptions(repoRoot, options);
  const installRoot = setup.projectRoot;
  const { configPath, created: createdConfig, config } = await ensureConfig(installRoot, setup);
  const { ignorePath, created: createdIgnore } = await ensureIgnoreFile(installRoot);
  const skillTargets = await installSkillTemplates(installRoot, setup);

  return {
    command: "init",
    installMode: setup.installMode,
    platforms: setup.platforms,
    installRoot,
    configPath,
    ignorePath,
    skillTargets,
    outputDir: config.defaults.outputDir,
    createdConfig,
    createdIgnore
  };
}

export async function analyzeCommand(appRoot, repoRoot, targetArg) {
  const { data: config } = await loadConfig(repoRoot);
  const targetPath = resolveTargetPath(repoRoot, targetArg);
  await validateTargetPath(targetPath);
  await ensureOutputDir(repoRoot, config.defaults.outputDir || OUTPUT_DIR);

  const result = runPythonEngine({
    appRoot,
    repoRoot,
    command: "analyze",
    targetPath,
    config
  });

  return {
    command: "analyze",
    targetPath,
    outputDir: config.defaults.outputDir || OUTPUT_DIR,
    reservedArtifacts: RESERVED_ARTIFACTS,
    operationalArtifacts: OPERATIONAL_ARTIFACTS,
    result
  };
}

export async function generateCommand(appRoot, repoRoot, targetArg) {
  const { data: config } = await loadConfig(repoRoot);
  const targetPath = resolveTargetPath(repoRoot, targetArg);
  await validateTargetPath(targetPath);
  await validateGenerateArtifacts(repoRoot, config.defaults.outputDir || OUTPUT_DIR);

  const result = runPythonEngine({
    appRoot,
    repoRoot,
    command: "generate",
    targetPath,
    config
  });

  return {
    command: "generate",
    targetPath,
    outputDir: config.defaults.outputDir || OUTPUT_DIR,
    result
  };
}

export async function cleanCommand(repoRoot) {
  const { data: config } = await loadConfig(repoRoot);
  const outputDir = path.join(repoRoot, config.defaults.outputDir || OUTPUT_DIR);
  const exists = await pathExists(outputDir);

  if (exists) {
    await removeContents(outputDir);
  }

  return {
    command: "clean",
    outputDir,
    removed: exists
  };
}

export async function statusCommand(repoRoot) {
  const configPath = path.join(repoRoot, "archify.config.json");
  const configExists = await pathExists(configPath);

  if (!configExists) {
    return {
      command: "status",
      installed: false,
      repoRoot,
      summary: "Archify is not set up in this repository yet.",
      nextStep: "Run `npx archify init` in this repository.",
    };
  }

  const { data: config } = await loadConfig(repoRoot);
  const outputDirName = config.defaults.outputDir || OUTPUT_DIR;
  const outputDir = path.join(repoRoot, outputDirName);
  const outputDirExists = await pathExists(outputDir);
  const manifestPath = path.join(outputDir, "manifest.json");
  const manifestExists = outputDirExists ? await pathExists(manifestPath) : false;
  const designPacketPath = path.join(outputDir, "design-packet.json");
  const designPacketExists = outputDirExists ? await pathExists(designPacketPath) : false;

  let manifest = null;
  let manifestStatus = "missing";
  if (manifestExists) {
    try {
      manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
      manifestStatus = manifest?.status ?? "unknown";
    } catch {
      manifestStatus = "invalid";
    }
  }

  let designPacket = null;
  let designPacketStatus = "missing";
  if (designPacketExists) {
    try {
      designPacket = JSON.parse(await fs.readFile(designPacketPath, "utf8"));
      designPacketStatus = designPacket?.status ?? "unknown";
    } catch {
      designPacketStatus = "invalid";
    }
  }

  const artifactStates = await Promise.all(
    ALL_ANALYSIS_ARTIFACTS.map(async (artifact) => ({
      name: artifact,
      present: outputDirExists ? await pathExists(path.join(outputDir, artifact)) : false
    }))
  );

  const availableArtifacts = artifactStates.filter((item) => item.present).map((item) => item.name);
  const missingArtifacts = artifactStates.filter((item) => !item.present).map((item) => item.name);
  const analysisReady = manifestStatus === "ready";
  const generatedPacketReady = designPacketStatus === "ready";
  const newestWorkspaceChange = await collectNewestWorkspaceChange(repoRoot);
  const manifestGeneratedAtMs = parseTimestamp(manifest?.generatedAt);
  const designPacketGeneratedAtMs = parseTimestamp(designPacket?.generatedAt);
  const knowledgeStale = Boolean(
    analysisReady &&
    newestWorkspaceChange &&
    manifestGeneratedAtMs !== null &&
    newestWorkspaceChange.mtimeMs > manifestGeneratedAtMs
  );
  const designPacketStale = Boolean(
    generatedPacketReady &&
    analysisReady &&
    (
      knowledgeStale ||
      (manifestGeneratedAtMs !== null &&
        designPacketGeneratedAtMs !== null &&
        manifestGeneratedAtMs > designPacketGeneratedAtMs)
    )
  );

  let recommendedAction = "reuse";
  let summary = "Archify is set up and repository knowledge is ready to reuse.";
  let nextStep = "Ask your AI assistant to use Archify on this repo.";

  if (!analysisReady) {
    recommendedAction = "analyze";
    summary = "Archify is set up, but repository knowledge has not been built yet.";
    nextStep = "Ask your AI assistant to use Archify on this repo, or run `npx archify analyze .` if you want to build the knowledge base manually.";
  } else if (knowledgeStale) {
    recommendedAction = "analyze";
    summary = "Archify knowledge exists, but it looks older than the current repository files.";
    nextStep = "Ask your AI assistant to use Archify on this repo so it can refresh the knowledge, or run `npx archify analyze .` manually.";
  } else if (!generatedPacketReady) {
    recommendedAction = "generate";
    summary = "Archify knowledge is ready, but the design packet has not been generated yet.";
    nextStep = "Ask your AI assistant to use Archify on this repo, or run `npx archify generate .` if you want the design packet now.";
  } else if (designPacketStale) {
    recommendedAction = "generate";
    summary = "Archify knowledge is ready, but the design packet is older than the latest analysis.";
    nextStep = "Ask your AI assistant to use Archify on this repo so it can refresh the design packet, or run `npx archify generate .` manually.";
  }

  return {
    command: "status",
    installed: true,
    repoRoot,
    outputDir,
    outputDirExists,
    analysisReady,
    generatedPacketReady,
    knowledgeStale,
    designPacketStale,
    recommendedAction,
    summary,
    nextStep,
    config: {
      installMode: config.skillInstall.mode,
      platforms: config.skillInstall.platforms,
      outputDir: outputDirName,
    },
    manifest: manifest
      ? {
          status: manifest.status ?? "unknown",
          mode: manifest.mode ?? null,
          targetPath: manifest.targetPath ?? null,
          generatedAt: manifest.generatedAt ?? null,
        }
      : null,
    designPacket: designPacket
      ? {
          status: designPacket.status ?? "unknown",
          generatedAt: designPacket.generatedAt ?? null,
        }
      : null,
    freshness: {
      newestWorkspaceChange,
      manifestGeneratedAt: manifest?.generatedAt ?? null,
      designPacketGeneratedAt: designPacket?.generatedAt ?? null,
    },
    availableArtifacts,
    missingArtifacts,
  };
}
