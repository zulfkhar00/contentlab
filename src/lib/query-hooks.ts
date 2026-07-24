"use client";
/**
 * Typed query + mutation hooks for all Content Lab entities.
 * Uses TanStack Query for caching, deduplication, and background refresh.
 * Error states: 401 → auth error, 404 → not found, 429 → rate limit, 5xx → provider error.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import {
  experimentApi,
  hypothesisApi,
  insightApi,
  variantApi,
  videoApi,
  type ApiVariant,
  type Candidate,
  type Experiment,
  type Hypothesis,
  type HypothesisPatch,
  type InsightDetail,
  type InsightSummary,
  type VideoRecord,
  type ExecutionObservation,
} from "./api-client";
import {
  type ProjectResponse,
  type ProjectUpdateRequest,
} from "./api-client";

// ── Query keys ────────────────────────────────────────────────────────────────

export const qk = {
  project: ["project", "current"] as const,
  hypotheses: (projectId?: string, status?: string) =>
    ["hypotheses", projectId, status] as const,
  hypothesis: (id: string) => ["hypothesis", id] as const,
  activeExperiment: (projectId?: string) =>
    ["active-experiment", projectId] as const,
  experiment: (id: string) => ["experiment", id] as const,
  variant: (id: string) => ["variant", id] as const,
  video: (id: string) => ["video", id] as const,
  observation: (videoId: string) => ["observation", videoId] as const,
  insights: (projectId?: string) => ["insights", projectId] as const,
  insight: (id: string) => ["insight", id] as const,
};

// ── Error helper ──────────────────────────────────────────────────────────────

type AppError = { status: number; detail: string };

function isRateLimit(err: unknown): boolean {
  return (err as AppError)?.status === 429;
}
function isProviderError(err: unknown): boolean {
  const s = (err as AppError)?.status;
  return s !== undefined && s >= 500;
}

// ── Project ───────────────────────────────────────────────────────────────────

export function useCurrentProject() {
  return useQuery({
    queryKey: qk.project,
    queryFn: () => import("./api-client").then(m => m.projectApi?.getCurrent?.() ?? Promise.reject("no project api")),
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProjectUpdateRequest }) =>
      import("./api-client").then(m => m.projectApi?.update(id, data) ?? Promise.reject()),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.project }),
  });
}

// ── Hypotheses ────────────────────────────────────────────────────────────────

export function useHypothesesQuery(status?: string) {
  return useQuery({
    queryKey: qk.hypotheses(undefined, status),
    queryFn: () => hypothesisApi.list(status ? { status } : undefined),
  });
}

export function useHypothesisQuery(id: string) {
  return useQuery({
    queryKey: qk.hypothesis(id),
    queryFn: () => hypothesisApi.get(id),
    enabled: !!id,
  });
}

export function useGenerateHypotheses() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => hypothesisApi.generate(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hypotheses"] }),
  });
}

export function usePatchHypothesis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: HypothesisPatch }) =>
      hypothesisApi.patch(id, data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: qk.hypothesis(id) });
      qc.invalidateQueries({ queryKey: ["hypotheses"] });
    },
  });
}

export function useRejectHypothesis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => hypothesisApi.reject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hypotheses"] }),
  });
}

export function useApproveAndGenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, design }: { id: string; design: HypothesisPatch }) =>
      hypothesisApi.approveAndGenerate(id, design),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hypotheses"] });
      qc.invalidateQueries({ queryKey: ["active-experiment"] });
    },
  });
}

// ── Experiment ────────────────────────────────────────────────────────────────

export function useActiveExperiment() {
  return useQuery({
    queryKey: qk.activeExperiment(),
    queryFn: () => experimentApi.getActive(),
    retry: (count, err) => (err as unknown as AppError)?.status === 404 ? false : count < 2,
  });
}

export function useExperimentQuery(id: string) {
  return useQuery({
    queryKey: qk.experiment(id),
    queryFn: () => experimentApi.get(id),
    enabled: !!id,
  });
}

// ── Variant ───────────────────────────────────────────────────────────────────

export function useVariantQuery(id: string) {
  return useQuery({
    queryKey: qk.variant(id),
    queryFn: () => variantApi.get(id),
    enabled: !!id,
  });
}

export function useUpdateBrief() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof variantApi.updateBrief>[1] }) =>
      variantApi.updateBrief(id, data),
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: qk.variant(id) }),
  });
}

export function useReviseBrief() {
  return useMutation({
    mutationFn: ({ id, instruction }: { id: string; instruction: string }) =>
      variantApi.reviseBrief(id, instruction),
  });
}

export function useApproveForRecording() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => variantApi.approveForRecording(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: qk.variant(id) });
      qc.invalidateQueries({ queryKey: ["active-experiment"] });
    },
  });
}

export function useConfirmRecorded() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => variantApi.confirmRecorded(id),
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: qk.variant(id) }),
  });
}

export function useCreateVideo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (variantId: string) => variantApi.createVideo(variantId),
    onSuccess: (_, variantId) => qc.invalidateQueries({ queryKey: qk.variant(variantId) }),
  });
}

// ── Video ─────────────────────────────────────────────────────────────────────

export function useVideoQuery(id: string) {
  return useQuery({
    queryKey: qk.video(id),
    queryFn: () => videoApi.get(id),
    enabled: !!id,
  });
}

export function useSubmitUrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id, url, checks,
    }: { id: string; url: string; checks: Parameters<typeof videoApi.submitUrl>[2] }) =>
      videoApi.submitUrl(id, url, checks),
    onSuccess: (video) => {
      qc.invalidateQueries({ queryKey: qk.video(video.id) });
      qc.invalidateQueries({ queryKey: ["active-experiment"] });
    },
  });
}

export function useObservationQuery(videoId: string) {
  return useQuery({
    queryKey: qk.observation(videoId),
    queryFn: () => videoApi.getObservation(videoId),
    enabled: !!videoId,
  });
}

export function useUpsertObservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ExecutionObservation> }) =>
      videoApi.upsertObservation(id, data),
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: qk.observation(id) }),
  });
}

// ── Insights ──────────────────────────────────────────────────────────────────

export function useInsightsQuery() {
  return useQuery({
    queryKey: qk.insights(),
    queryFn: () => insightApi.list(),
  });
}

export function useInsightQuery(id: string) {
  return useQuery({
    queryKey: qk.insight(id),
    queryFn: () => insightApi.get(id),
    enabled: !!id,
  });
}

export function useAcceptCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => insightApi.acceptCandidate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hypotheses"] });
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
  });
}

export function useDismissCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => insightApi.dismissCandidate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["insights"] }),
  });
}

// ── Error state helpers ───────────────────────────────────────────────────────

export function getErrorMessage(err: unknown): string {
  if (!err) return "";
  const status = (err as unknown as AppError)?.status;
  const detail = (err as AppError)?.detail;
  if (status === 401) return "Session expired. Please refresh the page.";
  if (status === 429) return "Too many requests. Please wait a moment.";
  if (status && status >= 500) return "The AI provider encountered an error. Please try again.";
  if (detail) return detail;
  return "An unexpected error occurred.";
}
