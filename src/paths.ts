import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

// dist/paths.js -> ../templates (mirrors opengoal's src/templates.ts resolution).
const __dirname = dirname(fileURLToPath(import.meta.url));
export const PACKAGE_ROOT = join(__dirname, "..");
export const TEMPLATE_DIR = join(PACKAGE_ROOT, "templates");

export const SKILL_SRC_DIR = join(TEMPLATE_DIR, "skills", "openillust");
export const COMMANDS_SRC_DIR = join(TEMPLATE_DIR, "commands", "opil");
export const SKILL_NAME = "openillust";
export const COMMAND_PREFIX = "opil";

export interface InstallDirOptions {
  global?: boolean;
  claudeDir?: string;
  codexDir?: string;
}

/**
 * Resolves the Claude Code config directory.
 * --claude-dir always wins. Otherwise --global forces ~/.claude.
 * Otherwise: ./.claude if it already exists in cwd, else ~/.claude.
 */
export function resolveClaudeDir(opts: InstallDirOptions): string {
  if (opts.claudeDir) return resolve(opts.claudeDir);
  if (opts.global) return join(homedir(), ".claude");
  const cwdClaude = join(process.cwd(), ".claude");
  if (existsSync(cwdClaude)) return cwdClaude;
  return join(homedir(), ".claude");
}

export interface CodexDirResolution {
  path: string;
  /** true when this is the default ~/.codex and it does not exist on disk. */
  skip: boolean;
}

/**
 * Resolves the Codex config directory.
 * --codex-dir always wins and is never skipped (explicit request: create if missing).
 * Otherwise the default is ~/.codex; if that does not exist, the caller should
 * skip the Codex install with a notice rather than creating a fresh tree for a
 * tool that is not installed on this machine.
 */
export function resolveCodexDir(opts: InstallDirOptions): CodexDirResolution {
  if (opts.codexDir) {
    return { path: resolve(opts.codexDir), skip: false };
  }
  const def = join(homedir(), ".codex");
  return { path: def, skip: !existsSync(def) };
}
