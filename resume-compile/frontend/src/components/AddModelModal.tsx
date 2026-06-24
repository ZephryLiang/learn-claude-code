"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { validateModel, addModel } from "@/lib/api";

interface Props {
  onClose: () => void;
  onAdded: () => void;
}

export default function AddModelModal({ onClose, onAdded }: Props) {
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com/anthropic");
  const [step, setStep] = useState<"form" | "validating" | "result">("form");
  const [error, setError] = useState<string | null>(null);
  const [valid, setValid] = useState(false);

  const handleValidate = async () => {
    if (!modelId.trim() || !apiKey.trim() || !baseUrl.trim()) return;
    setStep("validating");
    setError(null);
    try {
      const res = await validateModel(apiKey.trim(), baseUrl.trim(), modelId.trim());
      setValid(res.valid);
      setStep("result");
    } catch (e: any) {
      setError(e.message || "Validation failed");
      setStep("form");
    }
  };

  const handleAdd = async () => {
    try {
      await addModel(apiKey.trim(), baseUrl.trim(), modelId.trim());
      onAdded();
      onClose();
    } catch (e: any) {
      setError(e.message || "Failed to add model");
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>添加模型</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="grid gap-2">
            <Label htmlFor="modelId">模型 ID</Label>
            <Input
              id="modelId"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              placeholder="e.g. deepseek-chat, claude-sonnet-4-6"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="apiKey">API Key</Label>
            <Input
              id="apiKey"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              type="password"
              placeholder="sk-..."
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="baseUrl">Base URL</Label>
            <Input
              id="baseUrl"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.deepseek.com/anthropic"
              className="font-mono"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            支持的格式：<code className="text-foreground/60">https://api.example.com/anthropic</code>
          </p>

          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="flex gap-2">
            {step !== "result" ? (
              <Button
                onClick={handleValidate}
                disabled={step === "validating" || !modelId.trim() || !apiKey.trim() || !baseUrl.trim()}
                className="flex-1"
              >
                {step === "validating" ? "验证中..." : "验证"}
              </Button>
            ) : (
              <>
                <div className="flex-1 flex items-center gap-2 text-sm">
                  {valid ? (
                    <span className="text-emerald-400">✓ 验证通过</span>
                  ) : (
                    <span className="text-destructive">✗ 验证失败</span>
                  )}
                </div>
                {valid && (
                  <Button onClick={handleAdd} variant="default">
                    确认添加
                  </Button>
                )}
                <Button onClick={() => setStep("form")} variant="secondary">
                  重试
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
