// Browser A2A client using the official @a2a-js/sdk (ClientFactory), mirroring the
// bob-agents pattern: createFromUrl() discovers the agent via /.well-known/agent-card.json,
// sendMessageStream() yields typed protocol events we render incrementally.

import { ClientFactory } from "@a2a-js/sdk/client";
import type { Client } from "@a2a-js/sdk/client";
import type { MessageSendParams } from "@a2a-js/sdk";

// Full agent-card URL (same origin; Vite proxies /a2a to the FastAPI backend). We pass
// the complete URL with an empty path: createFromUrl(base) would otherwise resolve the
// default card path as new URL("/.well-known/agent-card.json", base) — an absolute path
// that drops the "/a2a" mount and hits the SPA fallback (HTML, not JSON).
const A2A_CARD_URL = `${window.location.origin}/a2a/.well-known/agent-card.json`;

let cached: Promise<Client> | null = null;

function getClient(): Promise<Client> {
  if (!cached) cached = new ClientFactory().createFromUrl(A2A_CARD_URL, "");
  return cached;
}

function buildParams(text: string, contextId?: string): MessageSendParams {
  return {
    message: {
      kind: "message",
      messageId: crypto.randomUUID(),
      role: "user",
      parts: [{ kind: "text", text }],
      ...(contextId ? { contextId } : {}),
    },
  };
}

export interface AgentTrace {
  label: string;
}

export interface AgentStreamResult {
  text: string;
  traces: AgentTrace[];
  appId: string | null;
  appTitle: string | null;
  contextId: string | null;
}

// Stream one user turn; accumulate assistant text, tool-call traces, and any
// compiled-app UI metadata (app_id) surfaced by the compile_prompt tool result.
export async function compileViaAgent(
  prompt: string,
  onUpdate: (partial: AgentStreamResult) => void,
  contextId?: string,
): Promise<AgentStreamResult> {
  const client = await getClient();
  const result: AgentStreamResult = {
    text: "",
    traces: [{ label: "Connected to A2A agent" }],
    appId: null,
    appTitle: null,
    contextId: contextId ?? null,
  };
  onUpdate({ ...result });

  for await (const event of client.sendMessageStream(buildParams(prompt, contextId))) {
    applyEvent(event as unknown as Record<string, unknown>, result);
    onUpdate({ ...result, traces: [...result.traces] });
  }
  return result;
}

function applyEvent(event: Record<string, unknown>, out: AgentStreamResult): void {
  const ctx = (event.contextId ?? event.context_id) as string | undefined;
  if (ctx) out.contextId = ctx;

  const kind = event.kind as string | undefined;
  if (kind === "task") {
    const status = event.status as Record<string, any> | undefined;
    consumeParts(status?.message?.parts, out);
    for (const a of (event.artifacts as any[]) ?? []) consumeParts(a?.parts, out);
  } else if (kind === "status-update") {
    consumeParts((event.status as any)?.message?.parts, out);
  } else if (kind === "artifact-update") {
    consumeParts((event.artifact as any)?.parts, out);
  } else if (kind === "message") {
    consumeParts(event.parts as any[], out);
  }
}

function consumeParts(parts: any[] | undefined, out: AgentStreamResult): void {
  for (const raw of parts ?? []) {
    const part = raw.root ?? raw;
    if (part.kind === "text" || part.type === "text") {
      if (part.metadata?.adk_thought) continue;
      // Some reasoning models (gpt-oss on OpenRouter) reject `reasoning_content` on
      // the post-tool summary turn; skip that provider-error noise — the tool result
      // (the compiled app) is what matters.
      const t: string = part.text ?? "";
      if (/litellm|BadRequestError|OpenrouterException|reasoning_content/i.test(t)) continue;
      if (t) out.text += t;
    } else if (part.kind === "data" || part.type === "data") {
      consumeData(part, out);
    }
  }
}

function consumeData(part: any, out: AgentStreamResult): void {
  const adk = part.metadata?.adk_type;
  const data = part.data ?? {};
  if (adk === "function_call") {
    out.traces.push({ label: `Calling ${data.name ?? "tool"}` });
    return;
  }
  if (adk !== "function_response") return;
  const structured = extractStructured(data);
  if (!structured) return;
  if (structured.app_id) {
    out.appId = structured.app_id as string;
    out.appTitle = (structured.service_title as string) ?? null;
    out.traces.push({ label: `App compiled: ${out.appTitle ?? out.appId}` });
  } else {
    out.traces.push({ label: `Tool result: ${data.name ?? "tool"}` });
  }
}

function extractStructured(data: any): Record<string, any> | null {
  const response = data.response ?? {};
  const candidates = [response.result, response, data.result, data];
  for (const c of candidates) {
    if (c && typeof c === "object" && (c.structuredContent || c.structured_content)) {
      return c.structuredContent ?? c.structured_content;
    }
  }
  return null;
}
