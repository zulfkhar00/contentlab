"use client";

import { useState } from "react";
import { Bell, Copy, Check } from "lucide-react";
import { useProjectContext } from "@/lib/project-context";

function domainFromUrl(url: string): string {
  return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
}

export function AppTopbar() {
  const { context } = useProjectContext();
  const [copied, setCopied] = useState(false);

  const trackingLink = `contentlab.app/p/${context.trackingSlug}`;

  const copy = () => {
    navigator.clipboard?.writeText(trackingLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <header className="fixed right-0 top-0 z-10 flex h-14 w-[calc(100%-240px)] items-center justify-between border-b border-border bg-card px-6">
      <div className="flex items-center gap-6">
        <span className="border-b border-primary pb-1 font-mono text-xs font-bold text-foreground">
          @{context.tiktokHandle}
        </span>
        <span className="font-mono text-xs text-muted-foreground hover:text-foreground">
          {domainFromUrl(context.productUrl)}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1">
          <span className="font-mono text-xs text-foreground">
            {trackingLink}
          </span>
          <button
            onClick={copy}
            aria-label="Copy tracking link"
            className="flex items-center text-muted-foreground hover:text-foreground"
          >
            {copied ? (
              <Check className="size-3.5" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>
        </div>
        <button
          aria-label="Notifications"
          className="text-muted-foreground hover:text-foreground"
        >
          <Bell className="size-5" />
        </button>
        <div className="flex size-8 items-center justify-center overflow-hidden rounded-full border border-border bg-secondary font-mono text-xs font-semibold">
          FL
        </div>
      </div>
    </header>
  );
}
