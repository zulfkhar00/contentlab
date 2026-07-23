import { AppSidebar } from "@/components/app-sidebar";
import { AppTopbar } from "@/components/app-topbar";
import { ProjectContextProvider } from "@/lib/project-context";
import { CampaignProvider } from "@/lib/campaign";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProjectContextProvider>
      <CampaignProvider>
        <div className="min-h-screen bg-background">
          <AppSidebar />
          <div className="ml-60 flex min-h-screen flex-col">
            <AppTopbar />
            <main className="mx-auto mt-14 flex w-full max-w-[1200px] flex-1 flex-col gap-6 p-6 lg:p-8">
              {children}
            </main>
          </div>
        </div>
      </CampaignProvider>
    </ProjectContextProvider>
  );
}
