import type { Metadata } from "next";
import "./globals.css";
import { Geist, DM_Serif_Display } from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' });
const dmSerif = DM_Serif_Display({
  subsets: ['latin'],
  weight: '400',
  variable: '--font-heading',
});

export const metadata: Metadata = {
  title: "Resume AI Editor",
  description: "AI-powered resume editor with LaTeX, JD analysis, and storytelling",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning className={cn("h-full", "font-sans", geist.variable, dmSerif.variable)}>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var t = localStorage.getItem("resume-editor-theme") || "dark";
                var d = window.matchMedia("(prefers-color-scheme: dark)").matches;
                if (t === "dark" || (t === "system" && d))
                  document.documentElement.classList.add("dark");
              } catch(e) {}
            `,
          }}
        />
      </head>
      <body className="h-full antialiased">{children}</body>
    </html>
  );
}
