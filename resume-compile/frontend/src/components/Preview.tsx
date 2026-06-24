"use client";

interface Props {
  pdfUrl: string | null;
  error: string | null;
  uploadedFileUrl?: string;
}

const COMMON_LATEX_ERRORS: [RegExp, string][] = [
  [/Undefined control sequence/i, '使用了未定义的 LaTeX 命令，检查是否有拼写错误'],
  [/File .* not found/i, '引用了不存在的文件，检查 usepackage 或 input 路径'],
  [/Missing \$/i, '数学模式符号不匹配，缺少 $ 符号'],
  [/Missing (begin|end)\{document\}/i, '缺少 begin{document} 或 end{document}'],
  [/Missing number/i, '缺少数字参数，检查 hspace、vspace 等命令'],
  [/Extra \}/i, '多余的花括号 }，检查括号是否成对'],
  [/Unbalanced.*brace/i, '花括号不配对'],
  [/LaTeX Error: (.*)/i, 'LaTeX 错误: $1'],
];

function friendlyError(msg: string): string {
  for (const [pattern, hint] of COMMON_LATEX_ERRORS) {
    if (pattern.test(msg)) return hint;
  }
  if (msg.includes("timeout") || msg.includes("timed out")) return "编译超时，LaTeX 代码可能过于复杂";
  if (msg.includes("5xx") || msg.includes("500")) return "服务器错误，请稍后重试";
  return "编译失败，请检查 LaTeX 语法";
}

export default function Preview({ pdfUrl, error, uploadedFileUrl }: Props) {
  const src = pdfUrl || (uploadedFileUrl ? `http://localhost:8000${uploadedFileUrl}` : null);

  if (error) {
    const hint = friendlyError(error);
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3">
        <div className="text-destructive/80 text-xs max-w-sm text-center">
          <div className="font-bold mb-1">{hint}</div>
          {hint !== error && (
            <details className="mt-2">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground/60 text-[11px]">查看原始错误</summary>
              <pre className="mt-2 whitespace-pre-wrap font-mono text-destructive/60 text-[11px] text-left">{error}</pre>
            </details>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground/60">修改 LaTeX 后点击「编译 PDF」重试</p>
      </div>
    );
  }

  if (!src) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-5">
        <div className="w-16 h-16 rounded-xl bg-card border border-border flex items-center justify-center">
          <svg className="w-7 h-7 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-muted-foreground">暂无预览</p>
          <p className="text-xs mt-1.5 text-muted-foreground/60">点击「编译 PDF」从 LaTeX 生成，或上传 PDF 文件</p>
        </div>
      </div>
    );
  }

  return (
    <iframe
      src={src}
      className="w-full h-full border-0 rounded"
      title="PDF Preview"
    />
  );
}
