"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Lightbulb, Sparkles, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { clicksPer1k, formatTimestamp } from "@/lib/campaign";
import {
  SEED_INSIGHTS,
  insightClicksPer1k,
  toHypothesis,
  type Insight,
  type ComparedVariant,
} from "@/lib/insights";
import { useHypotheses } from "@/lib/hypotheses";

function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

function VariantCard({ variant }: { variant: ComparedVariant }) {
  return (
    <div className="flex flex-col border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border bg-secondary p-3">
        <span className="flex size-6 items-center justify-center bg-primary font-mono text-xs text-primary-foreground">
          {variant.role}
        </span>
        <div>
          <h4 className="font-mono text-xs font-bold">{variant.title}</h4>
          <span className="block font-mono text-[10px] uppercase text-muted-foreground">
            {variant.roleLabel}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-3 divide-x divide-border">
        <div className="p-3">
          <div className="mb-1 font-mono text-[10px] uppercase text-muted-foreground">
            Views
          </div>
          <div className="font-mono text-lg">{variant.views.toLocaleString()}</div>
        </div>
        <div className="p-3">
          <div className="mb-1 font-mono text-[10px] uppercase text-muted-foreground">
            Clicks
          </div>
          <div className="font-mono text-lg">{variant.clicks.toLocaleString()}</div>
        </div>
        <div className="p-3">
          <div className="mb-1 font-mono text-[10px] uppercase text-muted-foreground">
            Clicks / 1K
          </div>
          <div className="font-mono text-lg">{insightClicksPer1k(variant)}</div>
        </div>
      </div>
    </div>
  );
}

function InsightDetail({ insight }: { insight: Insight }) {
  const router = useRouter();
  const { hypotheses, addHypothesis } = useHypotheses();

  const followUpHypothesis = toHypothesis(insight);
  const alreadyAdded = hypotheses.some((h) => h.id === followUpHypothesis.id);

  const totalViews = insight.control.views + insight.treatment.views;
  const totalClicks = insight.control.clicks + insight.treatment.clicks;

  function handleFollowUpClick() {
    if (alreadyAdded) {
      router.push("/hypotheses");
    } else {
      addHypothesis(followUpHypothesis);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="border border-border bg-card">
        <div className="border-b border-border bg-secondary p-4">
          <h3 className="mb-1 text-lg font-semibold tracking-tight">
            {insight.campaignName}
          </h3>
          <p className="text-sm italic text-muted-foreground">
            &quot;{insight.hypothesis}&quot;
          </p>
        </div>
        <div className="grid grid-cols-3 divide-x divide-border">
          <div className="p-3">
            <MonoLabel>Primary Metric</MonoLabel>
            <p className="mt-1 text-sm font-semibold">{insight.primaryMetric}</p>
          </div>
          <div className="p-3">
            <MonoLabel>Tracking Window</MonoLabel>
            <p className="mt-1 text-sm font-semibold">{insight.windowHours}h per variant</p>
          </div>
          <div className="p-3">
            <MonoLabel>Completed</MonoLabel>
            <p className="mt-1 text-sm font-semibold">
              {formatTimestamp(insight.completedAt)}
            </p>
          </div>
        </div>
      </div>

      {/* Completed-campaign summary metrics */}
      <div className="grid grid-cols-3 gap-4">
        <div className="border border-border bg-card p-4">
          <MonoLabel>Total Views</MonoLabel>
          <div className="mt-1 font-mono text-xl">{totalViews.toLocaleString()}</div>
        </div>
        <div className="border border-border bg-card p-4">
          <MonoLabel>Total Clicks</MonoLabel>
          <div className="mt-1 font-mono text-xl">{totalClicks.toLocaleString()}</div>
        </div>
        <div className="border border-border bg-card p-4">
          <MonoLabel>Combined Clicks / 1K</MonoLabel>
          <div className="mt-1 font-mono text-xl">{clicksPer1k(totalViews, totalClicks)}</div>
        </div>
      </div>

      {/* Compared variants */}
      <div>
        <h4 className="mb-2 text-sm font-semibold tracking-tight">Compared Variants</h4>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <VariantCard variant={insight.control} />
          <VariantCard variant={insight.treatment} />
        </div>
      </div>

      {/* Evidence & lift */}
      <div className="border border-border bg-card">
        <div className="flex items-center justify-between bg-primary p-4 text-primary-foreground">
          <span className="font-mono text-xs font-bold uppercase tracking-widest">
            Lift vs Control
          </span>
          <span className="font-mono text-2xl">{insight.lift}x</span>
        </div>
        <p className="p-4 text-sm text-muted-foreground">{insight.evidenceBasis}</p>
      </div>

      <div className="border border-border bg-card p-4">
        <MonoLabel>Supported Learning</MonoLabel>
        <p className="mt-2 text-sm">{insight.supportedLearning}</p>
      </div>

      <div className="border border-dashed border-border bg-secondary p-4">
        <MonoLabel>Do Not Infer Yet</MonoLabel>
        <ul className="mt-2 flex flex-col gap-2">
          {insight.doNotInferYet.map((caveat) => (
            <li key={caveat} className="flex gap-2 text-sm text-muted-foreground">
              <span aria-hidden>—</span>
              <span>{caveat}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="border border-border bg-card p-4">
        <MonoLabel>Recommended Next Test</MonoLabel>
        <p className="mt-2 text-sm">{insight.recommendedNextTest}</p>
      </div>

      {/* Follow-up hypothesis preview */}
      <div className="border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border bg-secondary px-4 py-3">
          <Sparkles className="size-4" />
          <h3 className="text-sm font-semibold tracking-tight">
            Follow-up Hypothesis Preview
          </h3>
        </div>
        <div className="flex flex-col gap-3 p-4">
          <p className="text-sm font-semibold leading-relaxed">
            &quot;{insight.followUp.statement}&quot;
          </p>
          <div className="flex flex-col gap-2 border-t border-border pt-3">
            <div>
              <MonoLabel>Category</MonoLabel>
              <p className="mt-0.5 text-sm">{insight.followUp.category}</p>
            </div>
            <div>
              <MonoLabel>Rationale</MonoLabel>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {insight.followUp.rationale}
              </p>
            </div>
          </div>
          <Button onClick={handleFollowUpClick} className="mt-1 gap-2 self-start">
            {alreadyAdded ? "View in Hypotheses" : "Add to Hypotheses"}
            <ArrowRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function InsightsPageInner() {
  const searchParams = useSearchParams();
  const idParam = searchParams.get("id");
  const [selectedId, setSelectedId] = useState<string | null>(
    idParam ?? SEED_INSIGHTS[0]?.id ?? null,
  );
  const { loaded } = useHypotheses();

  if (!loaded) return null;

  const selected = SEED_INSIGHTS.find((i) => i.id === selectedId) ?? null;

  return (
    <>
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Insights</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Evidence-backed results from completed campaigns, with a drafted
          follow-up hypothesis for each.
        </p>
      </div>

      {SEED_INSIGHTS.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 border border-dashed border-border bg-card px-6 py-20 text-center">
          <Lightbulb className="size-7 text-muted-foreground" />
          <h3 className="text-lg font-semibold tracking-tight">No insights yet</h3>
          <p className="max-w-md text-sm text-muted-foreground">
            Insights appear once a campaign completes its tracking windows.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Insight Library */}
          <div className="flex flex-col border border-border bg-card lg:col-span-4">
            <div className="border-b border-border bg-secondary px-4 py-3">
              <h3 className="text-sm font-semibold tracking-tight">Insight Library</h3>
            </div>
            <div className="flex flex-col gap-3 p-3">
              {SEED_INSIGHTS.map((insight) => {
                const isSelected = insight.id === selectedId;
                return (
                  <button
                    key={insight.id}
                    onClick={() => setSelectedId(insight.id)}
                    className={`flex flex-col gap-2 border bg-card p-3 text-left transition-colors ${
                      isSelected ? "border-primary" : "border-border hover:border-foreground/30"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold">{insight.campaignName}</span>
                      <span className="shrink-0 rounded bg-primary px-1.5 py-0.5 font-mono text-[10px] text-primary-foreground">
                        {insight.lift}x
                      </span>
                    </div>
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                      {insight.hypothesis}
                    </p>
                    <span className="font-mono text-[10px] uppercase text-muted-foreground">
                      {formatTimestamp(insight.completedAt)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Detail */}
          <div className="lg:col-span-8">
            {selected ? (
              <InsightDetail key={selected.id} insight={selected} />
            ) : (
              <div className="border border-border bg-card p-6 text-center text-sm text-muted-foreground">
                Select an insight to inspect it.
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default function InsightsPage() {
  return (
    <Suspense fallback={null}>
      <InsightsPageInner />
    </Suspense>
  );
}
