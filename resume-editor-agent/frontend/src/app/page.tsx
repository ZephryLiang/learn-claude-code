"use client";

import { useCallback, useRef, useState } from "react";
import PlanTimeline from "@/components/PlanTimeline";
import GoalInput from "@/components/GoalInput";
import InterceptInput from "@/components/InterceptInput";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import { Button } from "@/components/ui/button";
import { startAgentRun, sendIntercept } from "@/lib/api";
import type { StepState } from "@/components/PlanTimeline";

interface AgentResults {
  [stepId: string]: string;
}

interface AgentThinking {
  [stepId: string]: string;
}

type StepStatus = "idle" | "planning" | "running" | "done" | "error";

export default function Home() {
  const [resumeText, setResumeText] = useState("");
  const [jdText, setJdText] = useState("");
  const [goal, setGoal] = useState("");
  const [stepStatus, setStepStatus] = useState<StepStatus>("idle");
  const [steps, setSteps] = useState<StepState[]>([]);
  const [results, setResults] = useState<AgentResults>({});
  const [thinking, setThinking] = useState<AgentThinking>({});
  const [activeResult, setActiveResult] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Request notification permission on first analysis start
  const requestNotificationPermission = useCallback(() => {
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") {
      Notification.requestPermission().then(setNotificationPermission);
    } else {
      setNotificationPermission(Notification.permission);
    }
  }, []);

  const handleStartAnalysis = useCallback(async () => {
    if (!resumeText.trim() || !jdText.trim()) return;

    // Request notification permission on first click
    requestNotificationPermission();

    setStepStatus("planning");
    setSteps([]);
    setResults({});
    setThinking({});
    setActiveResult(null);
    setError(null);
    setRunId(null);

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      await startAgentRun(resumeText, jdText, goal, (event) => {
        if (abort.signal.aborted) return;

        try {
          const data = JSON.parse(event.data);

          if (event.type === "plan") {
            setRunId(data.run_id);
            setSteps(
              data.steps.map((s: any) => ({
                id: s.id,
                name: s.name,
                icon: s.icon || "📄",
                status: "pending" as const,
              }))
            );
            setStepStatus("running");
          } else if (event.type === "step_start") {
            setSteps((prev) =>
              prev.map((s) =>
                s.id === data.step_id ? { ...s, status: "running" as const } : s
              )
            );
          } else if (event.type === "step_done") {
            setSteps((prev) =>
              prev.map((s) =>
                s.id === data.step_id
                  ? { ...s, status: "done" as const, duration_ms: data.duration_ms }
                  : s
              )
            );
          } else if (event.type === "step_error") {
            setSteps((prev) =>
              prev.map((s) =>
                s.id === data.step_id ? { ...s, status: "error" as const } : s
              )
            );
          } else if (event.type === "message" && data.step_id && data.text != null) {
            // Streaming output via unnamed data: events
            setResults((prev) => ({
              ...prev,
              [data.step_id]: data.text,
            }));
            if (data.thinking != null) {
              setThinking((prev) => ({
                ...prev,
                [data.step_id]: data.thinking,
              }));
            }
          } else if (event.type === "all_done") {
            setStepStatus("done");
            // Browser notification if tab is hidden
            if (document.hidden && "Notification" in window && Notification.permission === "granted") {
              new Notification("简历分析完成", {
                body: `已完成 ${steps.filter(s => s.status === "done").length} 项分析`,
              });
            }
          } else if (event.type === "error") {
            setError(data.error);
            setStepStatus("error");
          }
        } catch { /* skip */ }
      }, abort.signal);
    } catch (e: any) {
      if (e.name !== "AbortError") {
        setError(e.message || "Agent run failed");
        setStepStatus("error");
      }
    }
  }, [resumeText, jdText, goal, requestNotificationPermission, steps]);

  const handleIntercept = useCallback(
    async (stepId: string, feedback: string) => {
      if (!runId) return;
      setSteps((prev) =>
        prev.map((s) =>
          s.id === stepId ? { ...s, status: "revising" as const } : s
        )
      );

      try {
        await sendIntercept(runId, stepId, feedback, (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.text != null) {
              setResults((prev) => ({ ...prev, [stepId]: data.text }));
            }
          } catch { /* skip */ }
        });
        setSteps((prev) =>
          prev.map((s) =>
            s.id === stepId ? { ...s, status: "done" as const } : s
          )
        );
      } catch {
        setSteps((prev) =>
          prev.map((s) =>
            s.id === stepId ? { ...s, status: "error" as const } : s
          )
        );
      }
    },
    [runId]
  );

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between px-5 h-13 border-b border-border bg-background/80 backdrop-blur-sm shrink-0">
        <h1 className="font-heading text-base tracking-tight text-foreground">
          Resume AI Agent
        </h1>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-10 pb-32 px-6 space-y-6">
          {/* Resume input */}
          <section>
            <label className="text-sm font-medium text-foreground block mb-2">
              简历内容
            </label>
            <textarea
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="粘贴简历内容..."
              rows={6}
              className="w-full bg-secondary border border-border rounded-lg p-4 text-sm font-mono resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring placeholder:text-muted-foreground/40"
            />
          </section>

          {/* JD input */}
          <section>
            <label className="text-sm font-medium text-foreground block mb-2">
              目标岗位描述 (JD)
            </label>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="粘贴岗位描述..."
              rows={4}
              className="w-full bg-secondary border border-border rounded-lg p-4 text-sm resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring placeholder:text-muted-foreground/40"
            />
          </section>

          {/* Goal input */}
          <GoalInput onSubmit={setGoal} disabled={stepStatus === "running" || stepStatus === "planning"} />

          {/* Start button */}
          <Button
            onClick={handleStartAnalysis}
            disabled={!resumeText.trim() || !jdText.trim() || stepStatus === "running" || stepStatus === "planning"}
            size="lg"
            className="w-full"
          >
            {stepStatus === "planning"
              ? "正在规划..."
              : stepStatus === "running"
              ? "分析中..."
              : "开始分析"}
          </Button>

          {/* Error */}
          {error && (
            <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3">
              <p className="text-xs text-destructive">{error}</p>
            </div>
          )}

          {/* Plan timeline */}
          {steps.length > 0 && (
            <PlanTimeline
              steps={steps}
              results={results}
              thinking={thinking}
              activeTab={activeResult}
              onStepClick={setActiveResult}
              onIntercept={handleIntercept}
            />
          )}

          {/* Step result detail */}
          {activeResult && results[activeResult] && (
            <section>
              <h2 className="text-sm font-medium text-foreground mb-3">
                分析结果
              </h2>
              <div className="bg-card border border-border rounded-lg p-5">
                <MarkdownRenderer
                  content={results[activeResult] || ""}
                  thinking={thinking[activeResult] || undefined}
                />
                <InterceptInput
                  stepId={activeResult}
                  stepName={steps.find((s) => s.id === activeResult)?.name || activeResult}
                  onSubmit={handleIntercept}
                />
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
