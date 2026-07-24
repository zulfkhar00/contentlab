"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useHypotheses,
  SEED_HYPOTHESES,
  RELATIONSHIP_LABEL,
  type Hypothesis,
} from "@/lib/hypotheses";
import { SEED_INSIGHTS } from "@/lib/insights";
import { hypothesisApi } from "@/lib/api-client";
import { metricToApi } from "@/lib/api-adapters";

type Draft = {
  researchQuestion: string;
  statement: string;
  independentVariable: string;
  controlCondition: string;
  treatmentCondition: string;
  primaryMetric: string;
  controlledElements: string[];
  contradictionCondition: string;
};

function initialDraftFromHypothesis(h: Hypothesis): Draft {
  return {
    researchQuestion: h.researchQuestion ?? "",
    statement: h.statement ?? "",
    independentVariable: h.independentVariable ?? "",
    controlCondition: h.controlCondition ?? "",
    treatmentCondition: h.treatmentCondition ?? "",
    primaryMetric: h.primaryMetric ?? "",
    controlledElements: h.controlledElements ?? [],
    contradictionCondition: h.contradictionCondition ?? "",
  };
}

function findParentTitle(parentInsightId?: string): string | null {
  if (!parentInsightId) return null;
  const insight = SEED_INSIGHTS.find((i) => i.id === parentInsightId);
  if (!insight) return null;
  const parent = SEED_HYPOTHESES.find((h) => h.id === insight.sourceHypothesisId);
  return parent ? parent.title : null;
}

// Screen 10 (Follow-up Hypothesis Review) lineage lookup. Returns everything
// the "Derived From" card needs so the JSX stays declarative.
type FollowUpLineage = {
  parentTitle: string | null;
  parentId: string | null;
  sourceEvidence: string | null;
  relationshipLabel: string | null;
};

function findFollowUpLineage(h: Hypothesis): FollowUpLineage | null {
  if (!h.parentInsightId) return null;
  const insight = SEED_INSIGHTS.find((i) => i.id === h.parentInsightId);
  const parent = insight
    ? SEED_HYPOTHESES.find((x) => x.id === insight.sourceHypothesisId) ?? null
    : null;
  return {
    parentTitle: parent?.title ?? null,
    parentId: parent?.id ?? null,
    sourceEvidence: insight?.supportedLearning ?? insight?.evidenceBasis ?? null,
    relationshipLabel: h.relationshipType
      ? RELATIONSHIP_LABEL[h.relationshipType]
      : null,
  };
}

export default function HypothesisReviewPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const { hypotheses, loaded, updateHypothesis } = useHypotheses();

  const hypothesis = useMemo(
    () => hypotheses.find((h) => h.id === params.id) ?? null,
    [hypotheses, params.id],
  );

  const [draft, setDraft] = useState<Draft | null>(null);
  const [chipInput, setChipInput] = useState("");
  const [savedFlash, setSavedFlash] = useState<null | "draft" | "approved">(null);

  const workingDraft = draft ?? (hypothesis ? initialDraftFromHypothesis(hypothesis) : null);

  if (!loaded) return null;

  if (!hypothesis || !workingDraft) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">Hypothesis not found.</p>
        <Button asChild variant="outline" className="w-fit gap-2">
          <Link href="/research">
            <ArrowLeft className="size-4" />
            Back to Research
          </Link>
        </Button>
      </div>
    );
  }

  function patch(next: Partial<Draft>) {
    setDraft({ ...workingDraft!, ...next });
  }

  function addChip() {
    const v = chipInput.trim();
    if (!v) return;
    if (workingDraft!.controlledElements.includes(v)) {
      setChipInput("");
      return;
    }
    patch({ controlledElements: [...workingDraft!.controlledElements, v] });
    setChipInput("");
  }

  function removeChip(el: string) {
    patch({
      controlledElements: workingDraft!.controlledElements.filter((x) => x !== el),
    });
  }

  function persistDraft(nextStatus: "draft" | "approved") {
    if (!hypothesis) return;
    updateHypothesis(hypothesis.id, {
      researchQuestion: workingDraft!.researchQuestion.trim() || undefined,
      statement: workingDraft!.statement.trim(),
      independentVariable: workingDraft!.independentVariable.trim() || undefined,
      controlCondition: workingDraft!.controlCondition.trim() || undefined,
      treatmentCondition: workingDraft!.treatmentCondition.trim() || undefined,
      primaryMetric: workingDraft!.primaryMetric.trim() || hypothesis.primaryMetric,
      controlledElements:
        workingDraft!.controlledElements.length > 0
          ? workingDraft!.controlledElements
          : undefined,
      contradictionCondition: workingDraft!.contradictionCondition.trim() || undefined,
      status: nextStatus,
    });
    setSavedFlash(nextStatus);
  }

  function saveDraft() {
    if (!hypothesis) return;
    hypothesisApi.patch(hypothesis.id, {
      title: workingDraft!.researchQuestion ? undefined : undefined,
      statement: workingDraft!.statement || undefined,
      research_question: workingDraft!.researchQuestion || undefined,
      independent_variable: workingDraft!.independentVariable || undefined,
      control_condition: workingDraft!.controlCondition || undefined,
      treatment_condition: workingDraft!.treatmentCondition || undefined,
      controlled_elements: workingDraft!.controlledElements.length > 0 ? workingDraft!.controlledElements : undefined,
      contradiction_condition: workingDraft!.contradictionCondition || undefined,
      primary_metric: metricToApi(workingDraft!.primaryMetric) || undefined,
    }).catch(() => {});
    persistDraft("draft");
  }

  function approveAndGenerate() {
    if (!hypothesis) return;
    hypothesisApi.approveAndGenerate(hypothesis.id, {
      statement: workingDraft!.statement || undefined,
      research_question: workingDraft!.researchQuestion || undefined,
      independent_variable: workingDraft!.independentVariable || undefined,
      control_condition: workingDraft!.controlCondition || undefined,
      treatment_condition: workingDraft!.treatmentCondition || undefined,
      controlled_elements: workingDraft!.controlledElements.length > 0 ? workingDraft!.controlledElements : undefined,
      contradiction_condition: workingDraft!.contradictionCondition || undefined,
      primary_metric: metricToApi(workingDraft!.primaryMetric) || undefined,
    }).then(() => {
      persistDraft("approved");
      router.push("/research");
    }).catch(() => {
      persistDraft("approved");
      router.push("/research");
    });
  }

  const parentTitle = findParentTitle(hypothesis.parentInsightId);
  const lineage = findFollowUpLineage(hypothesis);
  const isFollowUp = lineage !== null;

  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <Button asChild variant="outline" size="sm" className="mt-1 gap-2">
            <Link href="/research">
              <ArrowLeft className="size-4" />
              Back
            </Link>
          </Button>
          <div className="flex flex-col gap-1">
            <h2 className="text-2xl font-semibold tracking-tight">
              {isFollowUp ? "Review Follow-up Hypothesis" : "Review Hypothesis"}
            </h2>
            <p className="text-sm text-muted-foreground">
              Refine the research question, hypothesis, and experiment design
              before turning it into an experiment.
            </p>
          </div>
        </div>
        {savedFlash && (
          <span className="font-mono text-[10px] uppercase tracking-wide text-success">
            {savedFlash === "draft" ? "Draft saved" : "Approved"}
          </span>
        )}
      </div>

      <div data-testid="review-form" className="flex flex-col gap-4">
        {isFollowUp && lineage && (
          <section data-testid="lineage-derived-from" className="border border-primary bg-card">
            <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
              <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Derived From
              </span>
            </header>
            <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-3">
              <div className="flex flex-col gap-1">
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Parent Hypothesis</span>
                <span className="text-sm font-medium">{lineage.parentTitle ?? "Unknown parent"}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Source Insight</span>
                <span className="text-sm text-muted-foreground">{lineage.sourceEvidence ?? "—"}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Relationship</span>
                <span className="text-sm">{lineage.relationshipLabel ?? "—"}</span>
              </div>
            </div>
          </section>
        )}

        {isFollowUp && hypothesis.previousLearning && (
          <section data-testid="lineage-previous-learning" className="border border-border bg-card">
            <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
              <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Previous Learning</span>
            </header>
            <div className="p-4">
              <p className="text-sm">{hypothesis.previousLearning}</p>
            </div>
          </section>
        )}

        {isFollowUp && hypothesis.remainingUnknown && (
          <section data-testid="lineage-remaining-unknown" className="border border-border bg-card">
            <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
              <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Remaining Unknown</span>
            </header>
            <div className="p-4">
              <p className="text-sm">{hypothesis.remainingUnknown}</p>
            </div>
          </section>
        )}

        <section className="border border-border bg-card">
          <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              1 — Research Question
            </span>
          </header>
          <div className="p-4">
            <Textarea
              value={workingDraft.researchQuestion}
              onChange={(e) => patch({ researchQuestion: e.target.value })}
              placeholder="What specific question does this hypothesis answer?"
              className="min-h-[80px] text-sm"
            />
          </div>
        </section>

        <section className="border border-border bg-card">
          <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              2 — Hypothesis Statement
            </span>
          </header>
          <div className="p-4">
            <Textarea
              value={workingDraft.statement}
              onChange={(e) => patch({ statement: e.target.value })}
              placeholder="A testable prediction to check against the metric."
              className="min-h-[100px] text-sm"
            />
          </div>
        </section>

        <section className="border border-border bg-card">
          <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              3 — Experiment Design
            </span>
          </header>
          <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2">
            <div className="flex flex-col gap-1">
              <label className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Independent Variable
              </label>
              <Input
                value={workingDraft.independentVariable}
                onChange={(e) => patch({ independentVariable: e.target.value })}
                placeholder="What varies between conditions?"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Primary Metric
              </label>
              <Input
                value={workingDraft.primaryMetric}
                onChange={(e) => patch({ primaryMetric: e.target.value })}
                placeholder="e.g. Clicks per 1K Views"
              />
            </div>
            <div className="flex flex-col gap-1 md:col-span-2">
              <label className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Control Condition
              </label>
              <Textarea
                value={workingDraft.controlCondition}
                onChange={(e) => patch({ controlCondition: e.target.value })}
                placeholder="Describe the baseline you compare against."
                className="min-h-[70px] text-sm"
              />
            </div>
            <div className="flex flex-col gap-1 md:col-span-2">
              <label className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Treatment Condition
              </label>
              <Textarea
                value={workingDraft.treatmentCondition}
                onChange={(e) => patch({ treatmentCondition: e.target.value })}
                placeholder="Describe the new condition under test."
                className="min-h-[70px] text-sm"
              />
            </div>
          </div>
        </section>

        <section className="border border-border bg-card">
          <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              4 — Controlled Elements
            </span>
          </header>
          <div className="flex flex-col gap-3 p-4">
            <div className="flex flex-wrap items-center gap-1.5">
              {workingDraft.controlledElements.map((el) => (
                <button
                  key={el}
                  type="button"
                  onClick={() => removeChip(el)}
                  className="flex items-center gap-1 rounded border border-border bg-card px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground hover:border-destructive hover:text-destructive"
                >
                  {el}
                  <X className="size-3" />
                </button>
              ))}
              {workingDraft.controlledElements.length === 0 && (
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  No controlled elements yet.
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={chipInput}
                onChange={(e) => setChipInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addChip();
                  }
                }}
                placeholder="Add an element that stays constant (press Enter)"
                className="h-9 text-sm"
              />
              <Button size="sm" variant="outline" onClick={addChip}>
                Add
              </Button>
            </div>
          </div>
        </section>

        <section className="border border-border bg-card">
          <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              5 — Contradiction Condition
            </span>
          </header>
          <div className="p-4">
            <Textarea
              value={workingDraft.contradictionCondition}
              onChange={(e) => patch({ contradictionCondition: e.target.value })}
              placeholder="What result would show this hypothesis is wrong?"
              className="min-h-[80px] text-sm"
            />
          </div>
        </section>

        <section className="border border-border bg-card">
          <header className="flex items-center justify-between gap-2 border-b border-border bg-secondary px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              6 — Source and Reason
            </span>
          </header>
          <div className="flex flex-col gap-3 p-4">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Why This Matters
              </span>
              <p className="mt-1 text-sm text-muted-foreground">{hypothesis.rationale}</p>
            </div>
            {hypothesis.parentInsightId && parentTitle ? (
              <div className="flex flex-col gap-2">
                <div>
                  <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    Derived From
                  </span>
                  <p className="mt-1 text-sm">{parentTitle}</p>
                </div>
                {hypothesis.relationshipType && (
                  <div>
                    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      Relationship
                    </span>
                    <p className="mt-1 text-sm">
                      {RELATIONSHIP_LABEL[hypothesis.relationshipType]}
                    </p>
                  </div>
                )}
                {hypothesis.previousLearning && (
                  <div>
                    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      Previous Learning
                    </span>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {hypothesis.previousLearning}
                    </p>
                  </div>
                )}
                {hypothesis.remainingUnknown && (
                  <div>
                    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      Remaining Unknown
                    </span>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {hypothesis.remainingUnknown}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div>
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  Source
                </span>
                <p className="mt-1 text-sm text-muted-foreground">
                  Generated from onboarding context
                </p>
              </div>
            )}
          </div>
        </section>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            className="gap-2"
            onClick={saveDraft}
            data-testid="save-draft"
          >
            <Save className="size-4" />
            Save Draft
          </Button>
          <Button
            className="gap-2"
            onClick={approveAndGenerate}
            data-testid="approve-and-generate"
          >
            <Sparkles className="size-4" />
            Approve &amp; Generate Experiment
          </Button>
        </div>
      </div>
    </>
  );
}
