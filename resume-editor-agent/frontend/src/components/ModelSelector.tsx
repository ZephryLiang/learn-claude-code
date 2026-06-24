"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ModelOption } from "@/lib/api";

interface Props {
  value: string | null;
  onChange: (modelId: string | null) => void;
  models: ModelOption[];
}

export default function ModelSelector({ value, onChange, models }: Props) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground block">
        模型选择
      </label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {models.map((m) => (
            <SelectItem key={m.id} value={m.id}>
              {m.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
