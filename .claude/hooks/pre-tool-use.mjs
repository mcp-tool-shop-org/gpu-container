#!/usr/bin/env node
/**
 * Wedge #1 PreToolUse hook — Tool-Call Conformance ADVISORY (deterministic floor; advisory + fail-open).
 * gpu-container is a Python repo with no role-os dependency, so the floor is imported from the sibling
 * role-os checkout by ABSOLUTE path (rig-specific: E:/AI/role-os). This reads
 * .claude/role-os/tool-contracts.json from the session cwd, runs the schema + computable contract floor
 * against the proposed call, and — only when the floor PROVES a violation — injects an advisory into context
 * via the Claude Code hook protocol ({hookSpecificOutput:{hookEventName:"PreToolUse", additionalContext}}).
 * It NEVER blocks (always exit 0) and NEVER throws — any error (incl. a missing role-os checkout) is a
 * silent no-op, because a hook must not break a tool call.
 */
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const ROLE_OS_HOOKS = "E:/AI/role-os/src/hooks.mjs"; // rig-specific sibling checkout

let input = {};
try { input = JSON.parse(readFileSync(0, "utf-8").toString() || "{}"); } catch { /* no stdin */ }

try {
  const { conformanceAdvisory } = await import(pathToFileURL(ROLE_OS_HOOKS).href);
  const note = conformanceAdvisory(input.cwd || process.cwd(), input.tool_name || "", input.tool_input);
  if (note) {
    console.log(JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", additionalContext: note },
    }));
  }
} catch { /* role-os checkout not present, or internal error -> no-op (never block a tool call) */ }

process.exit(0);
