"use client";

// Minimal Supabase anonymous auth without @supabase/supabase-js.
// Calls the Supabase Auth REST API directly.

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://127.0.0.1:54321";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

const SESSION_KEY = "cl_supabase_session";

export type Session = {
  access_token: string;
  refresh_token: string;
  expires_at: number; // unix timestamp
  user_id: string;
};

function loadSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(s: Session) {
  if (typeof window === "undefined") return;
  localStorage.setItem(SESSION_KEY, JSON.stringify(s));
}

function clearSession() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SESSION_KEY);
}

async function refreshSession(refreshToken: string): Promise<Session | null> {
  try {
    const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: SUPABASE_ANON_KEY,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const session: Session = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600),
      user_id: data.user?.id ?? "",
    };
    saveSession(session);
    return session;
  } catch {
    return null;
  }
}

async function signInAnonymously(): Promise<Session | null> {
  try {
    const res = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: SUPABASE_ANON_KEY,
      },
      body: JSON.stringify({}),
    });
    if (!res.ok) return null;
    const data = await res.json();
    const session: Session = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600),
      user_id: data.user?.id ?? "",
    };
    saveSession(session);
    return session;
  } catch {
    return null;
  }
}

/**
 * Returns a valid session, refreshing or creating one as needed.
 * Call this before every API request that needs authentication.
 */
export async function getValidSession(): Promise<Session | null> {
  const session = loadSession();
  if (!session) return signInAnonymously();

  const nowPlusPadding = Math.floor(Date.now() / 1000) + 60;
  if (session.expires_at < nowPlusPadding) {
    const refreshed = await refreshSession(session.refresh_token);
    if (refreshed) return refreshed;
    clearSession();
    return signInAnonymously();
  }

  return session;
}

export function getStoredSession(): Session | null {
  return loadSession();
}
