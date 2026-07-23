"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FlaskConical,
  Sparkles,
  Search,
  ChevronUp,
  ChevronDown,
  Rocket,
  Pencil,
  Database,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useProjectContext } from "@/lib/project-context";
import {
  useHypotheses,
  SEED_HYPOTHESES,
  STATUS_LABEL,
  type Hypothesis,
  type Status,
} from "@/lib/hypotheses";
import { SEED_INSIGHTS, toHypothesis, type Insight } from "@/lib/insights";

type Revision = {
  statement: string;
  primaryMetric: string;
  rationale: string;
};

const FILTERS: Array<Status | "all"> = [
  "all",
  "generated",
  "approved",
  "testing",
  "tested",
  "rejected",
];

function findParentHypothesis(insightId: string): Hypothesis | null {
  const insight = SEED_INSIGHTS.find((i) => i.id === insightId);
  if (!insight) return null;
  return SEED_HYPOTHESES.find((h) => h.id === insight.sourceHypothesisId) ?? null;
}

function StatusPill({ status }: { status: Status }) {
  const style =
    status === "approved"
      ? "bg-[#ECFDF5] text-success"
      : status === "generated" || status === "testing"
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

function CategoryPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-primary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-primary-foreground">
      {children}
    </span>
  );
}

// TODO(ai): replace with a real Claude API call once the AI service exists
// (see CONTENT_LAB_PLAN.md phase 3). This deterministic transform stands in
// for hypothesis refinement until that's wired up.
function craftRevision(h: Hypothesis, instruction: string): Revision {
  const trimmed = instruction.trim();
  const angle = trimmed || "a sharper, more specific angle";
  return {
    statement: `Videos built around ${angle} will outperform the current framing on ${h.primaryMetric.toLowerCase()}.`,
    primaryMetric: h.primaryMetric,
    rationale: trimmed
      ? `Applying "${trimmed}" tightens the hook and keeps the comparison isolated to one variable.`
      : "A sharper framing reduces ambiguity about what's actually being tested.",
  };
}

const QUICK_ACTIONS = ["Make sharper", "More founder-led", "Less salesy", "More technical"];

export default function HypothesesPage() {
  const router = useRouter();
  const { context: projectContext } = useProjectContext();
  const {
    hypotheses,
    loaded,
    addHypothesis,
    updateHypothesis: setHypothesisFields,
    removeHypothesis,
    setAll,
  } = useHypotheses();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Status | "all">("all");
  const [revision, setRevision] = useState<Revision | null>(null);
  const [instruction, setInstruction] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [testingWorksOpen, setTestingWorksOpen] = useState(true);

  const selected = hypotheses.find((h) => h.id === selectedId) ?? null;

  const counts = useMemo(() => {
    const c: Record<Status | "all", number> = {
      all: hypotheses.length,
      generated: 0,
      approved: 0,
      testing: 0,
      tested: 0,
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
      rationale: "Generated to explore an angle not yet covered by the backlog.",
      status: "generated",
    };
    addHypothesis(fresh);
  }

  function updateHypothesis(id: string, patch: Partial<Hypothesis>) {
    setHypothesisFields(id, patch);
  }

  function approve(id: string) {
    updateHypothesis(id, { status: "approved" });
  }

  function reject(id: string) {
    updateHypothesis(id, { status: "rejected" });
  }

  function restore(id: string) {
    updateHypothesis(id, { status: "generated" });
  }

  function remove(id: string) {
    removeHypothesis(id);
    if (selectedId === id) setSelectedId(null);
  }

  function createCampaign(id: string) {
    updateHypothesis(id, { status: "testing" });
    router.push("/campaigns");
  }

  // Reuses the same Insight -> Hypothesis mapping the Insights page's "Add to
  // Hypotheses" button uses, so a follow-up drafted from either entry point
  // carries the same lineage (parentInsightId) instead of two divergent
  // ad-hoc shapes. Falls back to a generic placeholder only if no Insight
  // exists yet for this hypothesis (shouldn't happen for h5 today).
  function createFollowUp(h: Hypothesis, insight?: Insight) {
    const followUp: Hypothesis = insight
      ? toHypothesis(insight)
      : {
          id: `h-fu-${Date.now()}`,
          title: `Follow-up: ${h.title}`,
          statement: `Building on "${h.statement}" — testing a follow-up refinement.`,
          category: h.category,
          primaryMetric: h.primaryMetric,
          rationale: "Follow-up drafted from a completed campaign's insight.",
          status: "generated",
        };
    if (!hypotheses.some((existing) => existing.id === followUp.id)) {
      addHypothesis(followUp);
    }
    setSelectedId(followUp.id);
  }

  function startEdit(h: Hypothesis) {
    setEditingId(h.id);
    setEditDraft(h.statement);
  }

  function saveEdit(id: string) {
    updateHypothesis(id, { statement: editDraft });
    setEditingId(null);
  }

  function refineHypothesis() {
    if (!selected) return;
    setRevision(craftRevision(selected, instruction));
  }

  function applyRevision() {
    if (!selected || !revision) return;
    updateHypothesis(selected.id, {
      statement: revision.statement,
      primaryMetric: revision.primaryMetric,
      rationale: revision.rationale,
      // Applying a meaningful revision to an Approved hypothesis reverts it
      // to Generated (brief: hypothesis lifecycle rules).
      status: selected.status === "approved" ? "generated" : selected.status,
    });
    setRevision(null);
    setInstruction("");
  }

  function discardRevision() {
    setRevision(null);
  }

  if (!loaded) return null;

  if (hypotheses.length === 0) {
    return (
      <>
        <div className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Hypotheses</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Generate, refine, and track testable content hypotheses across their
            lifecycle.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div className="flex flex-col items-center justify-center gap-6 border border-dashed border-border bg-card px-6 py-20 text-center xl:col-span-8">
            <div className="flex size-16 items-center justify-center rounded-lg bg-secondary">
              <FlaskConical className="size-7 text-muted-foreground" />
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-lg font-semibold tracking-tight">
                No hypotheses yet
              </h3>
              <p className="max-w-md text-sm text-muted-foreground">
                Generate testable content hypotheses based on your product,
                audience, and conversion goal.
              </p>
            </div>
            <div className="flex w-full max-w-xs flex-col gap-3">
              <Button onClick={generateInitial} className="gap-2">
                Generate Initial Hypotheses
                <Sparkles className="size-4" />
              </Button>
            </div>
            <div className="mt-4 flex items-center gap-4 border-t border-border pt-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Sparkles className="size-3.5" />
                AI Powered
              </span>
              <span>·</span>
              <span className="flex items-center gap-1.5">
                <Database className="size-3.5" />
                Data Driven
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-4 xl:col-span-4">
            <div className="flex flex-col border border-border bg-card">
              <div className="border-b border-border bg-secondary p-3">
                <span className="font-mono text-xs uppercase tracking-wide text-foreground">
                  Generation Context
                </span>
              </div>
              <div className="flex flex-col gap-4 p-4">
                {(
                  [
                    ["Product", projectContext.productName],
                    ["Audience", projectContext.targetAudience],
                    ["Goal", projectContext.desiredAction],
                    ["Primary CTA", projectContext.primaryCta],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label}>
                    <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      {label}
                    </p>
                    <p className="text-sm font-medium">{value}</p>
                  </div>
                ))}
                <Button asChild variant="outline" className="mt-2 gap-2">
                  <Link href="/settings">
                    <Pencil className="size-3.5" />
                    Edit Project Setup
                  </Link>
                </Button>
              </div>
            </div>

            <div className="flex flex-col border border-border bg-card">
              <div className="border-b border-border bg-secondary p-3">
                <span className="font-mono text-xs uppercase tracking-wide text-foreground">
                  Quick Tutorial
                </span>
              </div>
              <div className="flex flex-col gap-3 p-4">
                {[
                  "Generate testable hypotheses",
                  "Approve one hypothesis",
                  "Create a 3-variant campaign",
                  "Publish and measure results",
                ].map((step, i) => (
                  <div key={step} className="flex items-start gap-3">
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-border font-mono text-[10px]">
                      {i + 1}
                    </span>
                    <span className="text-sm text-muted-foreground">{step}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="flex flex-col justify-between gap-3 border-b border-border pb-6 md:flex-row md:items-start">
        <div className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Hypotheses</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Generate, refine, and track testable content hypotheses across their
            lifecycle.
          </p>
        </div>
        <Button onClick={generateMore} variant="outline" className="shrink-0 gap-2">
          <Sparkles className="size-4" />
          Generate More
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        {/* Library */}
        <div className="flex h-[calc(100vh-16rem)] flex-col border border-border bg-card xl:col-span-8">
          <div className="flex items-center justify-between border-b border-border bg-secondary px-4 py-3">
            <h3 className="text-lg font-semibold tracking-tight">
              Hypothesis Library
            </h3>
            <span className="rounded border border-border bg-card px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
              {counts.all} TOTAL
            </span>
          </div>

          <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search hypotheses..."
                className="pl-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`whitespace-nowrap rounded-full px-3 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                    filter === f
                      ? "bg-primary text-primary-foreground"
                      : "border border-border text-muted-foreground hover:bg-secondary"
                  }`}
                >
                  {f === "all" ? "All" : STATUS_LABEL[f]} ({counts[f]})
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto bg-background p-4">
            <div className="flex flex-col gap-4">
              {visible.map((h) => {
                const isSelected = h.id === selectedId;
                const isEditing = editingId === h.id;
                const parentHypothesis = h.parentInsightId
                  ? findParentHypothesis(h.parentInsightId)
                  : null;
                const relatedInsight =
                  h.status === "tested"
                    ? SEED_INSIGHTS.find((i) => i.sourceHypothesisId === h.id)
                    : undefined;
                return (
                  <div
                    key={h.id}
                    onClick={() => setSelectedId(h.id)}
                    className={`cursor-pointer border bg-card p-4 transition-all ${
                      isSelected ? "border-primary" : "border-border hover:border-foreground/30"
                    }`}
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <StatusPill status={h.status} />
                      <CategoryPill>{h.category}</CategoryPill>
                    </div>
                    <h4 className="mb-1 font-semibold">{h.title}</h4>
                    {parentHypothesis && (
                      <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                        Follow-up of: {parentHypothesis.statement}
                      </p>
                    )}

                    {isEditing ? (
                      <div
                        className="flex flex-col gap-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Textarea
                          value={editDraft}
                          onChange={(e) => setEditDraft(e.target.value)}
                          className="h-20 resize-none text-sm"
                        />
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setEditingId(null)}
                          >
                            Cancel
                          </Button>
                          <Button size="sm" onClick={() => saveEdit(h.id)}>
                            Save
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="mb-3 text-sm text-muted-foreground">
                          {h.statement}
                        </p>
                        <div className="mb-3 flex flex-col gap-3 rounded bg-secondary p-3">
                          <div>
                            <p className="mb-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                              Primary Metric
                            </p>
                            <p className="text-sm font-semibold">
                              {h.primaryMetric}
                            </p>
                          </div>
                          <div>
                            <p className="mb-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                              Rationale
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {h.rationale}
                            </p>
                          </div>
                        </div>
                      </>
                    )}

                    {!isEditing && (
                      <div
                        className="flex items-center justify-end gap-2 border-t border-border pt-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {h.status === "generated" && (
                          <>
                            <Button size="sm" variant="ghost" onClick={() => startEdit(h)}>
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-destructive hover:text-destructive"
                              onClick={() => reject(h.id)}
                            >
                              Reject
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => approve(h.id)}>
                              Approve
                            </Button>
                          </>
                        )}
                        {h.status === "approved" && (
                          <>
                            <Button size="sm" variant="ghost" onClick={() => startEdit(h)}>
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-destructive hover:text-destructive"
                              onClick={() => reject(h.id)}
                            >
                              Reject
                            </Button>
                            <Button
                              size="sm"
                              className="gap-1"
                              onClick={() => createCampaign(h.id)}
                            >
                              <Rocket className="size-3.5" />
                              Create Campaign
                            </Button>
                          </>
                        )}
                        {h.status === "testing" && (
                          <Button asChild size="sm" variant="outline">
                            <Link href="/campaigns">View Campaign</Link>
                          </Button>
                        )}
                        {h.status === "tested" && (
                          <>
                            <Button asChild size="sm" variant="ghost">
                              <Link
                                href={
                                  relatedInsight
                                    ? `/insights?id=${relatedInsight.id}`
                                    : "/insights"
                                }
                              >
                                View Insight
                              </Link>
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => createFollowUp(h, relatedInsight)}
                            >
                              Create Follow-up
                            </Button>
                          </>
                        )}
                        {h.status === "rejected" && (
                          <>
                            <Button size="sm" variant="outline" onClick={() => restore(h.id)}>
                              Restore
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-destructive hover:text-destructive"
                              onClick={() => remove(h.id)}
                            >
                              Delete
                            </Button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
              {visible.length === 0 && (
                <p className="py-12 text-center text-sm text-muted-foreground">
                  No hypotheses match this filter.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Right panel */}
        <div className="flex flex-col gap-4 xl:col-span-4">
          <div className="flex flex-col border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border bg-secondary px-4 py-3">
              <Sparkles className="size-4" />
              <h3 className="text-lg font-semibold tracking-tight">AI Strategy</h3>
            </div>
            <div className="flex flex-col gap-4 p-4">
              <p className="text-sm text-muted-foreground">
                Refine the selected hypothesis, generate sharper alternatives, or
                stress-test the assumption before creating a campaign.
              </p>

              {selected ? (
                <>
                  <div className="relative border border-border bg-background p-3">
                    <span className="absolute -top-2 left-2 bg-card px-1 font-mono text-[10px] text-muted-foreground">
                      CONTEXT
                    </span>
                    <p className="text-sm font-semibold">
                      &quot;{selected.title}&quot;
                    </p>
                  </div>

                  {revision && (
                    <div className="relative flex flex-col gap-3 border border-dashed border-primary p-3">
                      <span className="absolute -top-2 left-2 bg-card px-1 font-mono text-[10px] font-bold text-foreground">
                        PROPOSED REVISION
                      </span>
                      <p className="text-sm font-semibold leading-relaxed">
                        &quot;{revision.statement}&quot;
                      </p>
                      <div className="flex flex-col gap-2 border-t border-border pt-2">
                        <div>
                          <p className="mb-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                            Primary Metric
                          </p>
                          <span className="w-fit rounded border border-border bg-card px-1.5 py-0.5 font-mono text-xs">
                            {revision.primaryMetric}
                          </span>
                        </div>
                        <div>
                          <p className="mb-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                            Rationale
                          </p>
                          <p className="text-xs leading-tight text-muted-foreground">
                            {revision.rationale}
                          </p>
                        </div>
                      </div>
                      <div className="mt-1 flex gap-2">
                        <Button
                          size="sm"
                          className="flex-1 font-mono text-[10px] uppercase"
                          onClick={applyRevision}
                        >
                          Apply
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="flex-1 font-mono text-[10px] uppercase"
                          onClick={discardRevision}
                        >
                          Discard
                        </Button>
                      </div>
                    </div>
                  )}

                  <Textarea
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="Ask AI to refine this hypothesis..."
                    className="resize-none font-mono text-xs"
                    rows={3}
                  />

                  <div>
                    <span className="mb-2 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      Quick Actions
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {QUICK_ACTIONS.map((qa) => (
                        <button
                          key={qa}
                          onClick={() => setInstruction(qa)}
                          className="rounded border border-border px-2 py-1 font-mono text-[10px] text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                        >
                          {qa}
                        </button>
                      ))}
                    </div>
                  </div>

                  <Button onClick={refineHypothesis} className="font-mono text-xs">
                    Refine Hypothesis
                  </Button>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Select a hypothesis from the library to refine it.
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-col border border-border bg-card">
            <button
              onClick={() => setTestingWorksOpen((v) => !v)}
              className="flex items-center justify-between border-b border-border bg-secondary px-4 py-3"
            >
              <h3 className="text-lg font-semibold tracking-tight">
                How Campaign Testing Works
              </h3>
              {testingWorksOpen ? (
                <ChevronUp className="size-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="size-4 text-muted-foreground" />
              )}
            </button>
            {testingWorksOpen && (
              <div className="flex flex-col gap-3 p-4">
                <p className="text-xs text-muted-foreground">
                  Every campaign has exactly 3 variants:
                </p>
                <div className="flex flex-col gap-2">
                  {[
                    ["A", "Baseline / Control"],
                    ["B", "Primary Hypothesis"],
                    ["C", "Contrasting Alternative"],
                  ].map(([letter, label]) => (
                    <div
                      key={letter}
                      className="flex items-center gap-3 border border-border bg-background p-2"
                    >
                      <div className="flex size-6 shrink-0 items-center justify-center rounded border border-border bg-secondary font-mono text-xs">
                        {letter}
                      </div>
                      <span className="font-mono text-xs text-muted-foreground">
                        {letter} — {label}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  Change one primary variable while keeping audience, CTA,
                  duration, and offer as consistent as possible.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
