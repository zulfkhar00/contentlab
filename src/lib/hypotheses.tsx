"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Status = "generated" | "approved" | "testing" | "tested" | "rejected";

export type Hypothesis = {
  id: string;
  title: string;
  statement: string;
  category: string;
  primaryMetric: string;
  rationale: string;
  status: Status;
  // Set only on AI-drafted follow-ups (see lib/insights.tsx toHypothesis()) —
  // absent on cold-start/"Generate More" hypotheses, which have no prior
  // evidence to trace back to.
  parentInsightId?: string;
};

export const STATUS_LABEL: Record<Status, string> = {
  generated: "Generated",
  approved: "Approved",
  testing: "Testing",
  tested: "Tested",
  rejected: "Rejected",
};

export const SEED_HYPOTHESES: Hypothesis[] = [
  {
    id: "h1",
    title: "Pain hooks outperform product demos",
    statement:
      "Founder pain stories will drive more product clicks than direct product feature demos.",
    category: "Pain / Founder Story",
    primaryMetric: "Clicks / 1K Views",
    rationale: "Pain-first content creates relevance before introducing the product.",
    status: "approved",
  },
  {
    id: "h2",
    title: "Founder failure stories drive more product clicks",
    statement:
      "Founder failure stories drive more product clicks than generic product demos.",
    category: "Founder Story",
    primaryMetric: "Clicks / 1K Views",
    rationale: "Concrete failure stories build more trust than generic pitches.",
    status: "testing",
  },
  {
    id: "h3",
    title: "Distribution problem beats AI automation angle",
    statement:
      "Technical founders respond more to distribution pain than generic AI automation benefits.",
    category: "Contrarian Insight",
    primaryMetric: "Clicks / 1K Views",
    rationale:
      "Distribution failure is more emotionally relevant to technical founders than generic AI benefits.",
    status: "generated",
  },
  {
    id: "h4",
    title: "Founder journey creates more trust",
    statement:
      "Founder journey videos will generate more product-related comments per 1,000 views than polished product pitches.",
    category: "Founder Story",
    primaryMetric: "Comments / 1K Views",
    rationale:
      "Personal narratives build community trust more effectively than polished pitches.",
    status: "generated",
  },
  {
    id: "h5",
    title: "Short pain-first hooks outperform long-form storytelling",
    statement:
      "Videos that open with a short, concrete pain hook will generate more clicks per 1,000 views than longer narrative openings.",
    category: "Product / Feature",
    primaryMetric: "Clicks / 1K Views",
    rationale: "Shorter hooks reduce drop-off before the CTA is shown.",
    status: "tested",
  },
  {
    id: "h6",
    title: "Use trending sounds for every post",
    statement:
      "Attaching trending sounds to every video will generate more clicks than videos without trending sounds.",
    category: "Format",
    primaryMetric: "Views",
    rationale: "Sound trends are noisy and don't isolate the message variable.",
    status: "rejected",
  },
];

const STORAGE_KEY = "cl_hypotheses";

function load(): Hypothesis[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function persist(list: Hypothesis[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

type HypothesesContextValue = {
  hypotheses: Hypothesis[];
  loaded: boolean;
  addHypothesis: (h: Hypothesis) => void;
  updateHypothesis: (id: string, patch: Partial<Hypothesis>) => void;
  removeHypothesis: (id: string) => void;
  setAll: (list: Hypothesis[]) => void;
};

const Ctx = createContext<HypothesesContextValue | null>(null);

// TODO(api): replace localStorage with real hypothesis endpoints once the
// backend exists. A single provider (mirroring CampaignProvider) keeps
// Overview, Hypotheses, and Insights showing one consistent, live list
// instead of each holding its own stale copy — needed so a follow-up
// hypothesis drafted from an Insight actually shows up on the Hypotheses page.
export function HypothesesProvider({ children }: { children: ReactNode }) {
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setHypotheses(load());
    setLoaded(true);
  }, []);

  function addHypothesis(h: Hypothesis) {
    setHypotheses((prev) => {
      // Guards against two clicks landing before a re-render (e.g. a
      // follow-up "Add to Hypotheses" button) both reading a stale "not
      // yet added" check and inserting the same id twice.
      if (prev.some((existing) => existing.id === h.id)) return prev;
      const next = [h, ...prev];
      persist(next);
      return next;
    });
  }

  function updateHypothesis(id: string, patch: Partial<Hypothesis>) {
    setHypotheses((prev) => {
      const next = prev.map((h) => (h.id === id ? { ...h, ...patch } : h));
      persist(next);
      return next;
    });
  }

  function removeHypothesis(id: string) {
    setHypotheses((prev) => {
      const next = prev.filter((h) => h.id !== id);
      persist(next);
      return next;
    });
  }

  function setAll(list: Hypothesis[]) {
    setHypotheses(list);
    persist(list);
  }

  return (
    <Ctx.Provider
      value={{ hypotheses, loaded, addHypothesis, updateHypothesis, removeHypothesis, setAll }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useHypotheses(): HypothesesContextValue {
  const value = useContext(Ctx);
  if (!value) {
    throw new Error("useHypotheses must be used within a HypothesesProvider");
  }
  return value;
}
