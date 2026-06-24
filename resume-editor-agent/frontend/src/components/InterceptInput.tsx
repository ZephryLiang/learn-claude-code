"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  stepId: string;
  stepName: string;
  onSubmit: (stepId: string, feedback: string) => void;
}

export default function InterceptInput({ stepId, stepName, onSubmit }: Props) {
  const [value, setValue] = useState("");
  const [sent, setSent] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    return () => clearTimeout(timerRef.current);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    onSubmit(stepId, value.trim());
    setValue("");
    setSent(true);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setSent(false), 3000);
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 mt-3">
      <span className="text-[11px] text-muted-foreground/40 shrink-0">
        对这个结果有补充吗？
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="例：其实我做过系统设计，但简历上没写"
        className="flex-1 h-8 bg-secondary/50 border border-border rounded-md px-3 text-xs placeholder:text-muted-foreground/30 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
      <button
        type="submit"
        disabled={!value.trim()}
        className="h-8 px-3 text-xs font-medium bg-brand text-white rounded-md hover:bg-brand-hover disabled:opacity-30 transition-colors"
      >
        发送
      </button>
      {sent && (
        <span className="text-[11px] text-brand/70">已发送</span>
      )}
    </form>
  );
}
