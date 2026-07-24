"use client";

/**
 * Adapts API response shapes (snake_case enums) to the frontend
 * Hypothesis type (camelCase, legacy status labels).
 * Used during the transition period while SEED_* data is being retired.
 */
import type { Hypothesis as ApiHypothesis } from "./api-client";
import type { Hypothesis as FrontendHypothesis, Status } from "./hypotheses";

const API_STATUS_MAP: Record<string, Status> = {
  generated: "suggested",
  draft: "draft",
  approved: "approved",
  testing: "testing",
  tested: "learned",
  rejected: "rejected",
};

const FRONTEND_STATUS_MAP: Record<Status, string> = {
  suggested: "generated",
  draft: "draft",
  approved: "approved",
  testing: "testing",
  learned: "tested",
  rejected: "rejected",
};

const METRIC_LABEL_MAP: Record<string, string> = {
  clicks_per_1k_views: "Clicks / 1K Views",
  comments_per_1k_views: "Comments / 1K Views",
  views: "Views",
  product_clicks: "Product Clicks",
  comments: "Comments",
};

const METRIC_API_MAP: Record<string, string> = {
  "Clicks / 1K Views": "clicks_per_1k_views",
  "Comments / 1K Views": "comments_per_1k_views",
  Views: "views",
  "Product Clicks": "product_clicks",
  Comments: "comments",
};

export function apiToFrontend(h: ApiHypothesis): FrontendHypothesis {
  return {
    id: h.id,
    title: h.title,
    statement: h.statement,
    category: h.category ?? "",
    primaryMetric: METRIC_LABEL_MAP[h.primary_metric] ?? h.primary_metric,
    rationale: h.rationale ?? "",
    status: (API_STATUS_MAP[h.status] ?? h.status) as Status,
    researchQuestion: h.research_question ?? undefined,
    independentVariable: h.independent_variable ?? undefined,
    controlCondition: h.control_condition ?? undefined,
    treatmentCondition: h.treatment_condition ?? undefined,
    controlledElements: h.controlled_elements ?? [],
    contradictionCondition: h.contradiction_condition ?? undefined,
    parentInsightId: undefined, // follow-up lineage is Sprint 3+
    relationshipType: (h.relationship_type as FrontendHypothesis["relationshipType"]) ?? undefined,
    previousLearning: h.previous_learning ?? undefined,
    remainingUnknown: h.remaining_unknown ?? undefined,
    _apiId: h.id, // preserve original UUID for API calls
  } as FrontendHypothesis & { _apiId?: string };
}

export function frontendStatusToApi(status: Status): string {
  return FRONTEND_STATUS_MAP[status] ?? status;
}

export function metricToApi(label: string): string {
  return METRIC_API_MAP[label] ?? label;
}

export function metricToLabel(apiValue: string): string {
  return METRIC_LABEL_MAP[apiValue] ?? apiValue;
}
