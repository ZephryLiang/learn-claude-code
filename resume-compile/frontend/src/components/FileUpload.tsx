"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { parseResume } from "@/lib/api";

export interface UploadResult {
  name: string;
  text: string;
  type: string;
  fileUrl?: string;
}

interface Props {
  onUpload: (result: UploadResult) => void;
}

export default function FileUpload({ onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    setFileName(null);
    try {
      const result = await parseResume(file);
      setFileName(result.filename);
      onUpload({
        name: result.filename,
        text: result.text,
        type: result.type,
        fileUrl: result.file_url,
      });
    } catch (err: any) {
      setError(err.message || "Upload failed");
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.tex"
        className="hidden"
        onChange={handleFile}
      />
      <Button
        variant="secondary"
        size="sm"
        onClick={() => inputRef.current?.click()}
        disabled={loading}
        title="上传 PDF / DOCX / LaTeX"
      >
        {loading ? "解析中..." : "上传简历"}
      </Button>
      {fileName && (
        <span className="text-xs text-muted-foreground truncate max-w-32" title={fileName}>
          {fileName}
        </span>
      )}
      {error && <span className="text-destructive text-xs">{error}</span>}
    </div>
  );
}
