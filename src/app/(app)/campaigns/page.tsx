"use client";

import { useState } from "react";
import Link from "next/link";
import { Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useCampaign,
  getCampaignStatus,
  campaignStatusLabel,
  getPublishedCount,
  getNextActionVariant,
  variantStatusLabel,
  variantStatusTone,
  clicksPer1k,
  isValidTiktokUrl,
  type Variant,
  type VariantRole,
} from "@/lib/campaign";

function StatusPill({
  children,
  tone = "idle",
}: {
  children: React.ReactNode;
  tone?: "active" | "idle";
}) {
  return (
    <span
      className={`shrink-0 whitespace-nowrap rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${
        tone === "active"
          ? "bg-[#ECFDF5] text-success"
          : "border border-border bg-card text-muted-foreground"
      }`}
    >
      {children}
    </span>
  );
}

function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

function stepperLabel(v: Variant, nextRole: VariantRole | null) {
  if (v.status === "tracking") return `Variant ${v.role} (Published / Tracking)`;
  if (v.status === "completed") return `Variant ${v.role} (Completed)`;
  if (v.role === nextRole) return `Variant ${v.role} (Next)`;
  return `Variant ${v.role} (Ready)`;
}

export default function CampaignsPage() {
  const { campaign, loaded, startTracking } = useCampaign();
  const [urlDraft, setUrlDraft] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [copiedRole, setCopiedRole] = useState<VariantRole | null>(null);

  function copyHook(role: VariantRole, hook: string) {
    navigator.clipboard?.writeText(hook);
    setCopiedRole(role);
    setTimeout(() => setCopiedRole(null), 1500);
  }

  function submitUrl(role: VariantRole) {
    const trimmed = urlDraft.trim();
    if (!isValidTiktokUrl(trimmed)) {
      setUrlError("Paste a valid TikTok video URL (https://tiktok.com/...).");
      return;
    }
    setUrlError(null);
    startTracking(role, trimmed);
    setUrlDraft("");
  }

  if (!loaded) return null;

  const status = getCampaignStatus(campaign.variants);
  const published = getPublishedCount(campaign.variants);
  const nextVariant = getNextActionVariant(campaign.variants);

  return (
    <>
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Campaigns</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Run 3-variant content experiments and track which videos drive
          product clicks.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Main workspace */}
        <div className="flex flex-col gap-6 lg:col-span-8">
          {/* Active campaign */}
          <section className="border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border bg-secondary p-4">
              <h3 className="text-lg font-semibold tracking-tight">
                Active Campaign: {campaign.name}
              </h3>
              <StatusPill tone={status === "ready" ? "idle" : "active"}>
                {campaignStatusLabel(status)}
              </StatusPill>
            </div>
            <div className="grid grid-cols-2 gap-4 border-b border-border p-4 text-sm md:grid-cols-5">
              <div className="flex flex-col gap-1 md:col-span-2">
                <MonoLabel>Hypothesis</MonoLabel>
                <p className="pr-4">{campaign.hypothesis}</p>
              </div>
              <div className="flex flex-col gap-1">
                <MonoLabel>Primary Metric</MonoLabel>
                <p>{campaign.primaryMetric}</p>
              </div>
              <div className="flex flex-col gap-1">
                <MonoLabel>CTA</MonoLabel>
                <p>{campaign.cta}</p>
              </div>
              <div className="flex flex-col gap-1">
                <MonoLabel>Tracking Window</MonoLabel>
                <p>{campaign.trackingWindowLabel}</p>
              </div>
            </div>
            <div className="p-4">
              <div className="mb-2 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Progress {published}/3 variants published
              </div>
              <div className="flex w-full items-center gap-2">
                {campaign.variants.map((v) => (
                  <div
                    key={v.role}
                    className={`h-1 flex-1 ${
                      variantStatusTone(v.status) === "active"
                        ? "bg-primary"
                        : "bg-secondary"
                    }`}
                  />
                ))}
              </div>
              <div className="mt-2 flex justify-between font-mono text-[10px] uppercase text-muted-foreground">
                {campaign.variants.map((v) => (
                  <span key={v.role}>
                    {stepperLabel(v, nextVariant?.role ?? null)}
                  </span>
                ))}
              </div>
            </div>
          </section>

          {/* Variant cards */}
          <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {campaign.variants.map((v) => {
              const isNext = v.role === nextVariant?.role;
              const isLive = variantStatusTone(v.status) === "active";
              return (
                <div
                  key={v.role}
                  className={`flex h-full flex-col bg-card ${
                    isNext ? "border-2 border-primary" : "border border-border"
                  }`}
                >
                  <div className="flex min-h-[60px] items-start justify-between gap-2 border-b border-border bg-secondary p-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex size-6 items-center justify-center font-mono text-xs ${
                          v.status === "queued"
                            ? "border border-border bg-card"
                            : "bg-primary text-primary-foreground"
                        }`}
                      >
                        {v.role}
                      </span>
                      <div>
                        <h4 className="font-mono text-xs font-bold">{v.title}</h4>
                        <span className="block font-mono text-[10px] uppercase text-muted-foreground">
                          {v.roleLabel}
                        </span>
                      </div>
                    </div>
                    <StatusPill tone={variantStatusTone(v.status)}>
                      {variantStatusLabel(v.status)}
                    </StatusPill>
                  </div>

                  <div className="flex flex-1 flex-col gap-3 p-3">
                    <div>
                      <span className="mb-1 block font-mono text-[10px] uppercase text-muted-foreground">
                        Hook
                      </span>
                      <p
                        className={`border-l-2 border-border pl-2 text-sm italic ${
                          v.status === "queued" ? "text-muted-foreground" : ""
                        }`}
                      >
                        &quot;{v.hook}&quot;
                      </p>
                    </div>

                    {isLive && v.metrics && (
                      <div className="mt-auto grid grid-cols-3 gap-2 border border-border bg-secondary p-2 font-mono text-xs">
                        <div className="flex flex-col">
                          <span className="text-[10px] uppercase text-muted-foreground">
                            Views
                          </span>
                          <span>{v.metrics.views.toLocaleString()}</span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[10px] uppercase text-muted-foreground">
                            Clicks
                          </span>
                          <span>{v.metrics.clicks.toLocaleString()}</span>
                        </div>
                        <div className="flex flex-col">
                          <span className="text-[10px] uppercase text-muted-foreground">
                            Clicks/1K
                          </span>
                          <span>
                            {clicksPer1k(v.metrics.views, v.metrics.clicks)}
                          </span>
                        </div>
                      </div>
                    )}

                    {isNext && v.status === "ready_to_record" && (
                      <div className="mt-auto flex flex-col gap-1">
                        <Input
                          value={urlDraft}
                          onChange={(e) => {
                            setUrlDraft(e.target.value);
                            setUrlError(null);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") submitUrl(v.role);
                          }}
                          placeholder="Paste TikTok URL..."
                          className="text-sm"
                        />
                        {urlError && (
                          <p className="text-xs text-destructive">{urlError}</p>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          className="mt-1"
                          onClick={() => submitUrl(v.role)}
                        >
                          Start Tracking
                        </Button>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-2 border-t border-border p-2">
                    {isLive ? (
                      <Button asChild size="sm" variant="outline">
                        <Link href="/videos">View Metrics</Link>
                      </Button>
                    ) : isNext ? (
                      <>
                        <Button asChild size="sm">
                          <Link href={`/campaigns/brief/${v.role.toLowerCase()}`}>
                            View Recording Brief
                          </Link>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-1"
                          onClick={() => copyHook(v.role, v.hook)}
                        >
                          {copiedRole === v.role ? (
                            <Check className="size-3.5" />
                          ) : (
                            <Copy className="size-3.5" />
                          )}
                          {copiedRole === v.role ? "Copied!" : "Copy Hook"}
                        </Button>
                      </>
                    ) : (
                      <Button
                        asChild
                        size="sm"
                        variant="outline"
                        className="text-muted-foreground"
                      >
                        <Link href={`/campaigns/brief/${v.role.toLowerCase()}`}>
                          Preview Brief
                        </Link>
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </section>

          {/* Metrics table */}
          <section className="mt-4 border border-border bg-card">
            <div className="border-b border-border p-4">
              <h3 className="text-lg font-semibold tracking-tight">Metrics</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead className="border-b border-border bg-secondary font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="p-3 font-medium">Variant</th>
                    <th className="p-3 font-medium">Role</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 text-right font-medium">Views</th>
                    <th className="p-3 text-right font-medium">Likes</th>
                    <th className="p-3 text-right font-medium">Comments</th>
                    <th className="p-3 text-right font-medium">Clicks</th>
                    <th className="p-3 text-right font-medium">Clicks/1K</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border font-mono text-xs">
                  {campaign.variants.map((v) => {
                    const isLive = variantStatusTone(v.status) === "active";
                    return (
                      <tr key={v.role} className="hover:bg-secondary/50">
                        <td className="flex items-center gap-2 p-3">
                          <span
                            className={`flex size-5 items-center justify-center text-[10px] ${
                              v.status === "queued"
                                ? "border border-border bg-card"
                                : "bg-primary text-primary-foreground"
                            }`}
                          >
                            {v.role}
                          </span>
                          {v.title}
                        </td>
                        <td className="p-3">{v.roleLabel}</td>
                        <td className="p-3">
                          <StatusPill tone={variantStatusTone(v.status)}>
                            {variantStatusLabel(v.status)}
                          </StatusPill>
                        </td>
                        <td className="p-3 text-right">
                          {isLive && v.metrics
                            ? v.metrics.views.toLocaleString()
                            : "—"}
                        </td>
                        <td className="p-3 text-right">
                          {isLive && v.metrics
                            ? v.metrics.likes.toLocaleString()
                            : "—"}
                        </td>
                        <td className="p-3 text-right">
                          {isLive && v.metrics
                            ? v.metrics.comments.toLocaleString()
                            : "—"}
                        </td>
                        <td className="p-3 text-right">
                          {isLive && v.metrics
                            ? v.metrics.clicks.toLocaleString()
                            : "—"}
                        </td>
                        <td className="p-3 text-right">
                          {isLive && v.metrics
                            ? clicksPer1k(v.metrics.views, v.metrics.clicks)
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* Right rail */}
        <div className="flex flex-col gap-6 lg:col-span-4">
          <div className="border border-border bg-card">
            <div className="border-b border-border bg-secondary p-4">
              <h3 className="mb-1 text-sm font-semibold">Next Action</h3>
              {nextVariant && (
                <p className="text-sm font-semibold">
                  Record Variant {nextVariant.role}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-4 p-4">
              {nextVariant ? (
                <>
                  <p className="text-xs text-muted-foreground">
                    Record the {nextVariant.title.toLowerCase()} treatment, add
                    captions, publish it on TikTok, then paste the URL to start
                    tracking.
                  </p>
                  <div className="flex flex-col gap-2">
                    <Button asChild size="sm">
                      <Link
                        href={`/campaigns/brief/${nextVariant.role.toLowerCase()}`}
                      >
                        View Recording Brief
                      </Link>
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      onClick={() => copyHook(nextVariant.role, nextVariant.hook)}
                    >
                      {copiedRole === nextVariant.role ? (
                        <Check className="size-3.5" />
                      ) : (
                        <Copy className="size-3.5" />
                      )}
                      {copiedRole === nextVariant.role ? "Copied!" : "Copy Hook"}
                    </Button>
                  </div>
                </>
              ) : (
                <p className="text-xs text-muted-foreground">
                  All variants are tracking. Check back once each 72h window
                  completes.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
