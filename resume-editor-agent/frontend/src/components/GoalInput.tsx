"use client";

interface Props {
  onSubmit: (goal: string) => void;
  disabled?: boolean;
}

export default function GoalInput({ onSubmit, disabled }: Props) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground block">
        🎯 你的求职目标是什么？
      </label>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const input = (e.target as HTMLFormElement).elements.namedItem("goal") as HTMLInputElement;
          if (input.value.trim()) onSubmit(input.value.trim());
        }}
        className="flex gap-2"
      >
        <input
          name="goal"
          type="text"
          placeholder="例：我想面进字节跳动的 AI Agent 岗位"
          disabled={disabled}
          className="flex-1 h-10 bg-secondary border border-border rounded-lg px-4 text-sm placeholder:text-muted-foreground/40 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-40"
        />
      </form>
    </div>
  );
}
