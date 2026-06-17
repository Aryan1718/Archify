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
import { DEFAULT_DOC_TYPE, DOC_TYPES, getDocTypeSpec } from "./doc-types.js";
import { ArchifyError } from "./errors.js";
import { pathExists, removeContents } from "./fs-utils.js";
import { resolveSetupOptions } from "./prompt.js";
import { runPythonEngine } from "./python.js";
import { installSkillTemplates } from "./skills.js";

function resolveTargetPath(repoRoot, inputPath) {
  return path.resolve(repoRoot, inputPath ?? ".");
}

function resolveDocType(docType = DEFAULT_DOC_TYPE) {
  const spec = getDocTypeSpec(docType);
  if (!spec) {
    throw new ArchifyError(`Unsupported doc type "${docType}".`, {
      code: "DOC_TYPE_UNSUPPORTED",
      exitCode: 2
    });
  }
  return spec;
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
  return validateReadyArtifacts(repoRoot, outputDir, REQUIRED_GENERATE_ARTIFACTS, "Generate");
}

async function validateReadyArtifacts(repoRoot, outputDir, artifacts, operationName) {
  const missing = [];

  for (const artifact of artifacts) {
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
      `${operationName} requires completed artifacts in ${outputDir}. Missing or incomplete: ${missing.join(", ")}.`,
      {
        code: `${operationName.toUpperCase()}_PREREQS_MISSING`,
        exitCode: 2
      }
    );
  }
}

function docArtifactDir(outputDir, docType) {
  return path.join(outputDir, "docs", docType);
}

function synthesisArtifactPaths(outputDir, docType) {
  const dir = docArtifactDir(outputDir, docType);
  return {
    dir,
    packet: path.join(dir, "packet.json"),
    brief: path.join(dir, "brief.md"),
    guide: path.join(dir, "guide.json"),
    guideBrief: path.join(dir, "guide.md")
  };
}

async function loadJsonIfPresent(filePath) {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf8"));
  } catch {
    return null;
  }
}

async function resolveSynthesisStatus(outputDir, docType) {
  const paths = synthesisArtifactPaths(outputDir, docType);
  const packet = await loadJsonIfPresent(paths.packet);
  const guide = await loadJsonIfPresent(paths.guide);

  if (packet || guide || docType !== DEFAULT_DOC_TYPE) {
    return { paths, packet, guide };
  }

  return {
    paths,
    packet: await loadJsonIfPresent(path.join(outputDir, "design-packet.json")),
    guide: await loadJsonIfPresent(path.join(outputDir, "archify.guide.json"))
  };
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
  const outputFiles = new Set(Object.values(DOC_TYPES).map((item) => item.outputFile));

  for (const entry of entries) {
    if (currentDir === rootDir && outputFiles.has(entry.name)) {
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

export async function generateCommand(appRoot, repoRoot, targetArg, options = {}) {
  const { data: config } = await loadConfig(repoRoot);
  const doc = resolveDocType(options.docType);
  const targetPath = resolveTargetPath(repoRoot, targetArg);
  await validateTargetPath(targetPath);
  await validateGenerateArtifacts(repoRoot, config.defaults.outputDir || OUTPUT_DIR);

  const result = runPythonEngine({
    appRoot,
    repoRoot,
    command: "generate",
    targetPath,
    config,
    docType: doc.id
  });

  return {
    command: "generate",
    docType: doc.id,
    targetPath,
    outputDir: config.defaults.outputDir || OUTPUT_DIR,
    result
  };
}

export async function writeCommand(appRoot, repoRoot, targetArg, options = {}) {
  const { data: config } = await loadConfig(repoRoot);
  const doc = resolveDocType(options.docType);
  const targetPath = resolveTargetPath(repoRoot, targetArg);
  await validateTargetPath(targetPath);
  const outputDirName = config.defaults.outputDir || OUTPUT_DIR;
  const outputDir = path.join(repoRoot, outputDirName);
  const synthesisPaths = synthesisArtifactPaths(outputDir, doc.id);
  await validateReadyArtifacts(repoRoot, outputDirName, [
    path.relative(outputDir, synthesisPaths.packet).split(path.sep).join("/"),
    path.relative(outputDir, synthesisPaths.guide).split(path.sep).join("/")
  ], "Write");

  const documentPath = path.join(repoRoot, doc.outputFile);
  const exists = await pathExists(documentPath);
  if (exists && !options.force) {
    throw new ArchifyError(
      `${doc.outputFile} already exists. Re-run with \`--force\` to overwrite it.`,
      { code: "OUTPUT_DOCUMENT_EXISTS", exitCode: 2 }
    );
  }

  const result = runPythonEngine({
    appRoot,
    repoRoot,
    command: "write",
    targetPath,
    config,
    docType: doc.id
  });

  return {
    command: "write",
    docType: doc.id,
    targetPath,
    outputFile: documentPath,
    overwritten: exists,
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

export async function statusCommand(repoRoot, options = {}) {
  const doc = resolveDocType(options.docType);
  const configPath = path.join(repoRoot, "archify.config.json");
  const configExists = await pathExists(configPath);

  if (!configExists) {
    return {
      command: "status",
      docType: doc.id,
      outputFile: doc.outputFile,
      installed: false,
      repoRoot,
      summary: "Archify is not set up in this repository yet.",
      nextStep: "Run `npx archify-cli init` in this repository."
    };
  }

  const { data: config } = await loadConfig(repoRoot);
  const outputDirName = config.defaults.outputDir || OUTPUT_DIR;
  const outputDir = path.join(repoRoot, outputDirName);
  const outputDirExists = await pathExists(outputDir);
  const manifestPath = path.join(outputDir, "manifest.json");
  const manifestExists = outputDirExists ? await pathExists(manifestPath) : false;
  const synthesis = await resolveSynthesisStatus(outputDir, doc.id);
  const finalDocumentPath = path.join(repoRoot, doc.outputFile);
  const finalDocumentExists = await pathExists(finalDocumentPath);

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

  const designPacket = synthesis.packet;
  const designPacketStatus = designPacket?.status ?? "missing";

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

  let finalDocumentGeneratedAt = null;
  if (finalDocumentExists) {
    try {
      const stats = await fs.stat(finalDocumentPath);
      finalDocumentGeneratedAt = stats.mtime.toISOString();
    } catch {
      finalDocumentGeneratedAt = null;
    }
  }

  const finalDocumentGeneratedAtMs = parseTimestamp(finalDocumentGeneratedAt);
  const finalDocumentStale = Boolean(
    generatedPacketReady &&
    finalDocumentExists &&
    designPacketGeneratedAtMs !== null &&
    finalDocumentGeneratedAtMs !== null &&
    designPacketGeneratedAtMs > finalDocumentGeneratedAtMs
  );

  let recommendedAction = "reuse";
  let summary = `Archify is set up and ${doc.outputFile} is ready to reuse.`;
  let nextStep = "Ask your AI assistant to use Archify on this repo.";
  const packetLabel = doc.id === DEFAULT_DOC_TYPE ? "design packet" : `${doc.outputFile} synthesis packet`;

  if (!analysisReady) {
    recommendedAction = "analyze";
    summary = "Archify is set up, but repository knowledge has not been built yet.";
    nextStep = "Ask your AI assistant to use Archify on this repo, or run `npx archify-cli analyze .` if you want to build the knowledge base manually.";
  } else if (knowledgeStale) {
    recommendedAction = "analyze";
    summary = "Archify knowledge exists, but it looks older than the current repository files.";
    nextStep = "Ask your AI assistant to use Archify on this repo so it can refresh the knowledge, or run `npx archify-cli analyze .` manually.";
  } else if (!generatedPacketReady) {
    recommendedAction = "generate";
    summary = `Archify knowledge is ready, but the ${packetLabel} has not been generated yet.`;
    nextStep = `Ask your AI assistant to use Archify on this repo, or run \`npx archify-cli generate . --doc-type ${doc.id}\` if you want ${doc.outputFile} now.`;
  } else if (designPacketStale) {
    recommendedAction = "generate";
    summary = `Archify knowledge is ready, but the ${packetLabel} is older than the latest analysis.`;
    nextStep = `Ask your AI assistant to use Archify on this repo so it can refresh ${doc.outputFile}, or run \`npx archify-cli generate . --doc-type ${doc.id}\` manually.`;
  } else if (!finalDocumentExists) {
    recommendedAction = "write";
    summary = `Archify synthesis artifacts are ready, but ${doc.outputFile} has not been written yet.`;
    nextStep = `Ask your AI assistant to use Archify on this repo, or run \`npx archify-cli write . --doc-type ${doc.id}\` if you want the final document now.`;
  } else if (finalDocumentStale) {
    recommendedAction = "write";
    summary = `${doc.outputFile} exists, but it is older than the latest synthesis packet.`;
    nextStep = `Ask your AI assistant to use Archify on this repo so it can refresh ${doc.outputFile}, or run \`npx archify-cli write . --doc-type ${doc.id} --force\` manually.`;
  }

  return {
    command: "status",
    docType: doc.id,
    outputFile: doc.outputFile,
    installed: true,
    repoRoot,
    outputDir,
    outputDirExists,
    analysisReady,
    generatedPacketReady,
    finalDocumentExists,
    finalDocumentStale,
    knowledgeStale,
    designPacketStale,
    recommendedAction,
    summary,
    nextStep,
    config: {
      installMode: config.skillInstall.mode,
      platforms: config.skillInstall.platforms,
      outputDir: outputDirName
    },
    manifest: manifest
      ? {
          status: manifest.status ?? "unknown",
          mode: manifest.mode ?? null,
          targetPath: manifest.targetPath ?? null,
          generatedAt: manifest.generatedAt ?? null
        }
      : null,
    designPacket: designPacket
      ? {
          docType: designPacket.docType ?? doc.id,
          status: designPacket.status ?? "unknown",
          generatedAt: designPacket.generatedAt ?? null
        }
      : null,
    finalDocument: {
      path: finalDocumentPath,
      exists: finalDocumentExists,
      generatedAt: finalDocumentGeneratedAt
    },
    freshness: {
      newestWorkspaceChange,
      manifestGeneratedAt: manifest?.generatedAt ?? null,
      designPacketGeneratedAt: designPacket?.generatedAt ?? null,
      finalDocumentGeneratedAt
    },
    availableArtifacts,
    missingArtifacts,
    synthesisArtifacts: {
      packetPath: synthesis.paths.packet,
      briefPath: synthesis.paths.brief,
      guidePath: synthesis.paths.guide,
      guideBriefPath: synthesis.paths.guideBrief
    }
  };
}
