"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FlaskConical,
  Megaphone,
  Clapperboard,
  BarChart3,
  Settings,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const NAV = [
  { label: "Overview", href: "/overview", icon: LayoutDashboard },
  { label: "Research", href: "/research", icon: FlaskConical },
  { label: "Experiments", href: "/experiments", icon: Megaphone },
  { label: "Videos", href: "/videos", icon: Clapperboard },
  { label: "Insights", href: "/insights", icon: BarChart3 },
];

export function AppSidebar() {
  const pathname = usePathname();

  const linkClass = (href: string) => {
    const active = pathname === href || pathname.startsWith(href + "/");
    return `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
      active
        ? "border border-primary/20 bg-secondary font-medium text-foreground"
        : "border border-transparent text-muted-foreground hover:bg-secondary"
    }`;
  };

  return (
    <aside className="fixed left-0 top-0 z-20 flex h-full w-60 flex-col gap-1 border-r border-border bg-card p-4">
      {/* Brand */}
      <div className="mb-6 flex items-center gap-3 px-2">
        <div className="flex size-8 items-center justify-center overflow-hidden rounded-full border border-border bg-secondary font-mono text-xs font-semibold">
          FL
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Content Lab</h1>
          <p className="font-mono text-xs text-muted-foreground">v0.1-beta</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1">
        {NAV.map(({ label, href, icon: Icon }) => (
          <Link key={href} href={href} className={linkClass(href)}>
            <Icon className="size-5" />
            {label}
          </Link>
        ))}
        <Link href="/settings" className={`mt-auto ${linkClass("/settings")}`}>
          <Settings className="size-5" />
          Settings
        </Link>
      </nav>

      {/* CTA */}
      <div className="mt-4">
        <Button asChild className="w-full gap-2">
          <Link href="/experiments">
            <Plus className="size-4" />
            Create Experiment
          </Link>
        </Button>
      </div>
    </aside>
  );
}
