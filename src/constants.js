import os from "node:os";
import path from "node:path";

export const CONFIG_FILE = "archify.config.json";
export const IGNORE_FILE = ".archifyignore";
export const OUTPUT_DIR = ".archify";
export const PROJECT_SKILL_DIR = path.join(".agents", "skills", "archify");
export const PROJECT_CLAUDE_SKILL_DIR = path.join(".claude", "skills", "archify");
export const SKILL_TEMPLATE_VERSION = 1;
export const INSTALL_MODES = ["project", "global"];
export const INSTALL_PLATFORMS = ["codex", "claude-code"];
export const SHARED_INSTALL_PLATFORM = "shared";
export const SHARED_INSTALL_PLATFORMS = ["codex", "claude-code"];
export const INSTALL_PLATFORM_ALIASES = {
  both: INSTALL_PLATFORMS,
  all: INSTALL_PLATFORMS,
  claude: ["claude-code"],
  "claude code": ["claude-code"]
};

export const RESERVED_ARTIFACTS = [
  "graph.json",
  "GRAPH_REPORT.md",
  "facts.json",
  "modules.json",
  "routes.json",
  "database.json",
  "services.json",
  "dependencies.json",
  "docs-summary.json",
  "architecture-context.json",
  "architecture-context.md"
];

export const REQUIRED_GENERATE_ARTIFACTS = [
  "graph.json",
  "facts.json",
  "modules.json",
  "routes.json",
  "database.json",
  "services.json",
  "dependencies.json",
  "docs-summary.json",
  "architecture-context.json",
  "architecture-context.md"
];

export const OPERATIONAL_ARTIFACTS = [
  "manifest.json"
];

export const SYNTHESIS_ARTIFACTS = [
  "design-packet.json",
  "design-brief.md",
  "archify.guide.json",
  "archify.guide.md"
];

export const ALL_ANALYSIS_ARTIFACTS = [
  ...RESERVED_ARTIFACTS,
  ...OPERATIONAL_ARTIFACTS,
  ...SYNTHESIS_ARTIFACTS
];

export const DEFAULT_CONFIG = {
  project: {
    name: "",
    description: ""
  },
  defaults: {
    sourceRoot: ".",
    outputDir: OUTPUT_DIR
  },
  skillInstall: {
    mode: "project",
    platform: "codex",
    platforms: ["codex"],
    installedAt: null,
    version: SKILL_TEMPLATE_VERSION,
    target: null,
    targets: []
  },
  analysis: {
    enabled: true,
    pipeline: {
      detect: true,
      extract: true,
      build: true,
      cluster: true,
      analyze: true,
      export: true
    },
    detect: {
      followSymlinks: false,
      includeHidden: false,
      maxFileSizeBytes: 1024 * 1024,
      includeGlobs: [],
      excludeGlobs: []
    },
    semantic: {
      enabled: false,
      mode: "docs_first",
      includeFileTypes: ["document"],
      includeExtensions: [".md", ".mdx", ".txt", ".rst"],
      maxDocumentBytes: 262144,
      maxChunksPerDocument: 32,
      maxChunkBytes: 8192,
      backend: "none"
    }
  },
  languageScope: {
    include: [],
    exclude: []
  }
};

export const DEFAULT_IGNORE_LINES = [
  "# Archify ignore rules",
  ".git/",
  "node_modules/",
  ".venv/",
  ".archify/",
  "dist/",
  "build/"
];

export function getSharedGlobalSkillDir() {
  const homeDir = process.env.HOME || os.homedir();
  return path.join(homeDir, ".agents", "skills", "archify");
}
