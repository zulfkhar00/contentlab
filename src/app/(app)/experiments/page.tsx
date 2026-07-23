"use client";

// Screen 4 (Experiment Workspace) per actionable_ui_ux_changes.md section 6.
// Refocuses the old Campaigns page on experiment execution: header + status
// row + hypothesis summary + experiment-integrity panel + three variant cards
// + a compact timeline + one contextual primary action.

import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Copy, Check, ClipboardCheck, ClipboardList, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useExperiment,
  getExperimentStatus,
  experimentStatusLabel,
  getPublishedCount,
  getNextActionVariant,
  variantStatusLabel,
  clicksPer1k,
  isValidTiktokUrl,
  type ExperimentData,
  type Variant,
  type VariantRole,
  type VariantStatus,
} from "@/lib/experiment";
import { useHypotheses, type Hypothesis } from "@/lib/hypotheses";

function StatusPill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "active" | "idle" | "success" | "warning";
}) {
  const style =
    tone === "active"
      ? "bg-primary text-primary-foreground"
      : tone === "success"
        ? "bg-[#ECFDF5] text-success"
        : tone === "warning"
          ? "bg-[#FEF2F2] text-destructive"
          : "border border-border bg-card text-muted-foreground";
  return (
    <span
      className={`shrink-0 whitespace-nowrap rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${style}`}
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

function variantTone(status: VariantStatus): "active" | "idle" | "success" | "warning" {
  if (status === "completed") return "success";
  if (status === "tracking") return "active";
  return "idle";
}

function findLinkedHypothesis(
  experiment: ExperimentData,
  hypotheses: Hypothesis[],
): Hypothesis | null {
  // Match by statement so the linked hypothesis Variable / Controlled
  // Elements / Research Question surface on this screen without
  // duplicating them on ExperimentData yet.
  const stmt = experiment.hypothesis.trim();
  return (
    hypotheses.find((h) => h.statement.trim() === stmt) ??
    hypotheses.find((h) => h.status === "testing") ??
    null
  );
}

// Compact per-variant event list surfaced in the Experiment Timeline
// panel. Each variant contributes 1-3 event rows based on its current
// status; no real transition timestamps exist yet so the list is derived,
// not stored.
type TimelineEvent = { role: VariantRole; label: string; done: boolean };

function timelineEventsFor(v: Variant): TimelineEvent[] {
  const events: TimelineEvent[] = [];
  events.push({ role: v.role, label: `${v.role} approved`, done: true });
  if (v.status === "ready_to_record") {
    events.push({ role: v.role, label: `${v.role} awaiting recording`, done: false });
    return events;
  }
  if (v.status === "queued") {
    events.pop();
    events.push({ role: v.role, label: `${v.role} awaiting review`, done: false });
    return events;
  }
  events.push({ role: v.role, label: `${v.role} published`, done: true });
  if (v.status === "tracking") {
    events.push({ role: v.role, label: `${v.role} tracking`, done: false });
  }
  if (v.status === "completed") {
    events.push({ role: v.role, label: `${v.role} tracking completed`, done: true });
  }
  return events;
}

function trackingHoursRemaining(v: Variant, windowHours: number): number | null {
  if (v.status !== "tracking" || !v.publishedAt) return null;
  const startedMs = new Date(v.publishedAt).getTime();
  const endsMs = startedMs + windowHours * 3600 * 1000;
  const remainingMs = endsMs - Date.now();
  return Math.max(0, Math.ceil(remainingMs / (3600 * 1000)));
}

export default function ExperimentWorkspacePage() {
  const { experiment, loaded, startTracking } = useExperiment();
  const { hypotheses, loaded: hypothesesLoaded } = useHypotheses();
  const [urlDraft, setUrlDraft] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [copiedRole, setCopiedRole] = useState<VariantRole | null>(null);

  const linked = useMemo(
    () => (hypothesesLoaded ? findLinkedHypothesis(experiment, hypotheses) : null),
    [experiment, hypotheses, hypothesesLoaded],
  );

  if (!loaded || !hypothesesLoaded) return null;

  const status = getExperimentStatus(experiment.variants);
  const published = getPublishedCount(experiment.variants);
  const nextVariant = getNextActionVariant(experiment.variants);
  const anyCompleted = experiment.variants.some((v) => v.status === "completed");
  const allCompleted = experiment.variants.every((v) => v.status === "completed");

  // Single dominant CTA per doc: "Only one dominant action".
  const primaryAction = nextVariant
    ? {
        label: `Review Variant ${nextVariant.role}`,
        href: `/experiments/brief/${nextVariant.role.toLowerCase()}`,
      }
    : allCompleted
      ? { label: "Review Experiment Results", href: "/insights" }
      : null;

  function copyHook(role: VariantRole, hook: string) {
    navigator.clipboard?.writeText(hook);
    setCopiedRole(role);
    setTimeout(() => setCopiedRole(null), 1500);
  }

  function submitUrl(role: VariantRole) {
    const trimmed = urlDraft.trim();
    if (!isValidTiktokUrl(trimmed)) {
      setUrlError("Paste a valid TikTok video URL (https://tiktok.com/...).".replaceAll("/", "/"));
      return;
    }
    setUrlError(null);
    startTracking(role, trimmed);
    setUrlDraft("");
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">Experiment Workspace</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Is the experiment being executed consistently?
        </p>
      </div>

      <section
        data-testid="experiment-header"
        className="flex flex-col gap-3 border border-border bg-card p-5"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <MonoLabel>Experiment 01</MonoLabel>
            <h3 className="text-xl font-semibold tracking-tight">{experiment.name}</h3>
          </div>
          <StatusPill tone={status === "ready" ? "idle" : "active"}>
            {experimentStatusLabel(status)}
          </StatusPill>
        </div>
        <div className="grid grid-cols-1 gap-3 border-t border-border pt-3 text-sm md:grid-cols-3">
          <div className="flex flex-col gap-1">
            <MonoLabel>Status</MonoLabel>
            <span>{experimentStatusLabel(status)} · {published}/3 published</span>
          </div>
          <div className="flex flex-col gap-1">
            <MonoLabel>Primary Metric</MonoLabel>
            <span>{experiment.primaryMetric}</span>
          </div>
          <div className="flex flex-col gap-1">
            <MonoLabel>Tracking Window</MonoLabel>
            <span>{experiment.trackingWindowLabel}</span>
          </div>
        </div>

        <div className="flex flex-col gap-1 border-t border-border pt-3">
          <MonoLabel>Hypothesis</MonoLabel>
          <p className="border-l-2 border-primary py-1 pl-3 text-sm">
            &quot;{experiment.hypothesis}&quot;
          </p>
        </div>
      </section>

      <section
        data-testid="experiment-integrity"
        className="flex flex-col gap-3 border border-border bg-card p-5"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-muted-foreground" />
          <MonoLabel>Experiment Integrity</MonoLabel>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-1">
            <MonoLabel>Variable Under Test</MonoLabel>
            <p className="text-sm">
              {linked?.independentVariable ?? "Opening angle"}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <MonoLabel>Keep Controlled</MonoLabel>
            {linked?.controlledElements && linked.controlledElements.length > 0 ? (
              <ul className="flex flex-col gap-0.5 text-sm">
                {linked.controlledElements.map((el) => (
                  <li key={el} className="flex items-center gap-2">
                    <span className="size-1 rounded-full bg-muted-foreground" />
                    {el}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                No controlled elements recorded on the linked hypothesis yet.
              </p>
            )}
          </div>
        </div>
        <div className="flex items-start gap-2 border-t border-border pt-3 text-sm">
          <AlertTriangle className="size-4 shrink-0 text-muted-foreground" />
          <span className="text-muted-foreground">
            No deviations detected. Recording briefs mark VARIABLE vs CONTROLLED sections so each variant preserves the design.
          </span>
        </div>
      </section>

      <section data-testid="variant-cards" className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {experiment.variants.map((v) => {
          const isNext = v.role === nextVariant?.role;
          const isLive = v.status === "tracking" || v.status === "completed";
          const hoursLeft = trackingHoursRemaining(v, experiment.trackingWindowHours);
          return (
            <div
              key={v.role}
              className={`flex h-full flex-col bg-card ${
                isNext ? "border-2 border-primary" : "border border-border"
              }`}
            >
              <div className="flex items-start justify-between gap-2 border-b border-border bg-secondary p-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex size-7 items-center justify-center bg-primary font-mono text-xs text-primary-foreground">
                    {v.role}
                  </span>
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold">{v.title}</span>
                    <MonoLabel>{v.roleLabel}</MonoLabel>
                  </div>
                </div>
                <StatusPill tone={variantTone(v.status)}>
                  {variantStatusLabel(v.status)}
                </StatusPill>
              </div>
              <div className="flex flex-1 flex-col gap-3 p-3">
                <div className="flex flex-col gap-1">
                  <MonoLabel>Variable Value</MonoLabel>
                  <p className="text-sm">{v.variableUnderTest}</p>
                </div>
                {v.status === "completed" && v.metrics && (
                  <div className="flex flex-col gap-1 border border-border bg-secondary p-2 font-mono text-xs">
                    <div className="flex items-center gap-1 border-b border-border pb-1">
                      <MonoLabel>Testing:</MonoLabel>
                      <span className="truncate text-[10px]">{v.variableUnderTest}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <div className="flex flex-col">
                        <MonoLabel>Views</MonoLabel>
                        <span>{v.metrics.views.toLocaleString()}</span>
                      </div>
                      <div className="flex flex-col">
                        <MonoLabel>Clicks / 1K</MonoLabel>
                        <span>{clicksPer1k(v.metrics.views, v.metrics.clicks)}</span>
                      </div>
                    </div>
                  </div>
                )}
                {v.status === "tracking" && (
                  <div className="flex flex-col gap-1 border border-border bg-secondary p-2 text-xs">
                    <div className="flex items-center gap-1">
                      <MonoLabel>Testing:</MonoLabel>
                      <span className="truncate text-[10px] text-muted-foreground">{v.variableUnderTest}</span>
                    </div>
                    <span>
                      {hoursLeft === null
                        ? "Tracking window active"
                        : hoursLeft === 0
                          ? "Window ended — refresh metrics"
                          : `Ends in ${hoursLeft}h`}
                    </span>
                  </div>
                )}
                {isNext && v.status === "ready_to_record" && (
                  <div className="mt-auto flex flex-col gap-1">
                    <MonoLabel>Paste TikTok URL to start tracking</MonoLabel>
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
                    {urlError && <p className="text-xs text-destructive">{urlError}</p>}
                    <Button size="sm" variant="outline" className="mt-1" onClick={() => submitUrl(v.role)}>
                      Start Tracking
                    </Button>
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-2 border-t border-border p-3">
                {v.status === "completed" ? (
                  <div className="flex flex-col gap-2">
                    {v.observation?.notes && (
                      <div className="flex items-center gap-1">
                        <ClipboardCheck className="size-3.5 text-success" />
                        <span className="font-mono text-[10px] uppercase tracking-wide text-success" data-testid={`observed-badge-${v.role}`}>Observed</span>
                      </div>
                    )}
                    <Button asChild size="sm" variant="outline">
                      <Link href={`/experiments/observe/${v.role.toLowerCase()}`}>Log Observation</Link>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link href={`/insights?ex=${v.role}`}>View Results</Link>
                    </Button>
                  </div>
                ) : v.status === "tracking" ? (
                  <div className="flex flex-col gap-2">
                    {v.observation?.notes && (
                      <div className="flex items-center gap-1">
                        <ClipboardCheck className="size-3.5 text-success" />
                        <span className="font-mono text-[10px] uppercase tracking-wide text-success" data-testid={`observed-badge-${v.role}`}>Observed</span>
                      </div>
                    )}
                    <Button asChild size="sm" variant="outline">
                      <Link href={`/experiments/observe/${v.role.toLowerCase()}`}>Log Observation</Link>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/videos">View Tracking</Link>
                    </Button>
                  </div>
                ) : (
                  <>
                    <Button asChild size="sm">
                      <Link href={`/experiments/brief/${v.role.toLowerCase()}`}>
                        Review Variant
                      </Link>
                    </Button>
                    <Button size="sm" variant="outline" className="gap-1" onClick={() => copyHook(v.role, v.hook)}>
                      {copiedRole === v.role ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                      {copiedRole === v.role ? "Copied!" : "Copy Hook"}
                    </Button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </section>

      <section
        data-testid="experiment-timeline"
        className="flex flex-col gap-3 border border-border bg-card p-5"
      >
        <div className="flex items-center gap-2">
          <ClipboardList className="size-4 text-muted-foreground" />
          <MonoLabel>Experiment Timeline</MonoLabel>
        </div>
        <ul className="flex flex-col gap-1.5 text-sm">
          {experiment.variants.flatMap((v) => timelineEventsFor(v)).map((ev, idx) => (
            <li
              key={`${ev.role}-${ev.label}-${idx}`}
              className="flex items-center gap-3 border border-border p-2"
            >
              <span
                className={`size-2 rounded-full ${ev.done ? "bg-success" : "bg-muted-foreground"}`}
                aria-hidden
              />
              <span className="font-mono text-xs">{ev.label}</span>
              <span className="ml-auto">
                {ev.done ? (
                  <StatusPill tone="success">Done</StatusPill>
                ) : (
                  <StatusPill tone="idle">Pending</StatusPill>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {primaryAction && (
        <section
          data-testid="primary-action-strip"
          className="flex flex-col items-start gap-3 border border-border bg-card p-5 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex flex-col gap-1">
            <MonoLabel>Primary Action</MonoLabel>
            <span className="text-sm">
              {allCompleted
                ? "All tracking windows are complete."
                : "Only one dominant action for now — keep the experiment moving."}
            </span>
          </div>
          <Button asChild className="gap-2">
            <Link href={primaryAction.href}>
              {primaryAction.label}
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </section>
      )}
      {!primaryAction && anyCompleted === false && (
        <section className="flex items-start gap-2 border border-dashed border-border bg-card p-4 text-xs text-muted-foreground">
          <ClipboardList className="size-4" />
          <span>
            All variants are tracking. Once every 72h window ends, results appear here.
          </span>
        </section>
      )}
    </>
  );
}
