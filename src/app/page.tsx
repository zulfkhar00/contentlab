import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default async function Home() {
  // TODO(auth): replace the cookie check with the authenticated user's
  // project.onboarding_completed_at once Supabase auth is wired.
  const onboarded = (await cookies()).get("cl_onboarded")?.value === "1";
  redirect(onboarded ? "/overview" : "/onboarding");
}
