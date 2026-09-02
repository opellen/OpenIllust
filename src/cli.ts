#!/usr/bin/env node

import { runInstall, type InstallOptions } from "./install-cmd.js";
import { runInit, InvalidCampaignNameError } from "./init-cmd.js";

function printUsage(): void {
  console.log(`
openillust - Campaign-driven vector asset production.

Usage:
  openillust install [options]
  openillust init <campaign-name>

Install options:
  --global              Install into ~/.claude instead of ./.claude
  --claude-dir <path>   Override the Claude Code config directory
  --codex-dir <path>    Override the Codex config directory
  --skip-python         Skip the Python prerequisite check and pip install
  -h, --help            Show this help

Commands:
  install     Install the openillust skill and /opil:* commands/prompts
  init        Scaffold a new campaign workspace (.openillust/campaigns/<name>/)
`);
}

interface ParsedArgs {
  command: string | null;
  positional: string[];
  install: InstallOptions;
  help: boolean;
}

function parseArgs(argv: string[]): ParsedArgs {
  let command: string | null = null;
  const positional: string[] = [];
  const install: InstallOptions = {};
  let help = false;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      help = true;
    } else if (arg === "--global") {
      install.global = true;
    } else if (arg === "--claude-dir") {
      const next = argv[++i];
      if (!next) {
        console.error("Error: --claude-dir requires a directory path");
        process.exit(1);
      }
      install.claudeDir = next;
    } else if (arg === "--codex-dir") {
      const next = argv[++i];
      if (!next) {
        console.error("Error: --codex-dir requires a directory path");
        process.exit(1);
      }
      install.codexDir = next;
    } else if (arg === "--skip-python") {
      install.skipPython = true;
    } else if (!arg.startsWith("-")) {
      if (command === null) {
        command = arg;
      } else {
        positional.push(arg);
      }
    } else {
      console.error(`Unknown option: ${arg}`);
      printUsage();
      process.exit(1);
    }
  }

  return { command, positional, install, help };
}

function cmdInstall(opts: InstallOptions): void {
  const summary = runInstall(opts);

  console.log("openillust install\n");

  console.log(`Claude Code (${summary.claudeDir}):`);
  console.log(`  + skill: ${summary.claudeSkillFiles.length} file(s) -> skills/openillust/`);
  console.log(`  + commands: ${summary.claudeCommandFiles.length} file(s) -> commands/opil/`);

  console.log("");
  if (summary.codex.attempted) {
    console.log(`Codex (${summary.codex.dir}):`);
    console.log(`  + skill: ${summary.codex.skillFiles?.length ?? 0} file(s) -> skills/openillust/`);
    console.log(`  + prompts: ${summary.codex.promptFiles?.length ?? 0} file(s) -> prompts/opil-*.md`);
  } else {
    console.log(`Codex: skipped - ${summary.codex.skippedReason}`);
  }

  console.log("");
  if (!summary.python.found) {
    console.log("Python: [WARN] not found on PATH.");
    if (summary.python.warning) console.log(`  ${summary.python.warning}`);
  } else if (!summary.python.ok) {
    console.log(`Python: [WARN] ${summary.python.version ?? "unknown version"} (>=3.10 required).`);
  } else {
    console.log(`Python: [OK] ${summary.python.version}`);
  }
  if (summary.python.pip) {
    if (summary.python.pip.success) {
      console.log("  pip install -r requirements.txt: [OK]");
    } else {
      console.log(`  pip install -r requirements.txt: [WARN] ${summary.python.pip.message}`);
    }
  } else {
    console.log("  pip install -r requirements.txt: skipped (--skip-python)");
  }

  console.log("\nDone.");
}

function cmdInit(name: string | undefined): void {
  if (!name) {
    console.error("Error: openillust init requires a campaign name");
    printUsage();
    process.exit(1);
  }

  try {
    const summary = runInit(name);
    console.log("openillust init\n");
    console.log(`Campaign workspace: ${summary.campaignDir}`);
    for (const dir of summary.dirsCreated) {
      console.log(`  + ${dir}`);
    }
    console.log(`  + ${summary.noteFile}`);

    console.log("");
    console.log(summary.envFile.created ? `+ ${summary.envFile.path} (created with RECRAFT_API_KEY placeholder)` : `~ ${summary.envFile.path} (already present, left untouched)`);
    if (summary.gitignoreFile.created) {
      console.log(`+ ${summary.gitignoreFile.path} (created, ignores .env)`);
    } else if (summary.gitignoreFile.updated) {
      console.log(`~ ${summary.gitignoreFile.path} (added .env)`);
    } else {
      console.log(`~ ${summary.gitignoreFile.path} (already ignores .env)`);
    }

    console.log(`\nNext: run /opil:init ${name} in Claude Code or Codex to distill the design guide.`);
  } catch (err) {
    if (err instanceof InvalidCampaignNameError) {
      console.error(`Error: ${err.message}`);
      process.exit(1);
    }
    throw err;
  }
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));

  if (args.help || !args.command) {
    printUsage();
    process.exit(args.help ? 0 : 1);
  }

  if (args.command === "install") {
    cmdInstall(args.install);
    return;
  }

  if (args.command === "init") {
    cmdInit(args.positional[0]);
    return;
  }

  console.error(`Unknown command: ${args.command}`);
  printUsage();
  process.exit(1);
}

main();
