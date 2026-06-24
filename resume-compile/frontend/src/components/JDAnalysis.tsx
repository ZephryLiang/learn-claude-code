"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { analyzeGaps } from "@/lib/api";

interface Props {
  resumeText: string;
  jdText: string;
  onJdChange: (v: string) => void;
  cachedResult: string | null;
  onResult: (v: string) => void;
  modelId: string;
  isLoading: boolean;
  onLoadingChange: (v: boolean) => void;
}

export default function JDAnalysis({ resumeText, jdText, onJdChange, cachedResult, onResult, modelId, isLoading, onLoadingChange }: Props) {
  const [localLoading, setLocalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (isLoading) setLocalLoading(true); }, [isLoading]);

  const handleAnalyze = async () => {
    if (!jdText.trim()) return;
    setLocalLoading(true);
    onLoadingChange(true);
    setError(null);
    try {
      const res = await analyzeGaps(resumeText, jdText, modelId);
      onResult(res.analysis);
    } catch (e: any) {
      setError(e.message || "Analysis failed");
    } finally {
      setLocalLoading(false);
      onLoadingChange(false);
    }
  };

  const loading = localLoading || isLoading;

  return (
    <div className="flex flex-col gap-3 h-full">
      <h3 className="text-sm font-medium text-foreground">JD 分析</h3>
      <textarea
        value={jdText}
        onChange={(e) => onJdChange(e.target.value)}
        placeholder="粘贴岗位描述 (JD)..."
        className="w-full bg-secondary border border-border rounded-md p-2 text-xs font-mono resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring placeholder:text-muted-foreground/50"
        rows={6}
      />
      <Button
        onClick={handleAnalyze}
        disabled={loading || !jdText.trim()}
        className="w-full"
      >
        {loading ? "分析中..." : "分析 Gap"}
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
