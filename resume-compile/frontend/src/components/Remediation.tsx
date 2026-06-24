"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { remediateGaps } from "@/lib/api";

interface Props {
  resumeText: string;
  jdText: string;
  cachedResult: string | null;
  onResult: (v: string) => void;
  modelId: string;
  isLoading: boolean;
  onLoadingChange: (v: boolean) => void;
}

export default function Remediation({ resumeText, jdText, cachedResult, onResult, modelId, isLoading, onLoadingChange }: Props) {
  const [localLoading, setLocalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (isLoading) setLocalLoading(true); }, [isLoading]);

  const handleRemediate = async () => {
    if (!jdText.trim()) return;
    setLocalLoading(true);
    onLoadingChange(true);
    setError(null);
    try {
      const res = await remediateGaps(resumeText, jdText, modelId);
      onResult(res.plan);
    } catch (e: any) {
      setError(e.message || "Failed to generate plan");
    } finally {
      setLocalLoading(false);
      onLoadingChange(false);
    }
  };

  const loading = localLoading || isLoading;

  return (
    <div className="flex flex-col gap-3 h-full">
      <h3 className="text-sm font-medium text-foreground">能力补足计划</h3>
      <p className="text-xs text-muted-foreground">针对 JD 要求的技能差距，生成学习路线和优先级。</p>
      {!jdText.trim() && (
        <div className="text-xs text-amber-400/80 bg-amber-900/20 border border-amber-700/30 rounded-md px-3 py-2">
          请先在「JD 分析」中粘贴岗位描述
        </div>
      )}
      <Button
        onClick={handleRemediate}
        disabled={loading || !jdText.trim()}
        className="w-full"
      >
        {loading ? "生成中..." : "生成补足计划"}
      </Button>
      {error && <div className="text-destructive text-xs">{error}</div>}
      {(cachedResult || loading) && (
        <div className="flex-1 overflow-y-auto bg-card border border-border rounded-md min-h-0 flex flex-col">
          <div className="h-0.5 bg-brand/40 shrink-0" />
          <div className="flex-1 p-4 overflow-y-auto">
            {loading ? (
              <div className="text-muted-foreground text-xs">等待模型响应...</div>
            ) : (
              <pre className="text-sm whitespace-pre-wrap font-sans leading-[1.7] text-foreground/85">{cachedResult}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
