"use client";

import { useEffect, useRef } from "react";
import InterceptInput from "./InterceptInput";

export interface StepState {
  id: string;
  name: string;
  icon: string;
  status: "pending" | "running" | "done" | "error" | "revising";
  duration_ms?: number;
}

interface Props {
  steps: StepState[];
  results: Record<string, string>;
  thinking: Record<string, string>;
  activeTab: string | null;
  onStepClick: (stepId: string) => void;
  onIntercept: (stepId: string, feedback: string) => void;
}

const STATUS_ICONS: Record<string, string> = {
  pending: "⏳",
  running: "⟳",
  done: "✓",
  error: "✗",
  revising: "⟳",
};

export default function PlanTimeline({
  steps,
  results,
  thinking,
  activeTab,
  onStepClick,
  onIntercept,
}: Props) {
  const timelineRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [steps]);

  if (steps.length === 0) return null;

  return (
    <section ref={timelineRef} className="space-y-2">
      <h2 className="text-sm font-medium text-foreground mb-3">
        {"📋"} 执行计划
      </h2>

      {steps.map((step, idx) => {
        const isActive = activeTab === step.id;
        const hasResult = !!results[step.id];

        return (
          <div key={step.id} className="bg-card border border-border rounded-lg overflow-hidden">
            {/* Step header */}
            <div
              className={`flex items-center justify-between px-4 py-2.5 cursor-pointer hover:bg-secondary/50 transition-colors ${
                isActive ? "ring-1 ring-brand" : ""
              }`}
              onClick={() => onStepClick(step.id)}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={`text-sm ${
                    step.status === "running" || step.status === "revising"
                      ? "animate-spin"
                      : ""
                  }`}
                >
                  {STATUS_ICONS[step.status]}
                </span>
                <span className="text-sm text-foreground">{step.icon}</span>
                <span className="text-sm text-foreground">{step.name}</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground/60">
                {step.duration_ms != null && (
                  <span>
                    {step.duration_ms >= 1000
                      ? `${(step.duration_ms / 1000).toFixed(1)}s`
                      : `${step.duration_ms}ms`}
                  </span>
                )}
                <span className="capitalize">{step.status}</span>
              </div>
            </div>

            {/* Expandable detail */}
            {isActive && hasResult && (
              <div className="px-4 pb-4">
                <InterceptInput
                  stepId={step.id}
                  stepName={step.name}
                  onSubmit={onIntercept}
                />
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
