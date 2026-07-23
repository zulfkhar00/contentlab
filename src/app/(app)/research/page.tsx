"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FlaskConical, Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useHypotheses,
  SEED_HYPOTHESES,
  STATUS_LABEL,
  RELATIONSHIP_LABEL,
  type Hypothesis,
  type Status,
} from "@/lib/hypotheses";
import { SEED_INSIGHTS, toHypothesis, type Insight } from "@/lib/insights";

const FILTERS: Array<Status | "all"> = [
  "all",
  "suggested",
  "draft",
  "approved",
  "testing",
  "learned",
  "rejected",
];

function findParentHypothesis(insightId: string): Hypothesis | null {
  const insight = SEED_INSIGHTS.find((i) => i.id === insightId);
  if (!insight) return null;
  return SEED_HYPOTHESES.find((h) => h.id === insight.sourceHypothesisId) ?? null;
}

function findRelatedInsight(hypothesisId: string): Insight | undefined {
  return SEED_INSIGHTS.find((i) => i.sourceHypothesisId === hypothesisId);
}

function StatusPill({ status }: { status: Status }) {
  const style =
    status === "approved"
      ? "bg-[#ECFDF5] text-success"
      : status === "suggested" || status === "testing"
        ? "bg-primary text-primary-foreground"
        : "border border-border bg-card text-muted-foreground";
  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${style}`}
    >
      {STATUS_LABEL[status]}
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

function DerivedFromLine({ h }: { h: Hypothesis }) {
  if (!h.parentInsightId) {
    return (
      <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
        Derived from: Initial product context
      </span>
    );
  }
  const parent = findParentHypothesis(h.parentInsightId);
  const relLabel = h.relationshipType ? RELATIONSHIP_LABEL[h.relationshipType] : null;
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
        Derived from: {parent ? parent.title : "prior experiment"}
      </span>
      {relLabel && (
        <span className="font-mono text-[10px] uppercase tracking-wide text-primary">
          {relLabel}
        </span>
      )}
    </div>
  );
}

export default function ResearchLibraryPage() {
  const router = useRouter();
  const {
    hypotheses,
    loaded,
    addHypothesis,
    updateHypothesis,
    removeHypothesis,
    setAll,
  } = useHypotheses();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Status | "all">("all");

  const selected = hypotheses.find((h) => h.id === selectedId) ?? null;

  const counts = useMemo(() => {
    const c: Record<Status | "all", number> = {
      all: hypotheses.length,
      suggested: 0,
      draft: 0,
      approved: 0,
      testing: 0,
      learned: 0,
      rejected: 0,
    };
    for (const h of hypotheses) c[h.status]++;
    return c;
  }, [hypotheses]);

  const visible = hypotheses.filter((h) => {
    const matchesFilter = filter === "all" || h.status === filter;
    const matchesSearch = h.title.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  function generateInitial() {
    setAll(SEED_HYPOTHESES);
    setSelectedId(SEED_HYPOTHESES[0].id);
  }

  function generateMore() {
    const n = hypotheses.length + 1;
    const fresh: Hypothesis = {
      id: `h-gen-${Date.now()}`,
      title: `New angle candidate #${n}`,
      statement:
        "A newly generated hypothesis exploring an untested angle for this audience.",
      category: "Generated",
      primaryMetric: "Clicks / 1K Views",
      rationale: "Suggested to explore an angle not yet covered by the backlog.",
      status: "suggested",
    };
    addHypothesis(fresh);
    setSelectedId(fresh.id);
  }

  function createFollowUp(h: Hypothesis, insight?: Insight) {
    const followUp: Hypothesis = insight
      ? toHypothesis(insight)
      : {
          id: `h-fu-${Date.now()}`,
          title: `Follow-up: ${h.title}`,
          statement: `Building on "${h.statement}" — testing a follow-up refinement.`,
          category: h.category,
          primaryMetric: h.primaryMetric,
          rationale: "Follow-up drafted from a completed experiment insight.",
          status: "suggested",
        };
    if (!hypotheses.some((existing) => existing.id === followUp.id)) {
      addHypothesis(followUp);
    }
    setSelectedId(followUp.id);
  }

  function createExperiment(id: string) {
    updateHypothesis(id, { status: "testing" });
    router.push("/experiments");
  }

  if (!loaded) return null;

  if (hypotheses.length === 0) {
    return (
      <>
        <div className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Research</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Every hypothesis in your product&apos;s learning graph — what you
            believe, why you believe it, and where each belief came from.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center gap-4 border border-dashed border-border bg-card px-6 py-20 text-center">
          <FlaskConical className="size-8 text-muted-foreground" />
          <div>
            <h3 className="text-lg font-semibold tracking-tight">
              No hypotheses yet
            </h3>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              Content Lab drafts your first batch from your onboarding context.
              Review, edit, and approve one before it becomes an experiment.
            </p>
          </div>
          <Button onClick={generateInitial} className="gap-2">
            <Sparkles className="size-4" />
            Generate Initial Hypotheses
          </Button>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Research</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            What you believe, why you believe it, and where each hypothesis
            came from.
          </p>
        </div>
        <Button onClick={generateMore} variant="outline" className="shrink-0 gap-2">
          <Sparkles className="size-4" />
          Generate More
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="flex flex-col gap-3 lg:col-span-4">
          <div className="flex items-center gap-2 border border-border bg-card px-2.5">
            <Search className="size-4 shrink-0 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search hypotheses..."
              className="h-9 flex-1 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
            />
          </div>

          <div className="flex flex-wrap gap-1">
            {FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                  filter === f
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:border-foreground/30"
                }`}
              >
                {f === "all" ? "All" : STATUS_LABEL[f]} ({counts[f]})
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-2">
            {visible.length === 0 && (
              <div className="border border-dashed border-border bg-card p-4 text-center text-xs text-muted-foreground">
                No hypotheses match this filter.
              </div>
            )}
            {visible.map((h) => {
              const isSelected = h.id === selectedId;
              return (
                <button
                  key={h.id}
                  onClick={() => setSelectedId(h.id)}
                  className={`flex flex-col gap-2 border bg-card p-3 text-left transition-colors ${
                    isSelected
                      ? "border-primary"
                      : "border-border hover:border-foreground/30"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="line-clamp-2 text-sm font-semibold">
                      {h.title}
                    </span>
                    <StatusPill status={h.status} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      {h.primaryMetric}
                    </span>
                  </div>
                  <DerivedFromLine h={h} />
                </button>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-8">
          {selected ? (
            <HypothesisInspector
              key={selected.id}
              hypothesis={selected}
              onCreateExperiment={createExperiment}
              onCreateFollowUp={createFollowUp}
              onReject={(id) => updateHypothesis(id, { status: "rejected" })}
              onRestore={(id) => updateHypothesis(id, { status: "suggested" })}
              onRemove={(id) => {
                removeHypothesis(id);
                setSelectedId(null);
              }}
            />
          ) : (
            <div className="border border-border bg-card p-6 text-center text-sm text-muted-foreground">
              Select a hypothesis to inspect it.
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function HypothesisInspector({
  hypothesis,
  onCreateExperiment,
  onCreateFollowUp,
  onReject,
  onRestore,
  onRemove,
}: {
  hypothesis: Hypothesis;
  onCreateExperiment: (id: string) => void;
  onCreateFollowUp: (h: Hypothesis, insight?: Insight) => void;
  onReject: (id: string) => void;
  onRestore: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  const h = hypothesis;
  const parent = h.parentInsightId ? findParentHypothesis(h.parentInsightId) : null;
  const relatedInsight = h.status === "learned" ? findRelatedInsight(h.id) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <div className="border border-border bg-card">
        <div className="flex items-start justify-between gap-3 border-b border-border bg-secondary p-4">
          <div className="flex flex-col gap-1">
            <h3 className="text-lg font-semibold tracking-tight">{h.title}</h3>
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {h.category} · {h.primaryMetric}
            </span>
          </div>
          <StatusPill status={h.status} />
        </div>
      </div>

      {h.researchQuestion && (
        <div className="border border-border bg-card p-4">
          <MonoLabel>Research Question</MonoLabel>
          <p className="mt-2 text-sm">{h.researchQuestion}</p>
        </div>
      )}

      <div className="border border-border bg-card p-4">
        <MonoLabel>Hypothesis</MonoLabel>
        <p className="mt-2 text-sm">{h.statement}</p>
      </div>

      {(h.independentVariable ||
        h.controlCondition ||
        h.treatmentCondition ||
        h.controlledElements) && (
        <div className="border border-border bg-card">
          <div className="border-b border-border bg-secondary px-4 py-2">
            <MonoLabel>Experiment Design Preview</MonoLabel>
          </div>
          <div className="grid grid-cols-1 divide-y divide-border md:grid-cols-2 md:divide-x md:divide-y-0">
            <div className="flex flex-col gap-3 p-4">
              {h.independentVariable && (
                <div>
                  <MonoLabel>Variable</MonoLabel>
                  <p className="mt-1 text-sm">{h.independentVariable}</p>
                </div>
              )}
              {h.controlCondition && (
                <div>
                  <MonoLabel>Control</MonoLabel>
                  <p className="mt-1 text-sm">{h.controlCondition}</p>
                </div>
              )}
              {h.treatmentCondition && (
                <div>
                  <MonoLabel>Treatment</MonoLabel>
                  <p className="mt-1 text-sm">{h.treatmentCondition}</p>
                </div>
              )}
              <div>
                <MonoLabel>Primary Metric</MonoLabel>
                <p className="mt-1 text-sm">{h.primaryMetric}</p>
              </div>
            </div>
            {h.controlledElements && h.controlledElements.length > 0 && (
              <div className="p-4">
                <MonoLabel>Controlled</MonoLabel>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {h.controlledElements.map((el) => (
                    <span
                      key={el}
                      className="rounded border border-border bg-card px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground"
                    >
                      {el}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="border border-border bg-card p-4">
        <MonoLabel>Why This Matters</MonoLabel>
        <p className="mt-2 text-sm text-muted-foreground">{h.rationale}</p>
      </div>

      <div className="border border-border bg-card">
        <div className="border-b border-border bg-secondary px-4 py-2">
          <MonoLabel>Lineage</MonoLabel>
        </div>
        <div className="flex flex-col gap-3 p-4">
          {h.parentInsightId && parent ? (
            <>
              <div>
                <MonoLabel>Derived From</MonoLabel>
                <p className="mt-1 text-sm">{parent.title}</p>
              </div>
              {h.relationshipType && (
                <div>
                  <MonoLabel>Relationship</MonoLabel>
                  <p className="mt-1 text-sm">
                    {RELATIONSHIP_LABEL[h.relationshipType]}
                  </p>
                </div>
              )}
              {h.previousLearning && (
                <div>
                  <MonoLabel>Previous Learning</MonoLabel>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {h.previousLearning}
                  </p>
                </div>
              )}
              {h.remainingUnknown && (
                <div>
                  <MonoLabel>Remaining Unknown</MonoLabel>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {h.remainingUnknown}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div>
              <MonoLabel>Source</MonoLabel>
              <p className="mt-1 text-sm text-muted-foreground">
                Generated from onboarding context
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {(h.status === "suggested" || h.status === "draft") && (
          <>
            <Button asChild size="sm">
              <Link href={`/research/${h.id}/review`}>Review Hypothesis</Link>
            </Button>
            <Button size="sm" variant="outline" onClick={() => onReject(h.id)}>
              Reject
            </Button>
          </>
        )}
        {h.status === "approved" && (
          <>
            <Button size="sm" onClick={() => onCreateExperiment(h.id)}>
              Create Experiment
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href={`/research/${h.id}/review`}>Edit</Link>
            </Button>
          </>
        )}
        {h.status === "testing" && (
          <Button asChild size="sm">
            <Link href="/experiments">View Experiment</Link>
          </Button>
        )}
        {h.status === "learned" && (
          <>
            <Button asChild size="sm">
              <Link
                href={
                  relatedInsight ? `/insights?id=${relatedInsight.id}` : "/insights"
                }
              >
                View Insight
              </Link>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onCreateFollowUp(h, relatedInsight)}
            >
              Create Follow-up
            </Button>
          </>
        )}
        {h.status === "rejected" && (
          <>
            <Button size="sm" variant="outline" onClick={() => onRestore(h.id)}>
              Restore
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onRemove(h.id)}>
              Remove
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
