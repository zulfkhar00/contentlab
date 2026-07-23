import { clicksPer1k, type VariantRole } from "@/lib/experiment";
import type { Hypothesis, HypothesisRelationship } from "@/lib/hypotheses";

export type ComparedVariant = {
  role: VariantRole;
  title: string;
  roleLabel: "Control" | "Hypothesis Treatment" | "Alternative Treatment";
  views: number;
  clicks: number;
};

export type NextCandidateKind = "Replication" | "Mechanism Isolation" | "Optimization";

export type NextCandidate = {
  id: string;
  kind: NextCandidateKind;
  statement: string;
  whyThisFollows: string;
  recommended?: boolean;
  category?: string;
  primaryMetric?: string;
  relationshipType: HypothesisRelationship;
  previousLearning: string;
  remainingUnknown: string;
};

export type Insight = {
  id: string;
  // The Hypothesis this experiment tested — lets the Research page's "View
  // Insight" link and the "Follow-up of" note resolve without guessing.
  sourceHypothesisId: string;
  // Kept named `experimentName` in the vocabulary shift; the old
  // `campaignName` was retired; new data uses experimentName. Leave the
  // insights below all set the new name.
  experimentName: string;
  hypothesis: string;
  primaryMetric: string;
  completedAt: string;
  windowHours: number;
  control: ComparedVariant;
  treatment: ComparedVariant;
  lift: number;
  evidenceBasis: string;
  supportedLearning: string;
  doNotInferYet: string[];
  recommendedNextTest: string;
  followUp: {
    title: string;
    statement: string;
    category: string;
    primaryMetric: string;
    rationale: string;
    // core_ideas.md §"How the next hypothesis should be generated": every
    // follow-up sits in one of six explicit relationships to the parent.
    // The seed follow-up narrows the winning treatment's hook — that's
    // mechanism isolation.
    relationshipType: HypothesisRelationship;
    // Carries forward into the follow-up Hypothesis so the Follow-up
    // Hypothesis Review screen can show what was learned and what remains
    // unknown without recomputing from insight fields.
    previousLearning: string;
    remainingUnknown: string;
  };
  // ---- Screen 6 (Experiment Results) extensions ----
  // Section 1 (Research Question).
  researchQuestion?: string;
  // Optional third variant so the doc-required 3-row comparison table can
  // render when the experiment had an Alternative Treatment.
  alternative?: ComparedVariant;
  // Section 7 (Experiment Limitations).
  limitations?: string[];
  // Section 8 (Outcome Classification).
  outcome?: { label: string; description: string };
  // Section 9 (Next Hypothesis Candidates).
  nextCandidates?: NextCandidate[];
};

// TODO(ai): fictional completed-experiment analysis standing in for a real
// Claude-generated insight once that service exists. Deliberately built
// around h5 ("Short pain-first hooks outperform long-form storytelling")
// rather than the brief's Founder Failure / Product Demo experiment — that
// experiment is still active and in-progress in lib/experiment.tsx, so it
// can't also be shown here as completed without contradicting the
// Experiments/Videos/Overview surfaces.
export const SEED_INSIGHTS: Insight[] = [
  {
    id: "i1",
    sourceHypothesisId: "h5",
    experimentName: "Short Hook vs Long-Form Story",
    hypothesis:
      "Videos that open with a short, concrete pain hook will generate more clicks per 1,000 views than longer narrative openings.",
    primaryMetric: "Clicks / 1K Views",
    completedAt: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString(),
    windowHours: 72,
    control: {
      role: "A",
      title: "Long-Form Story Opening",
      roleLabel: "Control",
      views: 6400,
      clicks: 64,
    },
    treatment: {
      role: "B",
      title: "Short Pain-First Hook",
      roleLabel: "Hypothesis Treatment",
      views: 6100,
      clicks: 110,
    },
    lift: 1.8,
    evidenceBasis:
      "Both variants ran a full 72-hour tracking window with the same audience, CTA, and offer — only the opening length and structure changed.",
    supportedLearning:
      "Opening with the pain point in the first few seconds kept more viewers watching through to the CTA than easing into it with a longer story setup.",
    doNotInferYet: [
      "This compares one short hook against one long-form opening — it doesn't establish an ideal hook length.",
      "Both videos ran on the same account and audience; the result hasn't been tested against a different audience or offer yet.",
    ],
    recommendedNextTest:
      "Test a second short pain-first hook with a different specific pain point to see if the effect holds beyond this one script.",
    researchQuestion:
      "Which opening length generates more clicks per 1,000 views?",
    limitations: [
      "Both variants ran on the same account and audience so the effect could carry account-level dynamics",
      "Only one long-form and one short hook were compared - length inside each style was not varied",
    ],
    outcome: {
      label: "Directional Difference",
      description:
        "The treatment produced a clear observed difference but replication or mechanism isolation is needed before treating it as a reusable rule",
    },
    nextCandidates: [
      {
        id: "i1-c1",
        kind: "Replication",
        statement:
          "A different short pain-first hook will also generate more clicks per 1,000 views than the long-form control.",
        whyThisFollows: "The current result has only been observed once",
        relationshipType: "replication",
        previousLearning:
          "The short pain-first hook produced greater click efficiency than the long-form opening in this experiment",
        remainingUnknown:
          "Whether the effect holds when the specific words in the short hook change",
        category: "Format",
        primaryMetric: "Clicks / 1K Views",
      },
      {
        id: "i1-c2",
        kind: "Mechanism Isolation",
        statement:
          "A short hook naming a more specific pain point will generate more clicks per 1,000 views than the same hook without that detail.",
        whyThisFollows:
          "The winning treatment changed both hook length and specificity; this test isolates the specificity dimension",
        recommended: true,
        relationshipType: "mechanism-isolation",
        previousLearning:
          "The short pain-first hook outperformed the long-form opening but two things changed at once",
        remainingUnknown:
          "Whether the click lift came from hook length or from the specificity of the pain named inside the short hook",
        category: "Format",
        primaryMetric: "Clicks / 1K Views",
      },
      {
        id: "i1-c3",
        kind: "Optimization",
        statement:
          "Showing the product at 10 seconds instead of 25 seconds after the same short pain-first hook will further increase clicks per 1,000 views.",
        whyThisFollows:
          "The opening captured attention; bringing the product context earlier may convert that attention more efficiently",
        relationshipType: "parameter-optimization",
        previousLearning:
          "The short pain-first hook held attention through the first several seconds",
        remainingUnknown:
          "Whether product reveal timing further improves click efficiency given the winning hook",
        category: "Structure",
        primaryMetric: "Clicks / 1K Views",
      },
    ],
    followUp: {
      title: "Follow-up: Sharper pain-first hooks",
      statement:
        "A short pain-first hook naming a more specific, concrete pain point will generate more clicks per 1,000 views than this experiment's winning hook.",
      category: "Format",
      primaryMetric: "Clicks / 1K Views",
      rationale:
        "The short hook already beat the long-form opening; narrowing the hook to a more specific pain point tests whether specificity compounds the gain.",
      relationshipType: "mechanism-isolation",
      previousLearning:
        "The short pain-first hook generated greater click efficiency than the long-form opening.",
      remainingUnknown:
        "Whether the effect came from hook length itself, or from the specificity of the pain point named in the short hook.",
    },
  },
];

export function insightClicksPer1k(v: ComparedVariant): number {
  return clicksPer1k(v.views, v.clicks);
}

// Follow-up Hypothesis derived from an Insight. Carries the lineage fields
// (parent insight, relationship type, previous learning, remaining unknown)
// forward so the Follow-up Hypothesis Review screen — and the Research
// Library "Derived From" note — can render lineage without recomputing.
// Follow-up Hypothesis derived from a specific NextCandidate on an Insight.
// Used by Screen 6 (Experiment Results) so each of the three candidate cards
// can hand a fully-formed Hypothesis to the Research Library.
export function candidateToHypothesis(
  insight: Insight,
  candidate: NextCandidate,
): Hypothesis {
  return {
    id: candidate.id + "-hypothesis",
    title: candidate.kind + ": " + candidate.statement.slice(0, 60).trim() + (candidate.statement.length > 60 ? "..." : ""),
    statement: candidate.statement,
    category: candidate.category ?? "Format",
    primaryMetric: candidate.primaryMetric ?? insight.primaryMetric,
    rationale: candidate.whyThisFollows,
    status: "suggested",
    parentInsightId: insight.id,
    relationshipType: candidate.relationshipType,
    previousLearning: candidate.previousLearning,
    remainingUnknown: candidate.remainingUnknown,
  };
}

export function toHypothesis(insight: Insight): Hypothesis {
  return {
    id: `${insight.id}-followup`,
    title: insight.followUp.title,
    statement: insight.followUp.statement,
    category: insight.followUp.category,
    primaryMetric: insight.followUp.primaryMetric,
    rationale: insight.followUp.rationale,
    status: "suggested",
    parentInsightId: insight.id,
    relationshipType: insight.followUp.relationshipType,
    previousLearning: insight.followUp.previousLearning,
    remainingUnknown: insight.followUp.remainingUnknown,
  };
}
