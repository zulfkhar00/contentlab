"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type ProjectContext = {
  productName: string;
  productType: string;
  productDescription: string;
  productUrl: string;
  targetAudience: string;
  problemSolved: string;
  whyItMatters: string;
  currentAlternatives: string;
  desiredAction: string;
  primaryCta: string;
  tiktokHandle: string;
  accountPublic: boolean;
  manualPublish: boolean;
  // The slug is generated once, at onboarding, and never changes afterward —
  // only destinationUrl is editable in Settings (brief: the permanent link
  // stays the same when the destination changes).
  trackingSlug: string;
  destinationUrl: string;
};

export const DEFAULT_PROJECT_CONTEXT: ProjectContext = {
  productName: "Content Lab",
  productType: "SaaS",
  productDescription:
    "An experimentation lab that turns one product into testable TikTok hooks.",
  productUrl: "https://contentlab.app",
  targetAudience: "Technical founders struggling with distribution",
  problemSolved: "Founders don't know which message drives product clicks.",
  whyItMatters: "Wasted ad spend and guesswork instead of evidence.",
  currentAlternatives: "Guessing, spreadsheets, generic UGC agencies.",
  desiredAction: "Drive product clicks",
  primaryCta: "Check the link in bio",
  tiktokHandle: "founder_lab",
  accountPublic: true,
  manualPublish: true,
  trackingSlug: "founder-lab",
  destinationUrl: "https://contentlab.app",
};

const STORAGE_KEY = "cl_project_context";

export function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// TODO(api): replace localStorage with a real GET/PATCH against the project
// API once the backend exists (see CONTENT_LAB_PLAN.md phase 2). This keeps
// onboarding input flowing into Settings/Hypotheses/etc. in the meantime.
export function loadProjectContext(): ProjectContext {
  if (typeof window === "undefined") return DEFAULT_PROJECT_CONTEXT;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PROJECT_CONTEXT;
    return { ...DEFAULT_PROJECT_CONTEXT, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_PROJECT_CONTEXT;
  }
}

export function saveProjectContext(ctx: ProjectContext) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ctx));
}

type ProjectContextValue = {
  context: ProjectContext;
  setContext: (next: ProjectContext) => void;
  loaded: boolean;
};

const Ctx = createContext<ProjectContextValue | null>(null);

/**
 * Single source of truth for the project context, shared by every screen
 * under (app) — including the persistent sidebar/topbar shell. Without this
 * provider, the topbar and a page like Settings would each hold independent
 * state and edits wouldn't show up in the topbar until a full page reload.
 */
export function ProjectContextProvider({ children }: { children: ReactNode }) {
  const [context, setContextState] = useState<ProjectContext>(
    DEFAULT_PROJECT_CONTEXT,
  );
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setContextState(loadProjectContext());
    setLoaded(true);
  }, []);

  function setContext(next: ProjectContext) {
    setContextState(next);
    saveProjectContext(next);
  }

  return (
    <Ctx.Provider value={{ context, setContext, loaded }}>
      {children}
    </Ctx.Provider>
  );
}

export function useProjectContext(): ProjectContextValue {
  const value = useContext(Ctx);
  if (!value) {
    throw new Error(
      "useProjectContext must be used within a ProjectContextProvider",
    );
  }
  return value;
}
