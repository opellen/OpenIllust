import { existsSync, mkdirSync, writeFileSync, readFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";

const WORKSPACE_SUBDIRS = ["anchors", "refs", "sheets", "plans", "icons", "preview"] as const;

export interface InitSummary {
  campaignDir: string;
  dirsCreated: string[];
  noteFile: string;
  envFile: { path: string; created: boolean };
  gitignoreFile: { path: string; created: boolean; updated: boolean };
}

export class InvalidCampaignNameError extends Error {}

function assertValidName(name: string): void {
  if (!name || !name.trim()) {
    throw new InvalidCampaignNameError("Campaign name must not be empty.");
  }
  if (/[\\/]/.test(name) || name === "." || name === "..") {
    throw new InvalidCampaignNameError(`Invalid campaign name "${name}": must be a single path segment.`);
  }
}

function noteContent(name: string): string {
  return `# Campaign: ${name}

This workspace was scaffolded by \`openillust init\`. It does not yet have a
design contract (campaign.yaml).

This CLI only scaffolds folders -- it does not distill a design guide into a
contract. To do that, open this project in Claude Code or Codex (whichever
you installed \`openillust\` into) and run:

    /opil:init ${name}

That command loads the openillust skill, walks you through the design-guide
distillation, and writes campaigns/${name}/campaign.yaml on your approval.
`;
}

/**
 * Scaffolds a campaign workspace under <cwd>/.openillust/campaigns/<name>/
 * and ensures .env / .gitignore exist in the project root. Idempotent:
 * running twice never duplicates content or clobbers an existing .env.
 */
export function runInit(name: string, cwd: string = process.cwd()): InitSummary {
  assertValidName(name);

  const campaignDir = join(cwd, ".openillust", "campaigns", name);
  const dirsCreated: string[] = [];
  for (const sub of WORKSPACE_SUBDIRS) {
    const dir = join(campaignDir, sub);
    mkdirSync(dir, { recursive: true });
    const gitkeep = join(dir, ".gitkeep");
    if (!existsSync(gitkeep)) {
      writeFileSync(gitkeep, "", "utf8");
    }
    dirsCreated.push(dir);
  }

  const noteFile = join(campaignDir, "README.md");
  writeFileSync(noteFile, noteContent(name), "utf8");

  // .env: create with a placeholder if absent; never touch or print an
  // existing one.
  const envPath = join(cwd, ".env");
  let envCreated = false;
  if (!existsSync(envPath)) {
    writeFileSync(
      envPath,
      "# Needed only for the recraft vectorizer (the default; best quality, ~$0.01/image).\n" +
        "# Leave empty to run keyless with the local vtracer provider (tooling.vectorizer: vtracer).\n" +
        "RECRAFT_API_KEY=\n",
      "utf8",
    );
    envCreated = true;
  }

  // .gitignore: ensure it ignores .env. .openillust/ is intentionally left
  // out -- campaign data is meant to be committed by the user.
  const gitignorePath = join(cwd, ".gitignore");
  let gitignoreCreated = false;
  let gitignoreUpdated = false;
  if (!existsSync(gitignorePath)) {
    writeFileSync(gitignorePath, ".env\n", "utf8");
    gitignoreCreated = true;
  } else {
    const content = readFileSync(gitignorePath, "utf8");
    const hasEnvLine = content.split(/\r?\n/).some((line) => line.trim() === ".env");
    if (!hasEnvLine) {
      const sep = content.length === 0 || content.endsWith("\n") ? "" : "\n";
      appendFileSync(gitignorePath, `${sep}.env\n`, "utf8");
      gitignoreUpdated = true;
    }
  }

  return {
    campaignDir,
    dirsCreated,
    noteFile,
    envFile: { path: envPath, created: envCreated },
    gitignoreFile: { path: gitignorePath, created: gitignoreCreated, updated: gitignoreUpdated },
  };
}
