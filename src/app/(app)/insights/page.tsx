"use client";

// Screen 6 (Experiment Results) + Screen 7 (Next Hypothesis Candidates) per
// actionable_ui_ux_changes.md sections 10 and 11.
//
// Structure:
//   1 Research Question
//   2 Hypothesis Tested
//   3 Variant Comparison (control / treatment / optional alternative)
//   4 Observed Result
//   5 Supported Learning
//   6 What Is Not Proven
//   7 Experiment Limitations
//   8 Outcome Classification (plain-language)
//   9 Next Hypothesis Candidates (three cards)

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, Lightbulb, Sparkles, ArrowRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { clicksPer1k, formatTimestamp } from "@/lib/experiment";
import {
  SEED_INSIGHTS,
  insightClicksPer1k,
  toHypothesis,
  candidateToHypothesis,
  type Insight,
  type ComparedVariant,
  type NextCandidate,
} from "@/lib/insights";
import { insightApi, type InsightSummary } from "@/lib/api-client";
import { useEffect, useState as useApiState } from "react";
import { useHypotheses } from "@/lib/hypotheses";

function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

function ResultSection({
  index,
  title,
  children,
  testId,
}: {
  index: number;
  title: string;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <section data-testid={testId} className="flex flex-col gap-2 border border-border bg-card p-5">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          Section {index}
        </span>
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function ComparisonRow({ v }: { v: ComparedVariant }) {
  return (
    <tr className="border-b border-border last:border-b-0">
      <td className="p-3">
        <div className="flex items-center gap-2">
          <span className="flex size-6 items-center justify-center bg-primary font-mono text-xs text-primary-foreground">
            {v.role}
          </span>
          <span className="text-sm font-medium">{v.title}</span>
        </div>
      </td>
      <td className="p-3 text-sm">{v.roleLabel}</td>
      <td className="p-3 text-right font-mono text-xs">{v.views.toLocaleString()}</td>
      <td className="p-3 text-right font-mono text-xs">{v.clicks.toLocaleString()}</td>
      <td className="p-3 text-right font-mono text-xs font-semibold">{insightClicksPer1k(v)}</td>
    </tr>
  );
}

function CandidateCard({
  candidate,
  insight,
  alreadyAdded,
  onAdd,
  onDismiss,
  dismissed,
}: {
  candidate: NextCandidate;
  insight: Insight;
  alreadyAdded: boolean;
  onAdd: (c: NextCandidate) => void;
  onDismiss: (id: string) => void;
  dismissed: boolean;
}) {
  const isRecommended = !!candidate.recommended;
  return (
    <div
      data-testid={"candidate-card-" + candidate.id}
      className={"flex flex-col gap-3 border bg-card p-4 " + (isRecommended ? "border-primary" : "border-border") + (dismissed ? " opacity-60" : "")}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {candidate.kind}
        </span>
        {isRecommended && (
          <span className="rounded bg-primary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-primary-foreground">
            Recommended
          </span>
        )}
      </div>
      <p className="text-sm font-medium leading-relaxed">{candidate.statement}</p>
      <div className="flex flex-col gap-1 border-t border-border pt-2">
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          Why This Follows
        </span>
        <p className="text-xs text-muted-foreground">{candidate.whyThisFollows}</p>
      </div>
      <div className="mt-auto flex flex-wrap gap-2">
        <Button size="sm" variant={isRecommended ? "default" : "outline"} className="flex-1 gap-1" onClick={() => onAdd(candidate)} disabled={dismissed}>
          {alreadyAdded ? "View in Research" : "Review Hypothesis"}
          <ArrowRight className="size-3.5" />
        </Button>
        <Button size="sm" variant="outline" className="gap-1" onClick={() => onDismiss(candidate.id)} disabled={dismissed || alreadyAdded}>
          <X className="size-3.5" />
          Not Relevant
        </Button>
      </div>
    </div>
  );
}

function InsightDetail({ insight }: { insight: Insight }) {
  const router = useRouter();
  const { hypotheses, addHypothesis } = useHypotheses();
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  const legacyFollowUp = toHypothesis(insight);
  const candidates = insight.nextCandidates ?? [];

  const totalViews = insight.control.views + insight.treatment.views + (insight.alternative?.views ?? 0);
  const totalClicks = insight.control.clicks + insight.treatment.clicks + (insight.alternative?.clicks ?? 0);

  function handleCandidateAdd(c: NextCandidate) {
    const h = candidateToHypothesis(insight, c);
    const already = hypotheses.some((x) => x.id === h.id);
    if (already) {
      router.push("/research");
      return;
    }
    addHypothesis(h);
  }

  function handleLegacyFollowUp() {
    const already = hypotheses.some((x) => x.id === legacyFollowUp.id);
    if (already) router.push("/research");
    else addHypothesis(legacyFollowUp);
  }

  const legacyAlreadyAdded = hypotheses.some((x) => x.id === legacyFollowUp.id);

  return (
    <div className="flex flex-col gap-4">
      <div data-testid="results-header" className="flex flex-col gap-2 border border-border bg-card p-5">
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>Experiment Results</span>
          <span className="rounded bg-[#ECFDF5] px-1.5 py-0.5 text-success">Completed</span>
        </div>
        <h2 className="text-2xl font-semibold tracking-tight">{insight.experimentName}</h2>
        <p className="text-sm text-muted-foreground">What did we learn and what should we test next?</p>
        <div className="grid grid-cols-3 gap-3 border-t border-border pt-3 text-sm">
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Primary Metric</span>
            <span>{insight.primaryMetric}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Tracking Window</span>
            <span>{insight.windowHours}h per variant</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Completed</span>
            <span>{formatTimestamp(insight.completedAt)}</span>
          </div>
        </div>
      </div>

      {insight.researchQuestion && (
        <ResultSection index={1} title="Research Question" testId="section-research-question">
          <p className="text-base">{insight.researchQuestion}</p>
        </ResultSection>
      )}

      <ResultSection index={2} title="Hypothesis Tested" testId="section-hypothesis-tested">
        <p className="border-l-2 border-primary py-1 pl-3 text-sm">&quot;{insight.hypothesis}&quot;</p>
      </ResultSection>

      <ResultSection index={3} title="Variant Comparison" testId="section-variant-comparison">
        <div className="overflow-x-auto">
          <table className="w-full border border-border">
            <thead className="bg-secondary font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="p-3 text-left font-medium">Variant</th>
                <th className="p-3 text-left font-medium">Role</th>
                <th className="p-3 text-right font-medium">Views</th>
                <th className="p-3 text-right font-medium">Clicks</th>
                <th className="p-3 text-right font-medium">Clicks / 1K</th>
              </tr>
            </thead>
            <tbody>
              <ComparisonRow v={insight.control} />
              <ComparisonRow v={insight.treatment} />
              {insight.alternative && <ComparisonRow v={insight.alternative} />}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex justify-end gap-4 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>Total Views: {totalViews.toLocaleString()}</span>
          <span>Total Clicks: {totalClicks.toLocaleString()}</span>
          <span>Combined efficiency {clicksPer1k(totalViews, totalClicks)}</span>
        </div>
      </ResultSection>

      <ResultSection index={4} title="Observed Result" testId="section-observed-result">
        <div className="flex items-center justify-between border border-border bg-primary p-4 text-primary-foreground">
          <span className="font-mono text-xs uppercase tracking-widest">Treatment lift vs Control</span>
          <span className="font-mono text-2xl">{insight.lift}x</span>
        </div>
        <p className="text-sm text-muted-foreground">{insight.evidenceBasis}</p>
      </ResultSection>

      <ResultSection index={5} title="Supported Learning" testId="section-supported-learning">
        <p className="text-sm">{insight.supportedLearning}</p>
      </ResultSection>

      <ResultSection index={6} title="What Is Not Proven" testId="section-not-proven">
        <ul className="flex flex-col gap-2">
          {insight.doNotInferYet.map((caveat) => (
            <li key={caveat} className="flex gap-2 text-sm text-muted-foreground">
              <span aria-hidden>-</span>
              <span>{caveat}</span>
            </li>
          ))}
        </ul>
      </ResultSection>

      {insight.limitations && insight.limitations.length > 0 && (
        <ResultSection index={7} title="Experiment Limitations" testId="section-limitations">
          <ul className="flex flex-col gap-2">
            {insight.limitations.map((lim) => (
              <li key={lim} className="flex gap-2 text-sm text-muted-foreground">
                <span aria-hidden>-</span>
                <span>{lim}</span>
              </li>
            ))}
          </ul>
        </ResultSection>
      )}

      {insight.outcome && (
        <ResultSection index={8} title="Outcome Classification" testId="section-outcome">
          <div className="flex flex-col gap-2 border border-border bg-secondary p-3">
            <span className="text-lg font-semibold">{insight.outcome.label}</span>
            <p className="text-sm text-muted-foreground">{insight.outcome.description}</p>
          </div>
        </ResultSection>
      )}

      {candidates.length > 0 ? (
        <section data-testid="next-candidates" className="flex flex-col gap-3 border border-border bg-card p-5">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Section 9</span>
            <h3 className="text-base font-semibold tracking-tight">Next Hypothesis Candidates</h3>
          </div>
          <p className="text-xs text-muted-foreground">What is the most valuable uncertainty to test next?</p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {candidates.map((c) => {
              const h = candidateToHypothesis(insight, c);
              const already = hypotheses.some((x) => x.id === h.id);
              return (
                <CandidateCard
                  key={c.id}
                  candidate={c}
                  insight={insight}
                  alreadyAdded={already}
                  dismissed={dismissedIds.has(c.id)}
                  onAdd={handleCandidateAdd}
                  onDismiss={(id) => setDismissedIds((prev) => { const n = new Set(prev); n.add(id); return n; })}
                />
              );
            })}
          </div>
        </section>
      ) : (
        <section data-testid="follow-up-legacy" className="flex flex-col gap-3 border border-border bg-card p-5">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4" />
            <h3 className="text-sm font-semibold">Follow-up Hypothesis Preview</h3>
          </div>
          <p className="text-sm font-semibold">&quot;{insight.followUp.statement}&quot;</p>
          <p className="text-xs text-muted-foreground">{insight.followUp.rationale}</p>
          <Button onClick={handleLegacyFollowUp} className="w-fit gap-2">
            {legacyAlreadyAdded ? "View in Research" : "Add to Research"}
            <ArrowRight className="size-4" />
          </Button>
        </section>
      )}
    </div>
  );
}

function InsightsPageInner() {
  const searchParams = useSearchParams();
  const idParam = searchParams.get("id");
  const [selectedId, setSelectedId] = useState<string | null>(idParam ?? null);
  const { loaded } = useHypotheses();
  const [apiInsights, setApiInsights] = useApiState<InsightSummary[]>([]);

  useEffect(() => {
    insightApi.list().then((items) => {
      setApiInsights(items);
      if (!selectedId && items.length > 0) setSelectedId(items[0].id);
    }).catch(() => {});
  }, []);

  if (!loaded) return null;

  const insights = apiInsights;
  const selected = SEED_INSIGHTS.find((i) => i.id === selectedId) ?? null;

  return (
    <>
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Experiment Results</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          What did we learn, what remains unknown, and what should we test next?
        </p>
      </div>

      {insights.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 border border-dashed border-border bg-card px-6 py-20 text-center">
          <Lightbulb className="size-7 text-muted-foreground" />
          <h3 className="text-lg font-semibold tracking-tight">No insights yet</h3>
          <p className="max-w-md text-sm text-muted-foreground">
            Insights appear once an experiment completes its tracking windows.
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
              {insights.map((insight) => {
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
                      <span className="text-sm font-semibold">{(insight as Record<string, unknown>)["experimentName"] as string ?? (insight as Record<string, unknown>)["hypothesis_text"] as string ?? "Insight"}</span>
                      <span className="shrink-0 rounded bg-primary px-1.5 py-0.5 font-mono text-[10px] text-primary-foreground">
                        {(insight as {outcome_type?: string}).outcome_type ?? "result"}
                      </span>
                    </div>
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                      {(insight as {hypothesis?: string}).hypothesis ?? (insight as {supported_learning?: string}).supported_learning ?? ""}
                    </p>
                    <span className="font-mono text-[10px] uppercase text-muted-foreground">
                      {formatTimestamp((insight as {completedAt?: string}).completedAt ?? (insight as {generated_at?: string}).generated_at ?? "")}
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
