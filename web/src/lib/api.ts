// REST client (same-origin via the Vite proxy). The deterministic compile path and
// the signature surface / correction / optimize endpoints.

export interface FieldWidget {
  name: string;
  label: string;
  widget: string;
  description: string;
  default: unknown;
  required: boolean;
  options: string[];
}

export interface AppSpec {
  app_id: string;
  task_name: string;
  title: string;
  description: string;
  inputs: any[];
  outputs: any[];
  constraints: string[];
  source_prompt: string;
}

export interface Surface {
  app_id: string;
  task_name: string;
  title: string;
  description: string;
  constraints: string[];
  fields: FieldWidget[];
  outputs: FieldWidget[];
  values: Record<string, unknown>;
  spec: AppSpec;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`${res.status}: ${(await res.text()).slice(0, 300)}`);
  return res.json() as Promise<T>;
}

export interface AppMatch {
  app_id: string;
  title: string;
  task_name: string;
  score: number;
  source_prompt: string;
}

export async function retrieveSimilar(prompt: string): Promise<AppMatch[]> {
  const { matches } = await post<{ matches: AppMatch[] }>("/api/retrieve", { prompt });
  return matches;
}

export async function compileViaRest(prompt: string): Promise<{ app_id: string }> {
  const structured = await post<{ app_id: string }>("/api/compile", { prompt });
  return structured;
}

export async function getSurface(appId: string): Promise<Surface> {
  const res = await fetch(`/api/apps/${appId}`);
  if (!res.ok) throw new Error(`surface ${res.status}`);
  return res.json();
}

export async function saveCorrection(appId: string, app: AppSpec): Promise<void> {
  await post(`/api/apps/${appId}/correct`, { app });
}

export async function optimizeInducer(): Promise<{ message: string; compiled: boolean }> {
  return post("/api/optimize");
}
