import React from "react";
"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, ExternalLink, Link2, Rocket, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useExperiment,
  variantStatusLabel,
  variantStatusTone,
  getExperimentStatus,
  getPublishedCount,
  clicksPer1k,
  formatTimestamp,
  getTrackingWindow,
  type Variant,
  type VariantRole,
} from "@/lib/experiment";

const FILTERS = ["All", "Tracking", "Completed"] as const;
type Filter = (typeof FILTERS)[number];

function StatusDot({ tone }: { tone: "active" | "idle" }) {
  return (
    <span
      className={`size-1.5 rounded-full ${tone === "active" ? "bg-success" : "bg-border"}`}
    />
  );
}

function WindowCountdown({ endsAt }: { endsAt: string | null }) {
  const [label, setLabel] = React.useState("");
  React.useEffect(() => {
    if (!endsAt) return;
    function tick() {
      const ms = new Date(endsAt!).getTime() - Date.now();
      if (ms <= 0) { setLabel("Closing…"); return; }
      const h = Math.floor(ms / 3600000);
      const m = Math.floor((ms % 3600000) / 60000);
      setLabel(`${h}h ${m}m remaining`);
    }
    tick();
    const id = setInterval(tick, 60000);
    return () => clearInterval(id);
  }, [endsAt]);
  if (!endsAt || !label) return null;
  return (
    <span className="font-mono text-[10px] tabular-nums text-muted-foreground">{label}</span>
  );
}

export default function VideosPage() {
  const { experiment, loaded } = useExperiment();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("All");

  const videos = experiment!.variants.filter(
    (v) => v.status === "tracking" || v.status === "completed",
  );

  const visible = videos.filter((v) => {
    const matchesFilter =
      filter === "All" || variantStatusLabel(v.status) === filter;
    const matchesSearch = v.title.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const [selectedRole, setSelectedRole] = useState<VariantRole | null>(
    videos[0]?.role ?? null,
  );
  const selected = experiment!.variants.find((v) => v.role === selectedRole) ?? null;

  function copyUrl(url: string) {
    navigator.clipboard?.writeText(url);
  }

  // Same gate every other (app) page uses: don't render experiment-derived UI
  // until the useEffect in ExperimentProvider has re-read localStorage. Without
  // this, VideoInspector's tracking-window bar renders a full-precision
  // `Date.now()`-derived width on the server (e.g. "5.555559799382716%"),
  // then the browser's CSSOM re-serializes that inline style to 6 significant
  // digits ("5.55556%") on parse, and React's client render diffs the two →
  // hydration mismatch. Gating on `loaded` moves the whole tracking-window
  // computation past hydration, where there's nothing to diff against.
  if (!loaded) return null;
  if (!experiment) return (
    <div className="border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground">
      No published videos yet. Complete the recording workflow to see tracking here.
    </div>
  );

  const publishedCount = getPublishedCount(experiment!.variants);
  const trackingCount = experiment!.variants.filter((v) => v.status === "tracking").length;
  const totalViews = experiment!.variants.reduce((s, v) => s + (v.metrics?.views ?? 0), 0);
  const totalClicksForAvg = experiment!.variants.reduce((s, v) => s + (v.metrics?.clicks ?? 0), 0);
  const avgClicksPer1k = totalViews > 0 ? clicksPer1k(totalViews, totalClicksForAvg) : 0;
  const expStatus = getExperimentStatus(experiment!.variants);

  const liveKpis = [
    { label: "Published Videos", value: String(publishedCount) },
    { label: "Currently Tracking", value: String(trackingCount) },
    { label: "Total Views", value: totalViews >= 1000 ? (totalViews / 1000).toFixed(1) + "K" : String(totalViews) },
    { label: "Avg Clicks / 1K Views", value: String(avgClicksPer1k) },
  ];

  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Videos</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            How are the published variants performing?
          </p>
        </div>
        {expStatus !== "ready" && (
          <Button asChild className="shrink-0 gap-2">
            {expStatus === "tracking" ? (
              <Link href="/experiments">Go to Workspace <ArrowRight className="size-4" /></Link>
            ) : (
              <Link href="/insights">Review Results <ArrowRight className="size-4" /></Link>
            )}
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {liveKpis.map((k) => (
          <div key={k.label} className="border border-border bg-card p-4">
            <div className="mb-1 font-mono text-xs uppercase tracking-wide text-muted-foreground">
              {k.label}
            </div>
            <div className="font-mono text-xl font-semibold">{k.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Registry */}
        <div className="flex flex-col border border-border bg-card lg:col-span-8">
          <div className="flex items-center justify-between border-b border-border bg-secondary p-3">
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search videos..."
                className="h-8 pl-8 text-xs"
              />
            </div>
            <div className="flex items-center gap-1 rounded border border-border bg-card p-1">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                    filter === f
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full whitespace-nowrap border-collapse text-left">
              <thead className="border-y border-border bg-background font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="p-3 font-medium">Video</th>
                  <th className="p-3 font-medium">Campaign</th>
                  <th className="p-3 font-medium">Variant</th>
                  <th className="p-3 font-medium">Role</th>
                  <th className="p-3 font-medium">Status</th>
                  <th className="p-3 font-medium">Published</th>
                  <th className="p-3 text-right font-medium">Views</th>
                  <th className="p-3 text-right font-medium">Comments</th>
                  <th className="p-3 text-right font-medium">Clicks</th>
                  <th className="p-3 text-right font-medium">Clicks / 1K</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((v) => (
                  <tr
                    key={v.role}
                    onClick={() => setSelectedRole(v.role)}
                    className={`cursor-pointer border-b border-border text-sm last:border-0 ${
                      v.role === selectedRole ? "bg-secondary" : "hover:bg-secondary/50"
                    }`}
                  >
                    <td className="max-w-[150px] truncate p-3 text-muted-foreground">
                      {v.title}
                    </td>
                    <td className="max-w-[150px] truncate p-3 text-xs text-muted-foreground">
                      {experiment!.name}
                    </td>
                    <td className="p-3">
                      <span className="rounded bg-primary px-1.5 py-0.5 font-mono text-[10px] text-primary-foreground">
                        {v.role}
                      </span>
                    </td>
                    <td className="p-3 text-xs text-muted-foreground">
                      {v.roleLabel}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-1.5">
                        <StatusDot tone={variantStatusTone(v.status)} />
                        <span className="font-mono text-[11px] uppercase tracking-wide text-success">
                          {variantStatusLabel(v.status)}
                        </span>
                      </div>
                    </td>
                    <td className="p-3 font-mono text-[11px] text-muted-foreground">
                      {v.publishedAt ? formatTimestamp(v.publishedAt) : "—"}
                    </td>
                    <td className="p-3 text-right font-mono text-[13px]">
                      {v.metrics?.views.toLocaleString() ?? "—"}
                    </td>
                    <td className="p-3 text-right font-mono text-[13px]">
                      {v.metrics?.comments.toLocaleString() ?? "—"}
                    </td>
                    <td className="p-3 text-right font-mono text-[13px]">
                      {v.metrics?.clicks.toLocaleString() ?? "—"}
                    </td>
                    <td className="p-3 text-right font-mono text-[13px] font-semibold">
                      {v.metrics ? clicksPer1k(v.metrics.views, v.metrics.clicks) : "—"}
                    </td>
                  </tr>
                ))}
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={10} className="p-12 text-center text-sm text-muted-foreground">
                      {videos.length === 0
                        ? "No videos published yet. Start tracking a variant from Campaigns to see it here."
                        : "No videos match this filter."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Inspector */}
        <div className="flex flex-col gap-4 lg:col-span-4">
          {selected ? (
            <VideoInspector
              key={selected.role}
              variant={selected}
              experimentName={experiment!.name}
              trackingWindowHours={experiment!.trackingWindowHours}
              onCopyUrl={copyUrl}
            />
          ) : (
            <div className="border border-border bg-card p-6 text-center text-sm text-muted-foreground">
              Select a video to inspect it.
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function VideoInspector({
  variant,
  experimentName,
  trackingWindowHours,
  onCopyUrl,
}: {
  variant: Variant;
  experimentName: string;
  trackingWindowHours: number;
  onCopyUrl: (url: string) => void;
}) {
  const trackingWindow = getTrackingWindow(variant, trackingWindowHours);
  const m = variant.metrics;

  return (
    <>
      <div className="border border-border bg-card">
        <div className="border-b border-border p-4">
          <div className="mb-3 flex items-start justify-between">
            <div className="flex flex-col gap-1">
              <span className="w-fit rounded-sm bg-primary px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-primary-foreground">
                Variant {variant.role} · {variant.roleLabel}
              </span>
              <h3 className="mt-2 text-lg font-bold">{variant.title}</h3>
              <p className="font-mono text-[11px] uppercase tracking-tight text-muted-foreground">
                {experimentName}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className={[
                "rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide",
                variant.status === "validating"
                  ? "border-amber-400/40 bg-amber-50 text-amber-700"
                  : variant.status === "tracking_failed"
                  ? "border-rose-400/40 bg-rose-50 text-rose-700"
                  : "border-success/20 bg-[#ECFDF5] text-success",
              ].join(" ")}>
                {variantStatusLabel(variant.status)}
              </span>
              <WindowCountdown endsAt={(variant as { tracking_window_ends_at?: string | null }).tracking_window_ends_at ?? null} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <Button
              asChild={!!variant.tiktokUrl}
              variant="outline"
              size="sm"
              disabled={!variant.tiktokUrl}
              className="gap-1 text-[10px]"
            >
              {variant.tiktokUrl ? (
                <a href={variant.tiktokUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="size-3.5" />
                  TikTok
                </a>
              ) : (
                <span>
                  <ExternalLink className="size-3.5" />
                  TikTok
                </span>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!variant.tiktokUrl}
              className="gap-1 text-[10px]"
              onClick={() => variant.tiktokUrl && onCopyUrl(variant.tiktokUrl)}
            >
              <Link2 className="size-3.5" />
              URL
            </Button>
            <Button asChild variant="outline" size="sm" className="gap-1 text-[10px]">
              <Link href="/experiments">
                <Rocket className="size-3.5" />
                Campaign
              </Link>
            </Button>
          </div>
        </div>
      </div>

      {m && (
        <div className="border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border bg-secondary px-4 py-2">
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              Performance Snapshot
            </span>
          </div>
          <div className="grid grid-cols-2 divide-x divide-y divide-border">
            <div className="p-3">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Views
              </div>
              <div className="font-mono text-xl">{m.views.toLocaleString()}</div>
            </div>
            <div className="p-3">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Likes
              </div>
              <div className="font-mono text-xl">{m.likes.toLocaleString()}</div>
            </div>
            <div className="p-3">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Comments
              </div>
              <div className="font-mono text-xl">{m.comments.toLocaleString()}</div>
            </div>
            <div className="p-3">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Clicks
              </div>
              <div className="font-mono text-xl">{m.clicks.toLocaleString()}</div>
            </div>
            <div className="col-span-2 flex items-center justify-between bg-primary p-3 text-primary-foreground">
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest">
                Efficiency (Clicks / 1K)
              </span>
              <span className="font-mono text-xl">
                {clicksPer1k(m.views, m.clicks)}
              </span>
            </div>
          </div>
        </div>
      )}

      {trackingWindow && (
        <div className="border border-border bg-card p-4">
          <div className="mb-3 flex items-end justify-between">
            <div>
              <h4 className="mb-1 font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Tracking Window
              </h4>
              <div className="text-xs font-semibold">
                {trackingWindow.elapsedHours}h{" "}
                <span className="font-normal text-muted-foreground">
                  / {trackingWindowHours}h elapsed
                </span>
              </div>
            </div>
            <div className="font-mono text-[10px] text-muted-foreground">
              Ends {formatTimestamp(trackingWindow.endsAt.toISOString())}
            </div>
          </div>
          <div className="mb-2 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full bg-primary"
              style={{ width: `${trackingWindow.percentElapsed}%` }}
            />
          </div>
          <div className="flex justify-between font-mono text-[10px] text-muted-foreground">
            <span>
              Started: {formatTimestamp(trackingWindow.startedAt.toISOString())}
            </span>
          </div>
        </div>
      )}
    </>
  );
}
