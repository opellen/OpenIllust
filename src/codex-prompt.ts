/**
 * Minimal flat front-matter reader for our command templates, which only
 * ever use simple `key: value` scalars (no nesting, no arrays). Values may
 * optionally be wrapped in double quotes (e.g. argument-hint: "[name]") —
 * quotes are stripped when present.
 */
export function parseFrontMatter(content: string): { meta: Record<string, string>; body: string } {
  const normalized = content.replace(/\r\n/g, "\n");
  const match = normalized.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!match) {
    return { meta: {}, body: normalized };
  }
  const meta: Record<string, string> = {};
  for (const line of match[1].split("\n")) {
    const m = line.match(/^([\w-]+):\s*(.*)$/);
    if (!m) continue;
    const value = m[2].trim().replace(/^"(.*)"$/, "$1").replace(/^'(.*)'$/, "$1");
    meta[m[1]] = value;
  }
  const body = normalized.slice(match[0].length);
  return { meta, body };
}

/**
 * Converts a Claude-style command template into a Codex custom-prompt file.
 *
 * Observed local convention (real ~/.codex/prompts files from other plugins):
 * Codex prompt files keep the YAML front-matter (description, argument-hint)
 * verbatim, exactly like Claude command files — the loader parses it. So the
 * conversion is a verbatim copy; only the FILENAME changes (opil-<name>.md,
 * since ':' is not filename-safe), which makes the Codex invocation
 * /opil-<name> rather than /opil:<name>.
 */
export function convertToCodexPrompt(_name: string, rawContent: string): string {
  return rawContent.replace(/\r\n/g, "\n");
}
