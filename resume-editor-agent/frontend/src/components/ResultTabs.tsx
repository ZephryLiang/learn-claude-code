"use client";

import { cn } from "@/lib/utils";

export interface TabInfo {
  stepId: string;
  stepName: string;
  icon: string;
}

interface Props {
  tabs: TabInfo[];
  activeTab: string | null;
  onSelect: (stepId: string) => void;
  onClose: (stepId: string) => void;
}

export default function ResultTabs({ tabs, activeTab, onSelect, onClose }: Props) {
  if (tabs.length === 0) return null;

  return (
    <div className="flex items-stretch gap-0 border-b border-border pl-2 bg-background/80 backdrop-blur-sm shrink-0 overflow-x-auto">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.stepId;
        return (
          <div
            key={tab.stepId}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 text-sm cursor-pointer select-none border-r border-border transition-colors shrink-0",
              isActive
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
            )}
            onClick={() => onSelect(tab.stepId)}
          >
            <span className="text-xs">{tab.icon}</span>
            <span className="text-xs font-medium truncate max-w-[120px]">
              {tab.stepName}
            </span>
            <button
              className="ml-0.5 p-0.5 rounded-sm hover:bg-secondary text-muted-foreground/40 hover:text-muted-foreground flex-shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                onClose(tab.stepId);
              }}
              aria-label={`Close ${tab.stepName}`}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M1 1l8 8M9 1l-8 8" />
              </svg>
            </button>
          </div>
        );
      })}
    </div>
  );
}
