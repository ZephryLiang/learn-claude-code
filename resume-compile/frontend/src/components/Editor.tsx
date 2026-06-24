"use client";

import dynamic from "next/dynamic";
import type { OnMount } from "@monaco-editor/react";

const Monaco = dynamic(() => import("@monaco-editor/react"), { ssr: false });

interface Props {
  value: string;
  onChange: (v: string) => void;
}

export default function Editor({ value, onChange }: Props) {
  const handleMount: OnMount = (editor) => {
    // Ctrl+S / Cmd+S to compile — parent listens for this
    editor.addAction({
      id: "compile",
      label: "Compile PDF",
      keybindings: [2048 | 49], // Ctrl/Cmd + S
      run: () => {
        document.dispatchEvent(new CustomEvent("compile-pdf"));
      },
    });
  };

  return (
    <Monaco
      height="100%"
      defaultLanguage="latex"
      theme="vs-dark"
      value={value}
      onChange={(v) => onChange(v ?? "")}
      onMount={handleMount}
      options={{
        fontSize: 13,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
        minimap: { enabled: false },
        lineNumbers: "on",
        scrollBeyondLastLine: false,
        wordWrap: "on",
        tabSize: 2,
        automaticLayout: true,
        padding: { top: 12 },
      }}
    />
  );
}
