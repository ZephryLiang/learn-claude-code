"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PlanTimeline from "@/components/PlanTimeline";
import GoalInput from "@/components/GoalInput";
import InterceptInput from "@/components/InterceptInput";
import ModelSelector from "@/components/ModelSelector";
import ResultTabs from "@/components/ResultTabs";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import { Button } from "@/components/ui/button";
import { startAgentRun, sendIntercept, fetchModels } from "@/lib/api";
import type { StepState } from "@/components/PlanTimeline";
import type { TabInfo } from "@/components/ResultTabs";
import type { ModelOption } from "@/lib/api";

interface ApiStep {
  id: string;
  name: string;
  icon?: string;
}

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
  const [planReasoning, setPlanReasoning] = useState<string | null>(null);
  const [planThinking, setPlanThinking] = useState<string | null>(null);
  const [modelId, setModelId] = useState("deepseek-v4-flash");
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
  const [openTabs, setOpenTabs] = useState<TabInfo[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const stepsRef = useRef<StepState[]>([]);

  // Keep ref in sync with steps state
  useEffect(() => {
    stepsRef.current = steps;
  }, [steps]);

  // Fetch available models on mount
  useEffect(() => {
    fetchModels()
      .then(setAvailableModels)
      .catch(() => {
        setAvailableModels([
          { id: "deepseek-v4-flash", name: "DeepSeek V4 Flash (default)" },
          { id: "deepseek-v4-pro", name: "DeepSeek V4 Pro" },
          { id: "deepseek-v3-0324", name: "DeepSeek V3" },
          { id: "deepseek-r1-0528", name: "DeepSeek R1" },
        ]);
      });
  }, []);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // Request notification permission on first analysis start
  const requestNotificationPermission = useCallback(() => {
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  const handleCloseTab = useCallback(
    (stepId: string) => {
      setOpenTabs((prev) => {
        const newTabs = prev.filter((t) => t.stepId !== stepId);
        if (newTabs.length === 0) {
          setActiveResult(null);
        } else if (activeResult === stepId) {
          setActiveResult(newTabs[newTabs.length - 1].stepId);
        }
        return newTabs;
      });
    },
    [activeResult]
  );

  const handleStepClick = useCallback(
    (stepId: string) => {
      setOpenTabs((prev) => {
        if (prev.some((t) => t.stepId === stepId)) return prev;
        const stepInfo = steps.find((s) => s.id === stepId);
        return [
          ...prev,
          {
            stepId,
            stepName: stepInfo?.name || stepId,
            icon: stepInfo?.icon || "📄",
          },
        ];
      });
      setActiveResult(stepId);
    },
    [steps]
  );

  const handleStartAnalysis = useCallback(async () => {
    if (!resumeText.trim() || !jdText.trim()) return;

    requestNotificationPermission();

    setStepStatus("planning");
    setSteps([]);
    setResults({});
    setThinking({});
    setActiveResult(null);
    setRunId(null);
    setError(null);
    setPlanReasoning(null);
    setPlanThinking(null);
    setOpenTabs([]);

    abortRef.current?.abort();
    const abort = new AbortController();
    abortRef.current = abort;

    try {
      await startAgentRun(resumeText, jdText, goal, modelId, (event) => {
        if (abort.signal.aborted) return;

        try {
          const data = JSON.parse(event.data);

          if (event.type === "plan_start") {
            setRunId(data.run_id);
          } else if (event.type === "plan_thinking") {
            setPlanThinking(data.text);
          } else if (event.type === "plan_reasoning") {
            setRunId(data.run_id);
            const r = data.reasoning || "根据简历和岗位要求选择了以下分析任务，但由于模型返回格式限制，详细分析不可用。";
            setPlanReasoning(r);
            setSteps(
              data.steps.map((s: ApiStep) => ({
                id: s.id,
                name: s.name,
                icon: s.icon || "📄",
                status: "pending" as const,
              }))
            );
          } else if (event.type === "plan") {
            setRunId(data.run_id);
            setSteps(
              data.steps.map((s: ApiStep) => ({
                id: s.id,
                name: s.name,
                icon: s.icon || "📄",
                status: "pending" as const,
              }))
            );
            setStepStatus("running");
          } else if (event.type === "step_compiled") {
            setSteps((prev) =>
              prev.map((s) =>
                s.id === data.step_id ? { ...s, status: "running" as const } : s
              )
            );
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
            // Auto-open tab for this step if not already open
            setOpenTabs((prev) => {
              if (prev.some((t) => t.stepId === data.step_id)) return prev;
              const stepInfo = stepsRef.current.find((s) => s.id === data.step_id);
              return [
                ...prev,
                {
                  stepId: data.step_id,
                  stepName: stepInfo?.name || data.step_id,
                  icon: stepInfo?.icon || "📄",
                },
              ];
            });
            // Auto-select first step that produces content
            setActiveResult((prev) => prev || data.step_id);
          } else if (event.type === "all_done") {
            setStepStatus("done");
            const resultCount = Object.keys(data.results || {}).length;
            if (document.hidden && "Notification" in window && Notification.permission === "granted") {
              new Notification("简历分析完成", {
                body: `已完成 ${resultCount} 项分析`,
              });
            }
          } else if (event.type === "error") {
            setError(data.error);
            setStepStatus("error");
          }
        } catch (err) {
          if (process.env.NODE_ENV === "development") {
            console.warn("SSE event skipped:", event.type, err);
          }
        }
      }, abort.signal);
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Agent run failed");
      setStepStatus("error");
    }
  }, [resumeText, jdText, goal, modelId, requestNotificationPermission]);

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
          } catch (err) {
            if (process.env.NODE_ENV === "development") {
              console.warn("Intercept event skipped:", event.type, err);
            }
          }
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

      <div className="flex flex-1 overflow-hidden">
        {/* ── LEFT PANEL: Inputs ── */}
        <aside className="w-[35%] min-w-[320px] max-w-[480px] border-r border-border overflow-y-auto shrink-0">
          <div className="p-5 space-y-5">
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

            <GoalInput
              onSubmit={setGoal}
              disabled={stepStatus === "running" || stepStatus === "planning"}
            />

            <ModelSelector
              value={modelId}
              onChange={(v) => v && setModelId(v)}
              models={availableModels}
            />

            <Button
              onClick={handleStartAnalysis}
              disabled={
                !resumeText.trim() ||
                !jdText.trim() ||
                stepStatus === "running" ||
                stepStatus === "planning"
              }
              size="lg"
              className="w-full"
            >
              {stepStatus === "planning"
                ? "正在分析简历和岗位要求..."
                : stepStatus === "running"
                ? "分析中..."
                : "开始分析"}
            </Button>

            {error && (
              <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3">
                <p className="text-xs text-destructive">{error}</p>
              </div>
            )}
          </div>
        </aside>

        {/* ── RIGHT PANEL: Outputs ── */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Planning thinking — shown during the planning phase */}
          {planThinking && !planReasoning && (
            <div className="shrink-0 mx-5 mt-4 bg-muted/20 border border-border/50 rounded-lg p-3">
              <p className="text-[10px] text-muted-foreground/40 mb-1">正在分析简历和岗位要求...</p>
              <pre className="text-[11px] text-muted-foreground/60 leading-relaxed whitespace-pre-wrap font-mono max-h-32 overflow-y-auto">
                {planThinking}
              </pre>
            </div>
          )}

          {/* Planning reasoning */}
          {planReasoning && (
            <details className="shrink-0 mx-5 mt-4 bg-muted/30 border border-border rounded-lg p-4 group">
              <summary className="text-xs font-medium text-muted-foreground cursor-pointer select-none
                                 group-open:text-foreground transition-colors">
                分析策略 — 点击展开规划思路
              </summary>
              <p className="mt-3 text-xs text-muted-foreground/80 leading-relaxed whitespace-pre-wrap">
                {planReasoning}
              </p>
            </details>
          )}

          {/* Result tabs bar */}
          <div className="shrink-0">
            <ResultTabs
              tabs={openTabs}
              activeTab={activeResult}
              onSelect={setActiveResult}
              onClose={handleCloseTab}
            />
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            {/* Plan timeline */}
            {steps.length > 0 && (
              <PlanTimeline
                steps={steps}
                results={results}
                thinking={thinking}
                activeTab={activeResult}
                onStepClick={handleStepClick}
              />
            )}

            {/* Active tab result content */}
            {activeResult && results[activeResult] && (
              <section key={activeResult}>
                <h2 className="text-sm font-medium text-foreground mb-3">
                  {steps.find((s) => s.id === activeResult)?.icon}{" "}
                  {steps.find((s) => s.id === activeResult)?.name}
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

            {/* Empty states */}
            {!activeResult && steps.length > 0 && (
              <div className="flex items-center justify-center h-64 text-muted-foreground/40 text-sm">
                选择一个分析步骤查看结果
              </div>
            )}
            {steps.length === 0 && !planThinking && !planReasoning && (
              <div className="flex items-center justify-center h-full text-muted-foreground/30 text-sm">
                在左侧输入简历和岗位描述，然后点击"开始分析"
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
