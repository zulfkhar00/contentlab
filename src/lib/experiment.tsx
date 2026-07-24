"use client";

// Owns Experiment + Variant state. One Hypothesis maps to exactly one
// Experiment with three Variants. Persists to `cl_experiment` in
// localStorage; a one-shot migration reads the legacy `cl_campaign` key
// once and drops it, so existing sessions from before the rename don't
// lose their in-progress variants.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type VariantRole = "A" | "B" | "C";

export type VariantStatus = "queued" | "ready_to_record" | "tracking" | "completed";

export type VariantMetrics = {
  views: number;
  likes: number;
  comments: number;
  clicks: number;
};

export type Variant = {
  role: VariantRole;
  title: string;
  roleLabel: "Control" | "Hypothesis Treatment" | "Alternative Treatment";
  hook: string;
  hookDeliveryNote: string;
  context: string;
  variableUnderTest: string;
  onScreenText: string;
  status: VariantStatus;
  tiktokUrl?: string;
  metrics?: VariantMetrics;
  observation?: VariantObservation;
  // Set the moment a variant starts tracking — real wall-clock time, not
  // seed data — so the tracking window can be computed honestly instead of
  // faking elapsed/remaining numbers.
  publishedAt?: string;
};

// Segments that stay identical across all three variants, per the "keep
// everything but the primary variable constant" rule.
export type LockedScript = {
  lesson: string;
  product: string;
  cta: string;
  targetDurationLabel: string;
};

export type ExperimentData = {
  name: string;
  hypothesis: string;
  primaryMetric: string;
  cta: string;
  trackingWindowLabel: string;
  trackingWindowHours: number;
  script: LockedScript;
  variants: [Variant, Variant, Variant];
};

// The brief's authoritative demo experiment — exact hooks, roles, and order.
// A function (not a constant) so Variant A's seed publishedAt is always a
// real, fresh "a few hours ago" timestamp instead of a fixed date that would
// drift stale over calendar time.
function createDefaultExperiment(): ExperimentData {
  return {
    name: "Founder Failure Hook vs Product Demo",
    hypothesis:
      "Founder failure stories drive more product clicks than generic product demos.",
    primaryMetric: "Clicks / 1K Views",
    cta: "Check link in bio",
    trackingWindowLabel: "72h per variant",
    trackingWindowHours: 72,
    script: {
      lesson:
        "I thought building the product was the hard part. Then I learned that a product nobody discovers is not really a startup.",
      product:
        "That is why I'm building Content Lab: to help founders test which messages actually drive product clicks.",
      cta: "Check the link in my bio to see the tool I'm building.",
      targetDurationLabel: "50s",
    },
    variants: [
      {
        role: "A",
        title: "Product Demo",
        roleLabel: "Control",
        hook: "I am building a tool that turns one startup idea into three TikTok experiments.",
        hookDeliveryNote: "Neutral, confident tone. Show the product briefly on screen.",
        context: "It sounds simple. Distribution is the hard part.",
        variableUnderTest: "Product-first opening",
        onScreenText: "One idea. Three TikTok tests.",
        status: "tracking",
        // Brief's authoritative comparison: A = 2.9 clicks/1K (24 clicks on
        // 8,204 views), not the 11.7 that belongs to Variant B.
        metrics: { views: 8204, likes: 412, comments: 38, clicks: 24 },
        publishedAt: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
      },
      {
        role: "B",
        title: "Founder Failure Story",
        roleLabel: "Hypothesis Treatment",
        hook: "I spent almost $2,000 on UGC ads and got almost no users.",
        hookDeliveryNote: "Look disappointed but analytical. Quick cut at the end.",
        context: "The app worked. The marketing didn't.",
        variableUnderTest: "Founder-failure opening",
        onScreenText: "$2,000 on UGC. Almost no users.",
        status: "ready_to_record",
      },
      {
        role: "C",
        title: "Contrarian Insight",
        roleLabel: "Alternative Treatment",
        hook: "Most engineers do not have a product problem. They have a distribution problem.",
        hookDeliveryNote: "Deadpan, matter-of-fact delivery.",
        context: "They can build anything. They just can't get anyone to see it.",
        variableUnderTest: "Contrarian-insight opening",
        onScreenText: "Everyone has a distribution problem.",
        status: "queued",
      },
    ],
  };
}

export type ExperimentStatus = "ready" | "in_progress" | "tracking";

const LIVE_STATUSES: VariantStatus[] = ["tracking", "completed"];

export function getPublishedCount(variants: Variant[]): number {
  return variants.filter((v) => LIVE_STATUSES.includes(v.status)).length;
}

// Ready (nothing published) -> In Progress (1-2 published) -> Tracking (all 3
// published, windows active) -> Analyzing -> Completed. Analyzing/Completed
// require a real time-based window and aren't modeled yet.
export function getExperimentStatus(variants: Variant[]): ExperimentStatus {
  const live = getPublishedCount(variants);
  if (live === 0) return "ready";
  if (live < variants.length) return "in_progress";
  return "tracking";
}

export function experimentStatusLabel(status: ExperimentStatus): string {
  return status === "ready"
    ? "Ready"
    : status === "in_progress"
      ? "In Progress"
      : "Tracking";
}

export function variantStatusLabel(status: VariantStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "ready_to_record":
      return "Ready to Record";
    case "tracking":
      return "Tracking";
    case "completed":
      return "Completed";
  }
}

export function variantStatusTone(status: VariantStatus): "active" | "idle" {
  return LIVE_STATUSES.includes(status) ? "active" : "idle";
}

export function getNextActionVariant(variants: Variant[]): Variant | null {
  return variants.find((v) => !LIVE_STATUSES.includes(v.status)) ?? null;
}

export function clicksPer1k(views: number, clicks: number): number {
  if (!views) return 0;
  return Math.round((clicks / views) * 1000 * 10) / 10;
}

export function isValidTiktokUrl(url: string): boolean {
  return /^https:\/\/([\w-]+\.)?tiktok\.com\/.+/i.test(url.trim());
}

export function getVariant(
  experiment: ExperimentData,
  role: string | undefined,
): Variant | null {
  const upper = role?.toUpperCase();
  return experiment.variants.find((v) => v.role === upper) ?? null;
}

export function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return `Today ${time}`;
  return `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`;
}

export type TrackingWindow = {
  startedAt: Date;
  endsAt: Date;
  elapsedHours: number;
  percentElapsed: number;
};

// Computed from the variant's real publishedAt timestamp — never fabricated
// "elapsed" or "remaining" figures.
export function getTrackingWindow(
  variant: Variant,
  windowHours: number,
): TrackingWindow | null {
  if (!variant.publishedAt) return null;
  const startedAt = new Date(variant.publishedAt);
  const windowMs = windowHours * 60 * 60 * 1000;
  const endsAt = new Date(startedAt.getTime() + windowMs);
  const elapsedMs = Math.max(0, Date.now() - startedAt.getTime());
  return {
    startedAt,
    endsAt,
    elapsedHours: Math.round((elapsedMs / (60 * 60 * 1000)) * 10) / 10,
    percentElapsed: Math.min(100, (elapsedMs / windowMs) * 100),
  };
}

const STORAGE_KEY = "cl_experiment";
const LEGACY_STORAGE_KEY = "cl_campaign";

function load(): ExperimentData | null {
  if (typeof window === "undefined") return null;
  try {
    const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
    if (legacy && !window.localStorage.getItem(STORAGE_KEY)) {
      window.localStorage.setItem(STORAGE_KEY, legacy);
      window.localStorage.removeItem(LEGACY_STORAGE_KEY);
    }
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function persist(e: ExperimentData) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(e));
}

export type VariantBriefEdit = Pick<
  Variant,
  "hook" | "hookDeliveryNote" | "context" | "onScreenText"
>;

export type VariantObservation = {
  deliveredVariable: boolean | null;
  reason: string;
  notes: string;
  dropOffAt: string;
  sentiment: string;
  unexpected: string;
};

export function emptyObservation(): VariantObservation {
  return { deliveredVariable: null, reason: "", notes: "", dropOffAt: "", sentiment: "", unexpected: "" };
}

type ExperimentContextValue = {
  experiment: ExperimentData | null;
  loaded: boolean;
  startTracking: (role: VariantRole, url: string) => void;
  updateVariantBrief: (role: VariantRole, edit: VariantBriefEdit) => void;
  updateVariantObservation: (role: VariantRole, obs: Partial<VariantObservation>) => void;
};

const Ctx = createContext<ExperimentContextValue | null>(null);

// TODO(api): replace localStorage with real experiment/variant/scrape-job
// endpoints once the backend exists. A single provider keeps Overview and
// Experiments showing one consistent, live experiment instead of each
// holding its own stale copy.
export function ExperimentProvider({ children }: { children: ReactNode }) {
  const [experiment, setExperimentState] = useState<ExperimentData | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const stored = load();
    setExperimentState(stored);
    setLoaded(true);
  }, []);

  function startTracking(role: VariantRole, url: string) {
    setExperimentState((prev) => {
      if (!prev) return prev;
      const idx = prev.variants.findIndex((v) => v.role === role);
      if (idx === -1) return prev;
      const variants = prev.variants.map((v, i) => {
        if (i === idx) {
          return {
            ...v,
            status: "tracking" as const,
            tiktokUrl: url,
            metrics: v.metrics ?? { views: 1240, likes: 58, comments: 6, clicks: 14 },
            publishedAt: v.publishedAt ?? new Date().toISOString(),
          };
        }
        // Unlock the next queued variant now that this one is live.
        if (i === idx + 1 && v.status === "queued") {
          return { ...v, status: "ready_to_record" as const };
        }
        return v;
      }) as [Variant, Variant, Variant];
      const next = { ...prev, variants };
      persist(next);
      return next;
    });
  }

  function updateVariantBrief(role: VariantRole, edit: VariantBriefEdit) {
    setExperimentState((prev) => {
      if (!prev) return prev;
      const variants = prev.variants.map((v) =>
        v.role === role ? { ...v, ...edit } : v,
      ) as [Variant, Variant, Variant];
      const next = { ...prev, variants };
      persist(next);
      return next;
    });
  }

  function updateVariantObservation(role: VariantRole, obs: Partial<VariantObservation>) {
    setExperimentState((prev) => {
      if (!prev) return prev;
      const variants = prev.variants.map((v) =>
        v.role === role
          ? { ...v, observation: { ...(v.observation ?? emptyObservation()), ...obs } }
          : v,
      ) as [Variant, Variant, Variant];
      const next = { ...prev, variants };
      persist(next);
      return next;
    });
  }

  return (
    <Ctx.Provider
      value={{ experiment, loaded, startTracking, updateVariantBrief, updateVariantObservation }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useExperiment(): ExperimentContextValue {
  const value = useContext(Ctx);
  if (!value) {
    throw new Error("useExperiment must be used within an ExperimentProvider");
  }
  return value;
}
