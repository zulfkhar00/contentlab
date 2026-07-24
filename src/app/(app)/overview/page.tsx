"use client";

import { useEffect, useState } from "react";

import Link from "next/link";
import {
  ArrowRight,
  FlaskConical,
  Lightbulb,
  Play,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  useExperiment,
  getExperimentStatus,
  getNextActionVariant,
  getPublishedCount,
  variantStatusLabel,
  type ExperimentData,
} from "@/lib/experiment";
import {
  useHypotheses,
  STATUS_LABEL,
  type Hypothesis,
} from "@/lib/hypotheses";
import {
  SEED_INSIGHTS,
  insightClicksPer1k,
  type Insight,
} from "@/lib/insights";
import { insightApi } from "@/lib/api-client";

function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

function StatusPill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "active" | "idle" | "success";
}) {
  const style =
    tone === "active"
      ? "bg-primary text-primary-foreground"
      : tone === "success"
        ? "bg-[#ECFDF5] text-success"
        : "border border-border bg-card text-muted-foreground";
  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${style}`}
    >
      {children}
    </span>
  );
}

function variantTone(status: string): "active" | "idle" | "success" {
  if (status === "completed") return "success";
  if (status === "tracking") return "active";
  return "idle";
}

type NextAction = {
  title: string;
  description: string;
  cta: { label: string; href: string } | null;
};

function computeNextAction(
  experiment: ExperimentData,
  latestInsight: Insight | null,
): NextAction {
  const nextVariant = getNextActionVariant(experiment.variants);
  const status = getExperimentStatus(experiment.variants);
  if (nextVariant) {
    return {
      title: `Record Variant ${nextVariant.role}: ${nextVariant.title}`,
      description:
        "Script, hook, and checklist are ready. Record it and paste the URL after publishing.",
      cta: {
        label: "Open Recording Brief",
        href: `/experiments/brief/${nextVariant.role.toLowerCase()}`,
      },
    };
  }
  if (status === "tracking" && latestInsight) {
    return {
      title: "Review Experiment Learning",
      description:
        "All three tracking windows are complete. Review the evidence and draft the next hypothesis.",
      cta: {
        label: "View Results",
        href: `/insights?id=${latestInsight.id}`,
      },
    };
  }
  return {
    title: "All variants are tracking",
    description:
      "Check back once each 72h tracking window completes to see the experiment insight.",
    cta: null,
  };
}

function pickLatestInsight(): Insight | null {
  return null; // replaced by API in component
}

function totalProductClicks(): number {
  return 0; // will be computed from real variant metrics
}

function findCurrentResearchQuestion(
  experiment: ExperimentData,
  hypotheses: Hypothesis[],
): string | null {
  // Match the active experiment's hypothesis text against the Research
  // Library so we can show the same "Which opening style ..." question the
  // user drafted, without duplicating the field on ExperimentData yet.
  const stmt = experiment.hypothesis.trim();
  const match =
    hypotheses.find((h) => h.statement.trim() === stmt) ??
    hypotheses.find((h) => h.status === "testing");
  return match?.researchQuestion ?? null;
}

export default function OverviewPage() {
  const { experiment, loaded: experimentLoaded } = useExperiment();
  const { hypotheses, loaded: hypothesesLoaded } = useHypotheses();

  if (!experimentLoaded || !hypothesesLoaded) return null;
  if (!experiment) {
    const noExpKpis = [
      { label: "Published Videos", value: "0" },
      { label: "Product Clicks", value: "0" },
      { label: "Completed Experiments", value: "0" },
      { label: "Active Research Thread", value: "0" },
    ];
    return (
      <>
        <div className="mb-2 flex flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Overview</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">What am I currently learning, and what should I do next?</p>
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {noExpKpis.map((k) => (
            <div key={k.label} className="flex flex-col justify-between border border-border bg-card p-4">
              <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">{k.label}</span>
              <span className="font-mono text-2xl font-semibold">{k.value}</span>
            </div>
          ))}
        </div>
        <div className="border border-dashed border-border bg-card p-8 text-center text-sm text-muted-foreground">
          No active experiment yet. Approve a hypothesis to get started.
        </div>
      </>
    );
  }

  const publishedVideos = getPublishedCount(experiment.variants);
  const completedExperiments = SEED_INSIGHTS.length;
  const productClicks = experiment.variants.reduce(
    (sum, v) => sum + (v.metrics?.clicks ?? 0),
    0,
  ) || totalProductClicks();
  const activeThreads = hypotheses.filter((h) => h.status === "testing").length || 1;
  const [apiLatestInsight, setApiLatestInsight] = useState<ReturnType<typeof pickLatestInsight>>(null);
  const latestInsight = apiLatestInsight ?? pickLatestInsight();

  useEffect(() => {
    insightApi.list().then((items) => {
      if (items.length > 0) {
        const latest = items[0];
        setApiLatestInsight({
          id: latest.id,
          experimentName: latest.hypothesis_text?.slice(0, 50) ?? "Experiment",
          hypothesis: latest.hypothesis_text ?? "",
          primaryMetric: latest.primary_metric ?? "Clicks / 1K Views",
          completedAt: latest.generated_at,
          windowHours: 72,
          control: { role: "A", title: "Control", roleLabel: "Control", views: 0, clicks: 0 },
          treatment: { role: "B", title: "Treatment", roleLabel: "Hypothesis Treatment", views: 0, clicks: 0 },
          lift: 0,
          evidenceBasis: latest.supported_learning ?? "",
          supportedLearning: latest.supported_learning ?? "",
          doNotInferYet: [],
          recommendedNextTest: "",
          followUp: { title: "", statement: "", category: "", primaryMetric: "", rationale: "", relationshipType: "replication", previousLearning: "", remainingUnknown: "" },
          sourceHypothesisId: "",
        } as ReturnType<typeof pickLatestInsight>);
      }
    }).catch(() => {});
  }, [experimentLoaded]);
  const nextAction = computeNextAction(experiment, latestInsight);
  const currentQuestion = findCurrentResearchQuestion(experiment, hypotheses);

  const backlog = hypotheses
    .filter((h) => h.status === "suggested" || h.status === "draft" || h.status === "approved")
    .slice(0, 4);

  return (
    <>
      <div className="mb-2 flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Overview</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          What am I currently learning, and what should I do next?
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="flex flex-col justify-between border border-border bg-card p-4">
          <MonoLabel>Published Videos</MonoLabel>
          <span className="font-mono text-2xl font-semibold">{publishedVideos}</span>
        </div>
        <div className="flex flex-col justify-between border border-border bg-card p-4">
          <MonoLabel>Product Clicks</MonoLabel>
          <span className="font-mono text-2xl font-semibold">{productClicks.toLocaleString()}</span>
        </div>
        <div className="flex flex-col justify-between border border-border bg-card p-4">
          <MonoLabel>Completed Experiments</MonoLabel>
          <span className="font-mono text-2xl font-semibold">{completedExperiments}</span>
        </div>
        <div className="flex flex-col justify-between border border-border bg-card p-4">
          <MonoLabel>Active Research Thread</MonoLabel>
          <span className="font-mono text-2xl font-semibold">{activeThreads}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <section
          data-testid="current-research-thread"
          className="flex flex-col gap-4 border border-border bg-card p-5 lg:col-span-8"
        >
          <div className="flex items-center gap-2">
            <FlaskConical className="size-4 text-muted-foreground" />
            <MonoLabel>Current Research Thread</MonoLabel>
          </div>

          {currentQuestion && (
            <div className="flex flex-col gap-1">
              <MonoLabel>Current Question</MonoLabel>
              <p className="text-base font-medium">{currentQuestion}</p>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <MonoLabel>Current Hypothesis</MonoLabel>
            <p className="border-l-2 border-primary py-1 pl-3 text-sm">
              &quot;{experiment.hypothesis}&quot;
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between border-b border-border pb-1">
              <MonoLabel>Experiment Progress</MonoLabel>
              <span className="rounded bg-secondary px-2 py-0.5 font-mono text-[10px]">
                {publishedVideos}/3 variants published
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              {experiment.variants.map((v) => (
                <div
                  key={v.role}
                  className="flex items-center justify-between rounded border border-border p-2.5"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-semibold">{v.role}</span>
                    <span className="text-sm">{v.title}</span>
                  </div>
                  <StatusPill tone={variantTone(v.status)}>
                    {variantStatusLabel(v.status)}
                  </StatusPill>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          data-testid="latest-learning"
          className="flex flex-col gap-3 border border-border bg-card p-5 lg:col-span-4"
        >
          <div className="flex items-center gap-2">
            <Lightbulb className="size-4 text-muted-foreground" />
            <MonoLabel>Latest Learning</MonoLabel>
          </div>
          {latestInsight ? (
            <>
              <p className="text-sm font-medium">{latestInsight.hypothesis}</p>
              <div className="flex flex-col gap-1">
                <MonoLabel>Evidence</MonoLabel>
                <p className="text-xs text-muted-foreground">
                  Control {insightClicksPer1k(latestInsight.control)} vs Treatment{" "}
                  {insightClicksPer1k(latestInsight.treatment)} clicks / 1K views
                </p>
              </div>
              <Button asChild variant="outline" size="sm" className="w-fit gap-2">
                <Link href={`/insightsSbid=${latestInsight.id}`.replace("Sb", "?")}>
                  View Evidence
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No learnings yet. Insights appear once an experiment completes.
            </p>
          )}
        </section>
      </div>

      <section
        data-testid="next-action-card"
        className="flex flex-col gap-3 border border-l-4 border-border border-l-primary bg-card p-6"
      >
        <div className="flex items-center gap-2">
          <Play className="size-5 text-primary" />
          <MonoLabel>Next Action</MonoLabel>
        </div>
        <h3 className="text-2xl font-semibold tracking-tight">{nextAction.title}</h3>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {nextAction.description}
        </p>
        {nextAction.cta && (
          <Button asChild className="mt-2 w-fit gap-2">
            <Link href={nextAction.cta.href}>
              {nextAction.cta.label}
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        )}
      </section>

      <section
        data-testid="research-backlog"
        className="flex flex-col gap-3 border border-border bg-card p-5"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-muted-foreground" />
            <MonoLabel>Research Backlog</MonoLabel>
          </div>
          <Button asChild variant="outline" size="sm" className="gap-1 font-mono text-xs">
            <Link href="/research">Open Research Library</Link>
          </Button>
        </div>
        {backlog.length > 0 ? (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {backlog.map((h) => (
              <Link
                key={h.id}
                href="/research"
                className="flex flex-col gap-1 border border-border p-3 transition-colors hover:border-primary"
              >
                <span className="text-sm font-medium">{h.title}</span>
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  {STATUS_LABEL[h.status]}
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <Link
            href="/research"
            className="rounded border border-dashed border-border p-4 text-center text-xs text-muted-foreground transition-colors hover:border-primary"
          >
            No hypotheses yet — generate your first batch.
          </Link>
        )}
      </section>
    </>
  );
}
