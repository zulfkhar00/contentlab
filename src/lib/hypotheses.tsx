"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// core_ideas.md vocabulary:
// - "suggested": AI just proposed this, user hasn't opened it yet
// - "draft":     user is editing but hasn't approved the experiment logic
// - "approved":  experiment logic locked; variants can be generated
// - "testing":   experiment is running (variants in tracking)
// - "learned":   experiment completed; an Insight exists for it
// - "rejected":  user dismissed
//
// The pair (suggested, draft) split what was formerly "generated". "learned"
// replaces "tested" — the doc is deliberate about calling the terminal state
// what the product actually produced (a learning), not that a test happened.
export type Status =
  | "suggested"
  | "draft"
  | "approved"
  | "testing"
  | "learned"
  | "rejected";

// core_ideas.md §"How the next hypothesis should be generated": every
// follow-up hypothesis relates to its parent through exactly one of these
// six relationships. Unset on cold-start hypotheses that aren't derived from
// prior evidence.
export type HypothesisRelationship =
  | "replication"
  | "mechanism-isolation"
  | "parameter-optimization"
  | "generalization"
  | "counter-hypothesis"
  | "recovery-redesign";

export const RELATIONSHIP_LABEL: Record<HypothesisRelationship, string> = {
  replication: "Replication",
  "mechanism-isolation": "Mechanism Isolation",
  "parameter-optimization": "Parameter Optimization",
  generalization: "Generalization",
  "counter-hypothesis": "Counter-hypothesis",
  "recovery-redesign": "Recovery / Redesign",
};

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

  // Experiment-design fields introduced by core_ideas.md §"Stage 2:
  // Generate the hypothesis". All optional so old hypotheses (and the
  // localStorage payload from before this shim) still parse. Later screens
  // (Hypothesis Review, Experiment Workspace) will fill these in for every
  // new hypothesis; the seeds below start populating them so downstream
  // screens have real content to render.
  researchQuestion?: string;
  independentVariable?: string;
  controlCondition?: string;
  treatmentCondition?: string;
  controlledElements?: string[];
  contradictionCondition?: string;

  // Lineage fields for follow-ups derived from a previous experiment.
  relationshipType?: HypothesisRelationship;
  previousLearning?: string;
  remainingUnknown?: string;
};

export const STATUS_LABEL: Record<Status, string> = {
  suggested: "Suggested",
  draft: "Draft",
  approved: "Approved",
  testing: "Testing",
  learned: "Learned",
  rejected: "Rejected",
};

// Migrate legacy status values persisted before the vocabulary shift.
// "generated" was the AI-drafted default → maps to "suggested"; "tested"
// meant "we ran the experiment and have a result" → maps to "learned".
type LegacyStatus = "generated" | "tested";
const LEGACY_STATUS_MAP: Record<LegacyStatus, Status> = {
  generated: "suggested",
  tested: "learned",
};

function migrateStatus(raw: string): Status {
  if (raw in LEGACY_STATUS_MAP) {
    return LEGACY_STATUS_MAP[raw as LegacyStatus];
  }
  return raw as Status;
}

function migrateHypothesis(h: Hypothesis): Hypothesis {
  return { ...h, status: migrateStatus(h.status as string) };
}

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
    researchQuestion: "Which opening framing generates more product clicks?",
    independentVariable: "Opening framing",
    controlCondition: "Direct product feature demo opening",
    treatmentCondition: "Founder pain-story opening",
    controlledElements: [
      "Audience",
      "Founder-led talking head",
      "Duration",
      "Product explanation",
      "Offer",
      "CTA",
      "Caption format",
    ],
    contradictionCondition:
      "The pain-story treatment does not outperform the product-demo control after all tracking windows complete.",
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
    researchQuestion: "Which opening style generates more product clicks?",
    independentVariable: "Opening angle",
    controlCondition: "Product-demo opening",
    treatmentCondition: "Concrete founder-failure opening",
    controlledElements: [
      "Audience",
      "Founder-led talking head",
      "Duration",
      "Product explanation",
      "Offer",
      "CTA",
      "Caption format",
      "Publishing account",
    ],
    contradictionCondition:
      "The founder-failure treatment does not outperform the product-demo control after all tracking windows complete.",
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
    status: "suggested",
    researchQuestion: "Which pain framing resonates most with technical founders?",
    independentVariable: "Pain framing",
    controlCondition: "Generic AI automation benefits framing",
    treatmentCondition: "Distribution-problem framing",
    controlledElements: [
      "Audience",
      "Founder-led talking head",
      "Duration",
      "Product explanation",
      "Offer",
      "CTA",
    ],
    contradictionCondition:
      "The distribution-problem framing does not outperform the AI automation framing after all tracking windows complete.",
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
    status: "suggested",
    researchQuestion:
      "Which style of storytelling generates more product-related comments?",
    independentVariable: "Storytelling style",
    controlCondition: "Polished product pitch",
    treatmentCondition: "Founder journey narrative",
    controlledElements: [
      "Audience",
      "Founder-led talking head",
      "Duration",
      "Product explanation",
      "Offer",
      "CTA",
    ],
    contradictionCondition:
      "The founder-journey treatment does not outperform the polished-pitch control on comments / 1K views after all tracking windows complete.",
  },
  {
    id: "h5",
    title: "Short pain-first hooks outperform long-form storytelling",
    statement:
      "Videos that open with a short, concrete pain hook will generate more clicks per 1,000 views than longer narrative openings.",
    category: "Product / Feature",
    primaryMetric: "Clicks / 1K Views",
    rationale: "Shorter hooks reduce drop-off before the CTA is shown.",
    status: "learned",
    researchQuestion: "Does opening length affect click efficiency?",
    independentVariable: "Opening length and structure",
    controlCondition: "Long-form narrative opening",
    treatmentCondition: "Short pain-first hook",
    controlledElements: [
      "Audience",
      "Founder-led talking head",
      "Duration",
      "Product explanation",
      "Offer",
      "CTA",
    ],
    contradictionCondition:
      "The short pain-first hook does not outperform the long-form opening after all tracking windows complete.",
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
    // Rejected because it fails core_ideas.md's controlled-experiment rule:
    // it changes format AND is orthogonal to the message variable being
    // tested elsewhere in the thread.
  },
];

const STORAGE_KEY = "cl_hypotheses";

function load(): Hypothesis[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Hypothesis[];
    // Legacy-status migration runs every load. It's idempotent — statuses
    // already in the new vocabulary pass through untouched.
    return parsed.map(migrateHypothesis);
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
// backend exists. A single provider (mirroring ExperimentProvider) keeps
// Overview, Research, and Insights showing one consistent, live list —
// needed so a follow-up hypothesis drafted from an Insight actually shows
// up on the Research page.
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
