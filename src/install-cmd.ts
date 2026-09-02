import { existsSync, mkdirSync, readdirSync, writeFileSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { copyTree } from "./fs-copy.js";
import { convertToCodexPrompt } from "./codex-prompt.js";
import { checkPythonVersion, installRequirements } from "./python-check.js";
import {
  SKILL_SRC_DIR,
  COMMANDS_SRC_DIR,
  SKILL_NAME,
  COMMAND_PREFIX,
  resolveClaudeDir,
  resolveCodexDir,
  type InstallDirOptions,
} from "./paths.js";

export interface InstallOptions extends InstallDirOptions {
  skipPython?: boolean;
}

export interface InstallSummary {
  claudeDir: string;
  claudeSkillFiles: string[];
  claudeCommandFiles: string[];
  codex: {
    attempted: boolean;
    skippedReason?: string;
    dir?: string;
    skillFiles?: string[];
    promptFiles?: string[];
  };
  python: {
    checked: boolean;
    found: boolean;
    ok: boolean;
    version?: string;
    warning?: string;
    pip?: { attempted: boolean; success: boolean; message: string };
  };
}

function listCommandNames(): string[] {
  return readdirSync(COMMANDS_SRC_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((f) => f.replace(/\.md$/, ""))
    .sort();
}

export function runInstall(opts: InstallOptions): InstallSummary {
  const commandNames = listCommandNames();

  // --- Claude Code ---
  const claudeDir = resolveClaudeDir(opts);
  mkdirSync(claudeDir, { recursive: true });

  const claudeSkillDest = join(claudeDir, "skills", SKILL_NAME);
  const claudeSkillFiles = copyTree(SKILL_SRC_DIR, claudeSkillDest);

  const claudeCommandsDest = join(claudeDir, "commands", COMMAND_PREFIX);
  mkdirSync(claudeCommandsDest, { recursive: true });
  const claudeCommandFiles: string[] = [];
  for (const name of commandNames) {
    const src = join(COMMANDS_SRC_DIR, `${name}.md`);
    const dest = join(claudeCommandsDest, `${name}.md`);
    writeFileSync(dest, readFileSync(src, "utf8"), "utf8");
    claudeCommandFiles.push(dest);
  }

  // --- Codex ---
  const codexResolution = resolveCodexDir(opts);
  const codex: InstallSummary["codex"] = { attempted: false };
  if (codexResolution.skip) {
    codex.attempted = false;
    codex.skippedReason = `Codex directory not found (${codexResolution.path}); skipping Codex install. Pass --codex-dir to install anyway.`;
  } else {
    mkdirSync(codexResolution.path, { recursive: true });
    const codexSkillDest = join(codexResolution.path, "skills", SKILL_NAME);
    const codexSkillFiles = copyTree(SKILL_SRC_DIR, codexSkillDest);

    const promptsDest = join(codexResolution.path, "prompts");
    mkdirSync(promptsDest, { recursive: true });
    const promptFiles: string[] = [];
    for (const name of commandNames) {
      const src = join(COMMANDS_SRC_DIR, `${name}.md`);
      const raw = readFileSync(src, "utf8");
      const converted = convertToCodexPrompt(name, raw);
      const dest = join(promptsDest, `${COMMAND_PREFIX}-${name}.md`);
      writeFileSync(dest, converted, "utf8");
      promptFiles.push(dest);
    }

    codex.attempted = true;
    codex.dir = codexResolution.path;
    codex.skillFiles = codexSkillFiles;
    codex.promptFiles = promptFiles;
  }

  // --- Python prerequisite ---
  const python: InstallSummary["python"] = { checked: true, found: false, ok: false };
  const versionResult = checkPythonVersion();
  python.found = versionResult.found;
  python.ok = versionResult.ok;
  python.version = versionResult.version;
  if (!versionResult.found) {
    python.warning = "python was not found on PATH. Install Python >=3.10 to run the skill's scripts.";
  } else if (!versionResult.ok) {
    python.warning = `python ${versionResult.version ?? versionResult.raw ?? "?"} found, but >=3.10 is required.`;
  }

  if (!opts.skipPython) {
    // Prefer the requirements.txt we just installed for Claude; fall back to
    // Codex's copy, then the source template, so this still works if only
    // one target was installed.
    const candidates = [
      join(claudeSkillDest, "requirements.txt"),
      codex.dir ? join(codex.dir, "skills", SKILL_NAME, "requirements.txt") : undefined,
      join(SKILL_SRC_DIR, "requirements.txt"),
    ].filter((p): p is string => Boolean(p) && existsSync(p as string));
    const reqPath = candidates[0];
    if (reqPath) {
      python.pip = installRequirements(reqPath);
    } else {
      python.pip = { attempted: false, success: false, message: "requirements.txt not found in any installed location" };
    }
  }

  return {
    claudeDir,
    claudeSkillFiles: claudeSkillFiles.map((f) => join(claudeSkillDest, f)),
    claudeCommandFiles,
    codex,
    python,
  };
}
