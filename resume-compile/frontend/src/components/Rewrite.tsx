"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { rewriteResume } from "@/lib/api";

interface Props {
  resumeText: string;
  jdText: string;
  onResult: (latex: string) => void;
  cachedResult: string | null;
  onCacheResult: (v: string) => void;
  modelId: string;
  isLoading: boolean;
  onLoadingChange: (v: boolean) => void;
}

export default function Rewrite({ resumeText, jdText, onResult, cachedResult, onCacheResult, modelId, isLoading, onLoadingChange }: Props) {
  const [localLoading, setLocalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const [section, setSection] = useState("all");
  const [undoContent, setUndoContent] = useState<string | null>(null);

  useEffect(() => { if (isLoading) setLocalLoading(true); }, [isLoading]);

  const handleRewrite = async () => {
    if (!jdText.trim()) return;
    setLocalLoading(true);
    onLoadingChange(true);
    setError(null);
    try {
      const res = await rewriteResume(resumeText, jdText, section, instruction, modelId);
      onCacheResult(res.rewritten);
    } catch (e: any) {
      setError(e.message || "Rewrite failed");
    } finally {
      setLocalLoading(false);
      onLoadingChange(false);
    }
  };

  const loading = localLoading || isLoading;

  const applyToEditor = () => {
    if (cachedResult) {
      setUndoContent(resumeText);
      onResult(cachedResult);
    }
  };

  const handleUndo = () => {
    if (undoContent) {
      onResult(undoContent);
      setUndoContent(null);
    }
  };

  return (
    <div className="flex flex-col gap-3 h-full">
      <h3 className="text-sm font-medium text-foreground">故事化改写</h3>
      <p className="text-xs text-muted-foreground">
        用「背景 → 问题 → 方案 → 痛点解决」的叙事逻辑重构简历。
      </p>
      {!jdText.trim() && (
        <div className="text-xs text-amber-400/80 bg-amber-900/20 border border-amber-700/30 rounded-md px-3 py-2">
          请先在「JD 分析」中粘贴岗位描述
        </div>
      )}

      <div className="grid gap-2">
        <label className="text-xs text-muted-foreground">改写范围</label>
        <select
          value={section}
          onChange={(e) => setSection(e.target.value)}
          className="w-full bg-secondary border border-border rounded-md p-1.5 text-xs focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <option value="all">全部</option>
          <option value="summary">个人总结</option>
          <option value="work">工作经历</option>
          <option value="project">项目经历</option>
        </select>
      </div>

      <div className="flex-1 flex flex-col min-h-0 gap-2">
        <label className="text-xs text-muted-foreground">额外要求（可选）</label>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="例如：突出 Permission Gate 的工程决策..."
          className="w-full flex-1 bg-secondary border border-border rounded-md p-2 text-xs font-mono resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring placeholder:text-muted-foreground/50"
          rows={3}
        />
      </div>

      <Button
        onClick={handleRewrite}
        disabled={loading || !jdText.trim()}
        className="w-full"
      >
        {loading ? "改写中..." : "开始改写"}
      </Button>

      {error && <div className="text-destructive text-xs">{error}</div>}

      {(cachedResult || loading) && (
        <div className="flex flex-col gap-2">
          <div className="max-h-48 overflow-y-auto bg-card border border-border rounded-md flex flex-col">
            <div className="h-0.5 bg-brand/40 shrink-0" />
            <div className="p-4">
              {loading ? (
                <div className="text-muted-foreground text-xs">等待模型响应...</div>
              ) : (
                <pre className="text-sm whitespace-pre-wrap font-sans leading-[1.7] text-foreground/85">{cachedResult}</pre>
              )}
            </div>
          </div>
          {cachedResult && !loading && !undoContent && (
            <Button
              onClick={applyToEditor}
              variant="default"
              className="w-full"
            >
              应用到编辑器
            </Button>
          )}
          {undoContent && (
            <div className="flex items-center gap-2 bg-amber-900/30 border border-amber-700/40 rounded-md px-3 py-2">
              <span className="text-xs text-amber-300/80 flex-1">已应用改写，可撤销恢复</span>
              <button
                onClick={handleUndo}
                className="text-xs font-medium text-amber-300 hover:text-amber-200 underline transition-colors"
              >
                撤销
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
