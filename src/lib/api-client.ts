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
// ── Variant + Video API ───────────────────────────────────────────────────────

export type VideoRecord = {
  id: string;
  variant_id: string;
  attempt_number: number;
  is_current: boolean;
  status: string;
  submitted_url: string | null;
  normalized_tiktok_url: string | null;
  tiktok_video_id: string | null;
  validated_at: string | null;
  tracking_started_at: string | null;
  tracking_window_ends_at: string | null;
  validation_error_code: string | null;
  validation_error_detail: string | null;
  created_at: string;
  updated_at: string;
};

export type ExecutionObservation = {
  id: string;
  video_id: string;
  delivered_variable: boolean | null;
  used_approved_hook: boolean | null;
  used_fixed_cta: boolean | null;
  actual_duration_seconds: number | null;
  actual_product_reveal_seconds: number | null;
  format_changed: boolean | null;
  audience_framing_changed: boolean | null;
  offer_changed: boolean | null;
  publishing_schedule_changed: boolean | null;
  reason: string | null;
  notes: string | null;
  unexpected: string | null;
  perceived_drop_off_at: string | null;
  founder_observed_comment_sentiment: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiVariant = Variant & {
  current_video: VideoRecord | null;
  observation: ExecutionObservation | null;
};

export const variantApi = {
  get: (id: string) => apiFetch<ApiVariant>(`/api/variants/${id}`),
  updateBrief: (id: string, data: Partial<Pick<Variant, "hook" | "hook_delivery_note" | "context" | "on_screen_text">>) =>
    apiFetch<ApiVariant>(`/api/variants/${id}/brief`, { method: "PATCH", body: JSON.stringify(data) }),
  reviseBrief: (id: string, instruction: string) =>
    apiFetch<{ proposed_revision: Partial<Variant>; variant_id: string }>(
      `/api/variants/${id}/revise-brief`,
      { method: "POST", body: JSON.stringify({ instruction }) }
    ),
  approveForRecording: (id: string) =>
    apiFetch<ApiVariant>(`/api/variants/${id}/approve-for-recording`, { method: "POST" }),
  confirmRecorded: (id: string) =>
    apiFetch<ApiVariant>(`/api/variants/${id}/confirm-recorded`, { method: "POST" }),
  createVideo: (id: string) =>
    apiFetch<VideoRecord>(`/api/variants/${id}/videos`, { method: "POST" }),
};

export const videoApi = {
  get: (id: string) => apiFetch<VideoRecord>(`/api/videos/${id}`),
  submitUrl: (id: string, url: string, checks: { video_live: boolean; variable_delivered: boolean; controlled_preserved: boolean }) =>
    apiFetch<VideoRecord>(`/api/videos/${id}/submit-url`, {
      method: "POST",
      body: JSON.stringify({ url, ...checks }),
    }),
  getObservation: (id: string) => apiFetch<ExecutionObservation | null>(`/api/videos/${id}/execution-observation`),
  upsertObservation: (id: string, data: Partial<ExecutionObservation>) =>
    apiFetch<ExecutionObservation>(`/api/videos/${id}/execution-observation`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};
// ── Project API (for TanStack Query hooks) ────────────────────────────────────
export type ProjectResponse = {
  id: string;
  user_id: string;
  product_name: string;
  product_type: string;
  product_description: string;
  product_url: string;
  target_audience: string;
  primary_cta: string;
  tiktok_handle: string;
  tracking_slug: string;
  tracking_url: string;
  destination_url: string;
  context_version: number;
  onboarded_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectUpdateRequest = Partial<
  Pick<ProjectResponse,
    "product_name" | "product_type" | "product_description" | "product_url"
    | "target_audience" | "primary_cta" | "tiktok_handle" | "destination_url"
  >
>;

export const projectApi = {
  getCurrent: () => apiFetch<ProjectResponse>("/api/projects/current"),
  update: (id: string, data: ProjectUpdateRequest) =>
    apiFetch<ProjectResponse>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};
