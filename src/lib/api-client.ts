"use client";

// Typed fetch wrapper for the Content Lab FastAPI backend.
// Automatically attaches the Supabase JWT to every request.

import { getValidSession } from "./supabase-auth";

const API_BASE = "";  // same origin via Next.js rewrite to FastAPI

type ApiError = {
  detail: string;
  status: number;
};

class ContentLabApiError extends Error {
  status: number;
  constructor(detail: string, status: number) {
    super(detail);
    this.status = status;
  }
}

async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const session = await getValidSession();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init.headers ?? {}),
    ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json() as ApiError;
      detail = body.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new ContentLabApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Hypothesis API ────────────────────────────────────────────────────────────

export type HypothesisStatus =
  | "generated" | "draft" | "approved" | "testing" | "tested" | "rejected";

export type Hypothesis = {
  id: string;
  project_id: string;
  title: string;
  statement: string;
  research_question: string | null;
  independent_variable: string | null;
  control_condition: string | null;
  treatment_condition: string | null;
  controlled_elements: string[];
  contradiction_condition: string | null;
  primary_metric: string;
  rationale: string | null;
  category: string | null;
  status: HypothesisStatus;
  parent_hypothesis_id: string | null;
  source_candidate_id: string | null;
  relationship_type: string | null;
  previous_learning: string | null;
  remaining_unknown: string | null;
  recommendation_reason: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  rejected_at: string | null;
  tested_at: string | null;
};

export type HypothesisPatch = Partial<
  Pick<Hypothesis,
    "title" | "statement" | "research_question" | "independent_variable"
    | "control_condition" | "treatment_condition" | "controlled_elements"
    | "contradiction_condition" | "primary_metric" | "rationale" | "category"
  >
>;

export const hypothesisApi = {
  generate: () =>
    apiFetch<Hypothesis[]>("/api/hypotheses/generate", { method: "POST" }),
  list: (params?: { status?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.status && params.status !== "all") q.set("status", params.status);
    if (params?.search) q.set("search", params.search);
    const qs = q.toString();
    return apiFetch<Hypothesis[]>(`/api/hypotheses${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => apiFetch<Hypothesis>(`/api/hypotheses/${id}`),
  patch: (id: string, data: HypothesisPatch) =>
    apiFetch<Hypothesis>(`/api/hypotheses/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  reject: (id: string) =>
    apiFetch<Hypothesis>(`/api/hypotheses/${id}/reject`, { method: "POST" }),
  approveAndGenerate: (id: string, design: HypothesisPatch) =>
    apiFetch<Experiment>(`/api/hypotheses/${id}/approve-and-generate-experiment`, {
      method: "POST",
      body: JSON.stringify(design),
    }),
};

// ── Experiment API ────────────────────────────────────────────────────────────

export type Variant = {
  id: string;
  project_id: string;
  experiment_id: string;
  position: "A" | "B" | "C";
  treatment_role: "control" | "hypothesis_treatment" | "alternative_treatment";
  title: string;
  variable_value: string;
  hook: string;
  hook_delivery_note: string | null;
  context: string | null;
  on_screen_text: string | null;
  script_sections: Record<string, unknown>;
  recording_guidance: Record<string, unknown>;
  status: string;
  approved_for_recording_at: string | null;
  recorded_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Experiment = {
  id: string;
  project_id: string;
  hypothesis_id: string;
  name: string;
  tracking_window_hours: number;
  status: string;
  hypothesis_design_snapshot: Record<string, unknown>;
  shared_constraints: Record<string, unknown>;
  design_schema_version: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  tracking_completed_at: string | null;
  analysis_started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  variants: Variant[];
};

export const experimentApi = {
  getActive: () => apiFetch<Experiment>("/api/experiments/active"),
  get: (id: string) => apiFetch<Experiment>(`/api/experiments/${id}`),
};

export { ContentLabApiError };
// ── Insight API ───────────────────────────────────────────────────────────────

export type EvidenceItem = {
  variant_id: string;
  position: string;
  treatment_role: string;
  title: string;
  views_delta: number;
  likes_delta: number;
  comments_delta: number;
  attributed_unique_clicks: number;
  unique_clicks_per_1k: number;
};

export type Candidate = {
  id: string;
  insight_id: string;
  slot: string;
  relationship_type: string;
  statement: string;
  why_this_follows: string | null;
  recommended: boolean;
  recommendation_reason: string | null;
  previous_learning: string | null;
  remaining_unknown: string | null;
  status: string;
  created_at: string;
};

export type InsightSummary = {
  id: string;
  experiment_id: string;
  outcome_type: string | null;
  outcome_description: string | null;
  supported_learning: string | null;
  research_question: string | null;
  hypothesis_text: string | null;
  primary_metric: string | null;
  generated_at: string;
};

export type InsightDetail = InsightSummary & {
  evidence_snapshot_id: string;
  evidence_basis: Record<string, unknown>;
  do_not_infer_yet: string[];
  recommended_next_test: string | null;
  limitations: string[];
  candidates: Candidate[];
  evidence_items: EvidenceItem[];
};

export const insightApi = {
  list: () => apiFetch<InsightSummary[]>("/api/insights"),
  get: (id: string) => apiFetch<InsightDetail>(`/api/insights/${id}`),
  acceptCandidate: (id: string) =>
    apiFetch<Hypothesis>(`/api/follow-up-candidates/${id}/accept`, { method: "POST" }),
  dismissCandidate: (id: string) =>
    apiFetch<Candidate>(`/api/follow-up-candidates/${id}/dismiss`, { method: "POST" }),
};
