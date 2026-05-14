"use client";

export default function Home() {
  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between px-5 h-13 border-b border-border bg-background/80 backdrop-blur-sm shrink-0">
        <h1 className="font-heading text-base tracking-tight text-foreground">
          Resume AI Agent
        </h1>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-10 pb-32 px-6 space-y-6">
          <p className="text-muted-foreground text-sm">Agent UI coming in Task 6...</p>
        </div>
      </main>
    </div>
  );
}
