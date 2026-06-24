"use client";

import { useCallback, useEffect, useState } from "react";
import Editor from "@/components/Editor";
import FileUpload from "@/components/FileUpload";
import ThemeToggle from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { compileLatex } from "@/lib/api";

interface UploadedFile {
  name: string;
  text: string;
  type: string;
}

const DEFAULT_LATEX = `\\documentclass[11pt,a4paper]{article}
\\usepackage[UTF8, fontset=fandol]{ctex}
\\usepackage[margin=0.6in]{geometry}
\\usepackage{enumitem}
\\usepackage[hidelinks]{hyperref}
\\usepackage{titlesec}
\\usepackage{xcolor}

\\definecolor{heading}{HTML}{2C3E50}
\\definecolor{accent}{HTML}{2980B9}
\\definecolor{lightgray}{HTML}{95A5A6}
\\setlist{leftmargin=0.8em, nosep, before=\\vspace{-0.2em}, after=\\vspace{0.1em}}
\\setlist[itemize]{label=\\textcolor{accent}{\\small\\textbullet}}
\\titleformat{\\section}{\\large\\bfseries\\color{heading}}{}{0em}{}[\\vspace{-0.2em}\\rule{\\textwidth}{0.4pt}\\vspace{0.1em}]
\\titlespacing{\\section}{0em}{0.5em}{0.2em}

\\newcommand{\\entry}[4]{
  \\noindent\\textbf{#1}\\hfill\\textcolor{lightgray}{\\small #2}\\\\
  \\textit{\\textcolor{accent}{#3}}\\hfill\\textcolor{lightgray}{\\small #4}\\vspace{0.1em}
}
\\newcommand{\\tag}[1]{\\textcolor{accent}{\\small\\texttt{#1}}}

\\begin{document}
\\begin{center}
  {\\LARGE\\bfseries\\color{heading} 姓名}\\\\[0.15em]
  {\\small (+86) 电话 \\quad \\href{mailto:email@example.com}{email@example.com} \\quad 上海~|~杭州}\\\\[0.1em]
  {\\small\\color{lightgray} \\textbf{Agentic AI Engineer}}
\\end{center}

\\section{个人总结}
Agentic AI / Generative AI 工程师...

\\section{技术能力}
\\begin{itemize}[leftmargin=0.5em]
  \\item \\textbf{Agentic AI}：Tool Calling / Function Calling、plan-execute loop
  \\item \\textbf{Guardrails \\& Governance}：Permission Gate、human-in-the-loop
\\end{itemize}

\\section{工作经历}
\\entry{公司名称}{2024.05 -- 2025.08}{职位}{}
\\begin{itemize}
  \\item 工作内容描述
\\end{itemize}

\\section{项目经历}
\\entry{项目名称}{2024.05 -- 2025.08}{}{}
\\begin{itemize}
  \\item 项目内容描述
\\end{itemize}

\\end{document}
`;

export default function Home() {
  const [latex, setLatex] = useState(DEFAULT_LATEX);
  const [mode, setMode] = useState<"text" | "code">("code");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);

  // ── compile (original pattern: use latex state directly) ──
  const handleCompile = useCallback(async () => {
    setCompiling(true);
    setCompileError(null);
    if (pdfUrl) { URL.revokeObjectURL(pdfUrl); setPdfUrl(null); }
    try {
      const blob = await compileLatex(latex);
      setPdfUrl(URL.createObjectURL(blob));
    } catch (e: any) {
      setCompileError(e.message || "Compilation failed");
    } finally {
      setCompiling(false);
    }
  }, [latex, pdfUrl]);

  // ── Ctrl+S ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleCompile();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleCompile]);

  // ── upload ──
  const handleUpload = useCallback((file: UploadedFile) => {
    setUploadedFile(file);
    if (file.type === "tex") {
      setLatex(file.text);
      setMode("code");
    }
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ── */}
      <header className="flex items-center justify-between px-5 h-13 border-b border-border bg-background/80 backdrop-blur-sm shrink-0">
        <h1 className="font-heading text-base tracking-tight text-foreground">LaTeX Compiler</h1>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <FileUpload onUpload={handleUpload} />
          <Button size="sm" onClick={handleCompile} disabled={compiling}>
            {compiling ? "编译中..." : "编译 PDF"}
          </Button>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto py-8 pb-24 px-6 space-y-4">
          {/* Mode toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1 bg-secondary rounded-md p-0.5">
              <button
                onClick={() => setMode("text")}
                className={`text-xs px-3 py-1 rounded transition-colors ${
                  mode === "text" ? "text-foreground bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                文本编辑
              </button>
              <button
                onClick={() => setMode("code")}
                className={`text-xs px-3 py-1 rounded transition-colors ${
                  mode === "code" ? "text-foreground bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Monaco 编辑器
              </button>
            </div>
            {uploadedFile && (
              <span className="text-xs text-muted-foreground">{uploadedFile.name}</span>
            )}
          </div>

          {/* Editor */}
          {mode === "text" ? (
            <textarea
              value={latex}
              onChange={(e) => setLatex(e.target.value)}
              className="w-full h-96 bg-secondary border border-border rounded-lg p-4 text-xs font-mono resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring leading-relaxed"
              spellCheck={false}
            />
          ) : (
            <div className="border border-border rounded-lg overflow-hidden" style={{ height: 500 }}>
              <Editor value={latex} onChange={setLatex} />
            </div>
          )}

          {/* Compile button */}
          <div className="flex items-center gap-3">
            <Button onClick={handleCompile} disabled={compiling} size="sm">
              {compiling ? "编译中..." : "编译 PDF"}
            </Button>
            <span className="text-xs text-muted-foreground">Ctrl+S</span>
          </div>

          {/* PDF Preview (original modal-style inline) */}
          {pdfUrl && (
            <div className="border border-border rounded-lg overflow-hidden" style={{ height: 650 }}>
              <div className="flex items-center justify-between px-3 h-8 bg-secondary border-b border-border shrink-0">
                <span className="text-xs text-muted-foreground">PDF 预览</span>
                <div className="flex items-center gap-2">
                  <a href={pdfUrl} download="resume.pdf" className="text-xs text-brand hover:underline">
                    下载 PDF
                  </a>
                  <button
                    onClick={() => { URL.revokeObjectURL(pdfUrl); setPdfUrl(null); }}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    关闭预览
                  </button>
                </div>
              </div>
              <iframe
                src={pdfUrl}
                className="w-full border-0"
                style={{ height: "calc(100% - 32px)" }}
                title="PDF Preview"
              />
            </div>
          )}
        </div>
      </main>

      {/* Compile error toast */}
      {compileError && (
        <div className="fixed bottom-6 right-6 z-40 max-w-sm bg-card border border-border rounded-lg shadow-xl p-4">
          <p className="text-xs text-destructive font-medium mb-1">编译失败</p>
          <pre className="text-xs text-muted-foreground whitespace-pre-wrap max-h-40 overflow-y-auto">{compileError}</pre>
          <Button variant="ghost" size="sm" className="mt-2" onClick={() => setCompileError(null)}>关闭</Button>
        </div>
      )}
    </div>
  );
}
