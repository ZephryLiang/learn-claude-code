const BASE = "http://localhost:8001";

/** Stream agent execution via SSE. Calls onEvent for each event. */
export async function startAgentRun(
  resumeText: string,
  jdText: string,
  goal: string,
  onEvent: (event: MessageEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const fd = new FormData();
  fd.append("resume_text", resumeText);
  fd.append("jd_text", jdText);
  fd.append("goal", goal);

  const res = await fetch(`${BASE}/api/agent`, { method: "POST", body: fd, signal });
  if (!res.ok) throw new Error("Agent run failed");

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          onEvent(new MessageEvent(eventType, { data: JSON.stringify(data) }));
        } catch { /* skip malformed */ }
        eventType = "message";
      }
    }
  }
}

/** Send intercept feedback for a completed step. */
export async function sendIntercept(
  runId: string,
  stepId: string,
  feedback: string,
  onEvent: (event: MessageEvent) => void,
): Promise<void> {
  const fd = new FormData();
  fd.append("run_id", runId);
  fd.append("step_id", stepId);
  fd.append("feedback", feedback);

  const res = await fetch(`${BASE}/api/intercept`, { method: "POST", body: fd });
  if (!res.ok) throw new Error("Intercept failed");

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
      if (line.startsWith("data: ")) {
        try {
          onEvent(new MessageEvent("step_revised", { data: line.slice(6) }));
        } catch { /* skip */ }
      }
    }
  }
}
