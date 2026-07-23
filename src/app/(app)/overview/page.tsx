"use client";

import Link from "next/link";
import {
  Video,
  ExternalLink,
  ArrowRight,
  Lightbulb,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  useCampaign,
  getCampaignStatus,
  campaignStatusLabel,
  getPublishedCount,
  getNextActionVariant,
  variantStatusLabel,
  variantStatusTone,
} from "@/lib/campaign";
import { useHypotheses, STATUS_LABEL } from "@/lib/hypotheses";
import { SEED_INSIGHTS, insightClicksPer1k } from "@/lib/insights";

/* ---- Seed data not yet backed by a real store (account-wide video/click
   history) — unrelated to the single active campaign above, so it stays as
   illustrative seed content for now. Hypothesis Backlog and Recent Insights
   below read from the real shared stores (lib/hypotheses, lib/insights). ---- */

const KPIS = [
  { label: "Total Videos", value: "12" },
  { label: "Total Views", value: "45.2K" },
  { label: "Total Clicks", value: "1.2K" },
  { label: "Clicks / 1K Views", value: "26.5" },
];

/* ---- Small primitives ---- */

function StatusPill({
  children,
  tone = "idle",
}: {
  children: React.ReactNode;
  tone?: "active" | "idle";
}) {
  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-xs uppercase tracking-wide ${
        tone === "active"
          ? "bg-[#ECFDF5] text-success"
          : "bg-secondary text-muted-foreground"
      }`}
    >
      {children}
    </span>
  );
}

function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

/* ---- Page ---- */

export default function OverviewPage() {
  const { campaign, loaded: campaignLoaded } = useCampaign();
  const { hypotheses, loaded: hypothesesLoaded } = useHypotheses();
  const status = getCampaignStatus(campaign.variants);
  const published = getPublishedCount(campaign.variants);
  const nextVariant = getNextActionVariant(campaign.variants);

  if (!campaignLoaded || !hypothesesLoaded) return null;

  const backlog = hypotheses
    .filter((h) => h.status === "generated" || h.status === "approved")
    .slice(0, 3);

  return (
    <>
      <div className="mb-2 flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Overview</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          High-level metrics and active experimentation status.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
        {/* Left column */}
        <div className="flex flex-col gap-4 md:col-span-8">
          {/* KPIs */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {KPIS.map((k) => (
              <div
                key={k.label}
                className="flex h-28 flex-col justify-between border border-border bg-card p-4 transition-colors hover:bg-secondary"
              >
                <MonoLabel>{k.label}</MonoLabel>
                <span className="font-mono text-xl font-semibold">
                  {k.value}
                </span>
              </div>
            ))}
          </div>

          <div className="flex justify-end px-1">
            <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground/70">
              Last updated 12 min ago
            </span>
          </div>

          {/* Active campaign */}
          <div className="flex flex-col border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border bg-secondary p-4">
              <h3 className="text-lg font-semibold tracking-tight">
                Active Campaign: {campaign.name}
              </h3>
              <div className="flex items-center gap-2">
                <Button
                  asChild
                  variant="outline"
                  size="sm"
                  className="gap-1 font-mono text-xs"
                >
                  <Link href="/campaigns">
                    <ExternalLink className="size-3.5" />
                    Open Campaign
                  </Link>
                </Button>
                <StatusPill tone={status === "ready" ? "idle" : "active"}>
                  {campaignStatusLabel(status)}
                </StatusPill>
              </div>
            </div>

            <div className="flex flex-col gap-6 p-5">
              <div className="flex flex-col gap-1">
                <MonoLabel>Hypothesis Under Test</MonoLabel>
                <p className="border-l-2 border-primary py-1 pl-3 text-sm font-medium">
                  &quot;{campaign.hypothesis}&quot;
                </p>
              </div>

              <div className="flex items-end justify-between border-b border-border pb-2">
                <MonoLabel>Variants</MonoLabel>
                <span className="rounded bg-secondary px-2 py-1 font-mono text-xs">
                  Progress: {published}/3 variants published
                </span>
              </div>

              <div className="flex flex-col gap-2">
                {campaign.variants.map((v) => (
                  <div
                    key={v.role}
                    className="flex items-center justify-between rounded border border-border p-3 transition-colors hover:bg-secondary"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`size-2 rounded-full ${
                          variantStatusTone(v.status) === "active"
                            ? "bg-success"
                            : "bg-border"
                        }`}
                      />
                      <span className="text-sm font-medium">
                        Variant {v.role}: {v.title}
                      </span>
                    </div>
                    <StatusPill tone={variantStatusTone(v.status)}>
                      {variantStatusLabel(v.status)}
                    </StatusPill>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4 md:col-span-4">
          {/* Next action */}
          <div className="flex flex-col gap-4 border border-l-4 border-border border-l-primary bg-card p-5">
            <div className="flex items-center gap-2">
              <Video className="size-5" />
              <MonoLabel>Next Action</MonoLabel>
            </div>
            {nextVariant ? (
              <>
                <h3 className="text-lg font-semibold leading-tight tracking-tight">
                  Record Variant {nextVariant.role}: {nextVariant.title}
                </h3>
                <p className="text-sm text-muted-foreground">
                  Script, hook, and checklist are ready. Record the next
                  variant and paste the TikTok URL after publishing.
                </p>
                <Button asChild className="mt-2 gap-2">
                  <Link href={`/campaigns/brief/${nextVariant.role.toLowerCase()}`}>
                    View Recording Brief
                    <ArrowRight className="size-4" />
                  </Link>
                </Button>
              </>
            ) : (
              <>
                <h3 className="text-lg font-semibold leading-tight tracking-tight">
                  All variants are tracking
                </h3>
                <p className="text-sm text-muted-foreground">
                  Check back once each 72h tracking window completes to see
                  the campaign insight.
                </p>
              </>
            )}
          </div>

          {/* Hypothesis backlog */}
          <div className="flex flex-col border border-border bg-card">
            <div className="border-b border-border bg-secondary p-3">
              <MonoLabel>Hypothesis Backlog</MonoLabel>
            </div>
            <div className="flex flex-col gap-2 p-3">
              {backlog.length > 0 ? (
                backlog.map((h) => (
                  <Link
                    key={h.id}
                    href="/hypotheses"
                    className="cursor-pointer rounded border border-border p-3 transition-colors hover:border-primary"
                  >
                    <h5 className="mb-1 text-sm font-medium">{h.title}</h5>
                    <span className="font-mono text-xs text-muted-foreground">
                      {STATUS_LABEL[h.status]}
                    </span>
                  </Link>
                ))
              ) : (
                <Link
                  href="/hypotheses"
                  className="rounded border border-dashed border-border p-3 text-center text-xs text-muted-foreground transition-colors hover:border-primary"
                >
                  No hypotheses yet — generate your first batch.
                </Link>
              )}
            </div>
          </div>

          {/* Recent insights (no confidence labels — brief override) */}
          <div className="flex flex-col border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border bg-secondary p-3">
              <MonoLabel>Recent Insights</MonoLabel>
              <Lightbulb className="size-4 text-muted-foreground" />
            </div>
            <div className="flex flex-col gap-2 p-3">
              {SEED_INSIGHTS.length > 0 ? (
                SEED_INSIGHTS.map((i) => (
                  <Link
                    key={i.id}
                    href={`/insights?id=${i.id}`}
                    className="rounded bg-secondary p-3 transition-colors hover:bg-secondary/70"
                  >
                    <h5 className="mb-2 text-sm font-medium leading-tight">
                      {i.hypothesis}
                    </h5>
                    <p className="mb-1 text-xs text-muted-foreground">
                      Evidence: {insightClicksPer1k(i.control)} vs{" "}
                      {insightClicksPer1k(i.treatment)} clicks / 1K views
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Recommendation: {i.recommendedNextTest}
                    </p>
                  </Link>
                ))
              ) : (
                <p className="rounded border border-dashed border-border p-3 text-center text-xs text-muted-foreground">
                  No insights yet — insights appear once a campaign completes.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
