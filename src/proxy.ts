import { NextResponse, type NextRequest } from "next/server";

// App routes that require a completed onboarding before they can be viewed.
const APP_PREFIXES = [
  "/overview",
  "/hypotheses",
  "/campaigns",
  "/videos",
  "/insights",
  "/settings",
];

export function proxy(request: NextRequest) {
  // TODO(auth): once Supabase auth exists, also require a session here and
  // derive "onboarded" from the user's project record instead of a cookie.
  const onboarded = request.cookies.get("cl_onboarded")?.value === "1";
  const { pathname } = request.nextUrl;

  const inApp = APP_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );

  if (inApp && !onboarded) {
    const url = request.nextUrl.clone();
    url.pathname = "/onboarding";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
