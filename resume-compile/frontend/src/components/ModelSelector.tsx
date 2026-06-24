"use client";

import { useEffect, useState } from "react";
import { fetchModels, ModelInfo } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Props {
  activeModel: string;
  onSelect: (id: string) => void;
  onAddClick: () => void;
}

export default function ModelSelector({ activeModel, onSelect, onAddClick }: Props) {
  const [models, setModels] = useState<ModelInfo[]>([]);

  useEffect(() => {
    fetchModels().then(setModels).catch(() => {});
  }, []);

  const handleValueChange = (value: string) => {
    if (value === "__add__") {
      onAddClick();
      return;
    }
    onSelect(value);
  };

  return (
    <Select value={activeModel || undefined} onValueChange={handleValueChange}>
      <SelectTrigger className="h-8 w-[180px] text-xs gap-1">
        <SelectValue placeholder="选择模型" />
      </SelectTrigger>
      <SelectContent>
        {models.map((m) => (
          <SelectItem key={m.id} value={m.id} className="text-xs">
            <span className="flex items-center justify-between w-full gap-2">
              <span className="truncate">{m.name}</span>
              {m.default && (
                <span className="text-muted-foreground text-[10px] shrink-0">默认</span>
              )}
            </span>
          </SelectItem>
        ))}
        <SelectItem value="__add__" className="text-xs text-muted-foreground">
          + 添加模型
        </SelectItem>
      </SelectContent>
    </Select>
  );
}
