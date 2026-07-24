"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
import { SEED_INSIGHTS, toHypothesis, insightClicksPer1k, type Insight } from "@/lib/insights";
import { hypothesisApi } from "@/lib/api-client";
import { apiToFrontend } from "@/lib/api-adapters";

const FILTERS: Array<Status | "all"> = [
  "all",
  "suggested",
  "draft",
  "approved",
  "testing",
  "learned",
  "rejected",
];

// Research Library has two views: the flat card list ("library") and a
// vertical tree grouped by lineage root ("thread"). Persisted to
// localStorage so a founder's preferred view survives reloads.
type ResearchView = "library" | "thread";
const VIEW_STORAGE_KEY = "research.view";

function loadResearchView(): ResearchView {
  if (typeof window === "undefined") return "library";
  return window.localStorage.getItem(VIEW_STORAGE_KEY) === "thread"
    ? "thread"
    : "library";
}

function persistResearchView(v: ResearchView) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(VIEW_STORAGE_KEY, v);
}


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
  const [view, setView] = useState<ResearchView>("library");
  const [apiLoading, setApiLoading] = useState(false);

  useEffect(() => {
    setView(loadResearchView());
  }, []);

  useEffect(() => {
    if (!loaded) return;
    if (hypotheses.length > 0) return;
    hypothesisApi.list().then((items) => {
      if (items.length > 0) setAll(items.map(apiToFrontend));
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded]);

  function switchView(v: ResearchView) {
    setView(v);
    persistResearchView(v);
  }

  // Walk from a hypothesis to its parent hypothesis, if any. A follow-up
  // stores parentInsightId; the insight's sourceHypothesisId is the parent
  // hypothesis. Returns null for hypotheses with no lineage in the current
  // set (roots).
  const parentIdOf = useCallback((h: Hypothesis): string | null => {
    if (!h.parentInsightId) return null;
    const insight = SEED_INSIGHTS.find((i) => i.id === h.parentInsightId);
    return insight?.sourceHypothesisId ?? null;
  }, []);


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

  // Thread view: build root -> children map keyed by hypothesis id. A
  // hypothesis is a root when its parent hypothesis either has no
  // parentInsightId or points to a parent that isn't in the current set.
  const tree = useMemo(() => {
    const byId = new Map(hypotheses.map((h) => [h.id, h]));
    const kids = new Map<string, Hypothesis[]>();
    const roots: Hypothesis[] = [];
    for (const h of hypotheses) {
      const pid = parentIdOf(h);
      if (pid && byId.has(pid)) {
        const arr = kids.get(pid) ?? [];
        arr.push(h);
        kids.set(pid, arr);
      } else {
        roots.push(h);
      }
    }
    return { roots, kids };
  }, [hypotheses, parentIdOf]);

  // Thread-view visibility: a subtree stays visible when the root or any
  // descendant passes the search + filter.
  const visibleIds = useMemo(() => new Set(visible.map((h) => h.id)), [visible]);
  const subtreeMatches = useCallback(
    function walk(h: Hypothesis): boolean {
      if (visibleIds.has(h.id)) return true;
      const kids = tree.kids.get(h.id) ?? [];
      return kids.some(walk);
    },
    [visibleIds, tree],
  );

  function generateInitial() {
    setApiLoading(true);
    hypothesisApi.generate()
      .then((items) => {
        const mapped = items.map(apiToFrontend);
        setAll(mapped);
        if (mapped.length > 0) setSelectedId(mapped[0].id);
      })
      .catch(() => {})
      .finally(() => setApiLoading(false));
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


  const cardClass = (isSelected: boolean) =>
    "flex flex-col gap-2 border bg-card p-3 text-left transition-colors w-full " +
    (isSelected ? "border-primary" : "border-border hover:border-foreground/30");

  function HypothesisCardButton({ h, depth }: { h: Hypothesis; depth?: number }) {
    const isSelected = h.id === selectedId;
    return (
      <button
        onClick={() => setSelectedId(h.id)}
        data-thread-node-id={h.id}
        data-thread-depth={depth ?? 0}
        className={cardClass(isSelected)}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="line-clamp-2 text-sm font-semibold">{h.title}</span>
          <StatusPill status={h.status} />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            {h.primaryMetric}
          </span>
          {h.status === "learned" && (() => {
            const ins = findRelatedInsight(h.id);
            if (!ins) return null;
            const best = insightClicksPer1k(ins.treatment) > insightClicksPer1k(ins.control)
              ? ins.treatment : ins.control;
            return (
              <span className="font-mono text-[10px] text-success">
                {insightClicksPer1k(best)}
              </span>
            );
          })()}
          {h.status === "testing" && (
            <span className="font-mono text-[10px] text-primary">Tracking</span>
          )}
        </div>
        <DerivedFromLine h={h} />
      </button>
    );
  }

  function renderLibraryList() {
    if (visible.length === 0) {
      return (
        <div className="border border-dashed border-border bg-card p-4 text-center text-xs text-muted-foreground">
          No hypotheses match this filter.
        </div>
      );
    }
    return visible.map((h) => <HypothesisCardButton key={h.id} h={h} />);
  }

  function renderThreadNode(h: Hypothesis, depth: number): React.ReactNode {
    const kids = tree.kids.get(h.id) ?? [];
    return (
      <div
        key={h.id}
        className="flex flex-col gap-2"
        style={{ marginLeft: depth * 20 }}
        data-thread-branch-root={depth === 0 ? h.id : undefined}
      >
        <HypothesisCardButton h={h} depth={depth} />
        {kids.map((k) => renderThreadNode(k, depth + 1))}
      </div>
    );
  }

  function renderThreadList() {
    const roots = tree.roots.filter(subtreeMatches);
    if (roots.length === 0) {
      return (
        <div className="border border-dashed border-border bg-card p-4 text-center text-xs text-muted-foreground">
          No hypotheses match this filter.
        </div>
      );
    }
    return roots.map((r) => renderThreadNode(r, 0));
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
        <div className="flex shrink-0 items-center gap-2">
          <div
            data-research-view={view}
            className="flex items-center border border-border bg-card p-0.5"
          >
            {(["library", "thread"] as const).map((choice) => (
              <button
                key={choice}
                type="button"
                data-view-choice={choice}
                onClick={() => switchView(choice)}
                className={`rounded-sm px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                  view === choice
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {choice === "library" ? "Library" : "Thread"}
              </button>
            ))}
          </div>
          <Button onClick={generateMore} variant="outline" className="gap-2">
            <Sparkles className="size-4" />
            Generate More
          </Button>
        </div>
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

          <div className="flex flex-col gap-2" data-research-list={view}>
            {view === "library" ? renderLibraryList() : renderThreadList()}
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
