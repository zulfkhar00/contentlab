import { clicksPer1k, type VariantRole } from "@/lib/campaign";
import type { Hypothesis } from "@/lib/hypotheses";

export type ComparedVariant = {
  role: VariantRole;
  title: string;
  roleLabel: "Control" | "Hypothesis Treatment" | "Alternative Treatment";
  views: number;
  clicks: number;
};

export type Insight = {
  id: string;
  // The Hypothesis this campaign tested — lets the Hypotheses page's "View
  // Insight" link and the "Follow-up of" note resolve without guessing.
  sourceHypothesisId: string;
  campaignName: string;
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
  };
};

// TODO(ai): fictional completed-campaign analysis standing in for a real
// Claude-generated insight once that service exists (see hypotheses/page.tsx
// craftRevision() for the same convention). Deliberately built around h5
// ("Short pain-first hooks outperform long-form storytelling") rather than
// the brief's Founder Failure / Product Demo campaign — that campaign is
// still active and in-progress in lib/campaign.tsx, so it can't also be
// shown here as completed without contradicting Campaigns/Videos/Overview.
export const SEED_INSIGHTS: Insight[] = [
  {
    id: "i1",
    sourceHypothesisId: "h5",
    campaignName: "Short Hook vs Long-Form Story",
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
    followUp: {
      title: "Follow-up: Sharper pain-first hooks",
      statement:
        "A short pain-first hook naming a more specific, concrete pain point will generate more clicks per 1,000 views than this campaign's winning hook.",
      category: "Format",
      primaryMetric: "Clicks / 1K Views",
      rationale:
        "The short hook already beat the long-form opening; narrowing the hook to a more specific pain point tests whether specificity compounds the gain.",
    },
  },
];

export function insightClicksPer1k(v: ComparedVariant): number {
  return clicksPer1k(v.views, v.clicks);
}

export function toHypothesis(insight: Insight): Hypothesis {
  return {
    id: `${insight.id}-followup`,
    title: insight.followUp.title,
    statement: insight.followUp.statement,
    category: insight.followUp.category,
    primaryMetric: insight.followUp.primaryMetric,
    rationale: insight.followUp.rationale,
    status: "generated",
    parentInsightId: insight.id,
  };
}
