import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

function preprocessContent(content: string): string {
  return content.replace(/(\d+)(\/10)/g, '$1<span class="score-badge">$2</span>');
}

const components: Partial<Components> = {
  h1: ({ children, ...props }) => (
    <h1 className="text-base font-heading text-foreground mt-7 mb-3 first:mt-0 pb-1 border-b border-border/40" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="text-[15px] font-heading text-foreground mt-6 mb-3 flex items-center gap-2" {...props}>
      <span className="w-1 h-4 rounded-full bg-brand/50 shrink-0" />
      <span>{children}</span>
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="text-sm font-heading text-foreground mt-5 mb-2" {...props}>{children}</h3>
  ),
  p: ({ children, ...props }) => (
    <p className="text-sm leading-[1.85] text-foreground/80 mb-3 last:mb-0" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="text-sm leading-[1.75] text-foreground/80 pl-0 mb-4 space-y-1.5 last:mb-0 [&>li]:pl-5 [&>li]:relative [&>li::before]:content-['◆'] [&>li::before]:absolute [&>li::before]:left-0 [&>li::before]:text-brand/60 [&>li::before]:text-[10px] [&>li::before]:leading-[1.75]" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="text-sm leading-[1.75] text-foreground/80 pl-5 mb-4 space-y-1.5 last:mb-0 list-decimal [&>li::marker]:text-brand/50 [&>li::marker]:font-medium" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-sm leading-[1.75] text-foreground/80" {...props}>{children}</li>
  ),
  strong: ({ children, ...props }) => {
    const text = extractText(children);
    if (text.endsWith(":")) {
      return (
        <strong className="font-semibold text-brand text-[13px] tracking-wide" {...props}>
          {children}
        </strong>
      );
    }
    return (
      <strong className="font-semibold text-foreground/90" {...props}>
        {children}
      </strong>
    );
  },
  code: ({ children, ...props }) => {
    const isInline = !props.node?.properties?.className;
    if (isInline) {
      return (
        <code className="text-xs bg-secondary px-1.5 py-0.5 rounded text-foreground/80 font-mono" {...props}>
          {children}
        </code>
      );
    }
    return (
      <pre className="bg-secondary border border-border rounded-md p-3 mb-3 overflow-x-auto last:mb-0">
        <code className="text-xs font-mono text-foreground/80 leading-relaxed" {...props}>
          {children}
        </code>
      </pre>
    );
  },
  pre: ({ children }) => <>{children}</>,
  blockquote: ({ children, ...props }) => (
    <blockquote className="relative bg-brand/[0.04] border-l-[3px] border-brand/35 rounded-r-lg pl-4 pr-4 py-3 mb-4 last:mb-0" {...props}>
      <div className="absolute top-2 right-2 text-[10px] text-brand/15 font-medium tracking-widest select-none">INSIGHT</div>
      <div className="text-sm text-foreground/75 leading-relaxed [&>p]:mb-0">{children}</div>
    </blockquote>
  ),
  hr: () => (
    <div className="my-6 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
  ),
  a: ({ children, href, ...props }) => (
    <a className="text-brand hover:text-brand-hover underline underline-offset-2 decoration-brand/30" href={href} target="_blank" rel="noreferrer" {...props}>
      {children}
    </a>
  ),
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto mb-4 rounded-lg border border-border">
      <table className="w-full text-sm border-collapse" {...props}>{children}</table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th className="bg-secondary/80 px-3 py-2 text-left text-xs font-semibold text-foreground/80 border-b border-border" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="px-3 py-2 text-sm text-foreground/70 border-t border-border/60" {...props}>{children}</td>
  ),
};

function extractText(node: React.ReactNode): string {
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    return extractText((node as any).props?.children ?? "");
  }
  return "";
}

interface Props {
  content: string;
  thinking?: string;
}

export default function MarkdownRenderer({ content, thinking }: Props) {
  return (
    <div className="markdown-body">
      {thinking && (
        <details className="group mb-4">
          <summary className="text-[11px] text-muted-foreground/40 hover:text-muted-foreground/60 cursor-pointer select-none transition-colors py-1 tracking-wider flex items-center gap-1.5">
            <span className="inline-block transition-transform group-open:rotate-90 text-[10px]">▸</span>
            推理过程
          </summary>
          <div className="mt-2 pl-3 border-l-2 border-border/40">
            <ReactMarkdown components={mutedComponents} remarkPlugins={[remarkGfm]}>
              {preprocessContent(thinking)}
            </ReactMarkdown>
          </div>
        </details>
      )}
      <ReactMarkdown components={components} remarkPlugins={[remarkGfm]}>
        {preprocessContent(content)}
      </ReactMarkdown>
    </div>
  );
}

/** Muted component variants for rendering thinking/reasoning blocks. */
const mutedComponents: Partial<Components> = {
  p: ({ children, ...props }) => (
    <p className="text-xs leading-relaxed text-muted-foreground/50 mb-2 last:mb-0" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="text-xs leading-relaxed text-muted-foreground/50 pl-4 mb-2 space-y-0.5 last:mb-0" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="text-xs leading-relaxed text-muted-foreground/50 pl-4 mb-2 space-y-0.5 last:mb-0 list-decimal" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-xs leading-relaxed text-muted-foreground/50" {...props}>{children}</li>
  ),
  strong: ({ children, ...props }) => (
    <strong className="font-medium text-muted-foreground/60" {...props}>{children}</strong>
  ),
  code: ({ children, ...props }) => {
    const isInline = !props.node?.properties?.className;
    if (isInline) {
      return (
        <code className="text-[11px] bg-muted/30 px-1 py-0.5 rounded text-muted-foreground/50 font-mono" {...props}>
          {children}
        </code>
      );
    }
    return (
      <pre className="bg-muted/20 border border-border/30 rounded-md p-2 mb-2 overflow-x-auto last:mb-0">
        <code className="text-[11px] font-mono text-muted-foreground/50 leading-relaxed" {...props}>{children}</code>
      </pre>
    );
  },
  pre: ({ children }) => <>{children}</>,
  hr: () => <div className="my-3 h-px bg-border/20" />,
};
