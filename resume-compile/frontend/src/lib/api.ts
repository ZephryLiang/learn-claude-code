const BASE = "http://localhost:8000";

// ── Models ─────────────────────────────────────────────────────────────

export interface ModelInfo {
  id: string;
  name: string;
  default: boolean;
  base_url: string;
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${BASE}/api/models`);
  if (!res.ok) throw new Error("Failed to fetch models");
  const data = await res.json();
  return data.models;
}

export async function validateModel(api_key: string, base_url: string, model_id: string): Promise<{ valid: boolean; response: string }> {
  const fd = new FormData();
  fd.append("api_key", api_key);
  fd.append("base_url", base_url);
  fd.append("model_id", model_id);
  const res = await fetch(`${BASE}/api/models/validate`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Validation failed");
  return res.json();
}

export async function addModel(api_key: string, base_url: string, model_id: string): Promise<any> {
  const fd = new FormData();
  fd.append("api_key", api_key);
  fd.append("base_url", base_url);
  fd.append("model_id", model_id);
  const res = await fetch(`${BASE}/api/models/add`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Add model failed");
  return res.json();
}

export async function deleteModel(modelId: string): Promise<void> {
  await fetch(`${BASE}/api/models/${encodeURIComponent(modelId)}`, { method: "DELETE" });
}

// ── Resume ─────────────────────────────────────────────────────────────

export async function parseResume(file: File): Promise<{
  filename: string; saved_name: string; text: string; type: string; file_url: string;
}> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/api/parse`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Parse failed");
  return res.json();
}

export async function analyzeGaps(resumeText: string, jdText: string, modelId = ""): Promise<{ analysis: string; thinking: string; truncated: boolean }> {
  const fd = new FormData();
  fd.append("resume_text", resumeText);
  fd.append("jd_text", jdText);
  fd.append("model_id", modelId);
  const res = await fetch(`${BASE}/api/analyze`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Analysis failed");
  return res.json();
}

export async function assessResume(resumeText: string, jdText: string, modelId = ""): Promise<{ assessment: string; thinking: string; truncated: boolean }> {
  const fd = new FormData();
  fd.append("resume_text", resumeText);
  fd.append("jd_text", jdText);
  fd.append("model_id", modelId);
  const res = await fetch(`${BASE}/api/assess`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Assessment failed");
  return res.json();
}

export async function remediateGaps(resumeText: string, jdText: string, modelId = ""): Promise<{ plan: string; thinking: string; truncated: boolean }> {
  const fd = new FormData();
  fd.append("resume_text", resumeText);
  fd.append("jd_text", jdText);
  fd.append("model_id", modelId);
  const res = await fetch(`${BASE}/api/remediate`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Remediation failed");
  return res.json();
}

export async function rewriteResume(
  resumeText: string, jdText: string,
  section = "all", instruction = "", modelId = ""
): Promise<{ rewritten: string; thinking: string; truncated: boolean }> {
  const fd = new FormData();
  fd.append("resume_text", resumeText);
  fd.append("jd_text", jdText);
  fd.append("section", section);
  fd.append("instruction", instruction);
  fd.append("model_id", modelId);
  const res = await fetch(`${BASE}/api/rewrite`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Rewrite failed");
  return res.json();
}

/** Stream analysis result as NDJSON. Calls onChunk for each delta. */
export async function streamAnalysis(
  type: string,
  resumeText: string,
  jdText: string,
  modelId: string,
  onChunk: (data: { text: string; thinking: string; done: boolean; truncated?: boolean; error?: string }) => void,
  signal?: AbortSignal,
): Promise<void> {
  const fd = new FormData();
  fd.append("type", type);
  fd.append("resume_text", resumeText);
  fd.append("jd_text", jdText);
  fd.append("model_id", modelId);
  if (type === "rewrite") {
    fd.append("section", "all");
    fd.append("instruction", "");
  }
  const res = await fetch(`${BASE}/api/stream`, { method: "POST", body: fd, signal });
  if (!res.ok) throw new Error((await res.json()).detail || "Stream failed");
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try { onChunk(JSON.parse(line)); } catch { /* skip malformed */ }
    }
  }
}

export async function compileLatex(latex: string): Promise<Blob> {
  const fd = new FormData();
  fd.append("latex", latex);
  const res = await fetch(`${BASE}/api/compile`, { method: "POST", body: fd });
  if (!res.ok) throw new Error((await res.json()).detail || "Compilation failed");
  return res.blob();
}
