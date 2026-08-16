import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { OverviewPage } from "@/pages/OverviewPage";
import { UploadPage } from "@/pages/UploadPage";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { BankPage } from "@/pages/BankPage";
import { BuilderPage } from "@/pages/BuilderPage";
import { ReviewExportPage } from "@/pages/ReviewExportPage";
import { AuthPage } from "@/pages/AuthPage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/AuthContext";
import { GraduationCap } from "lucide-react";

export type Page =
  | "overview"
  | "upload"
  | "analysis"
  | "bank"
  | "builder"
  | "review";

function FirstSubjectGate() {
  const { createSubject } = useAuth();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await createSubject(trimmed);
    } catch {
      setError("Couldn't create the subject. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary/40 px-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-white p-6 shadow-card">
        <div className="mb-4 flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <GraduationCap className="h-6 w-6" />
          </div>
          <h1 className="text-base font-semibold text-foreground">Create your first subject</h1>
          <p className="text-xs text-muted-foreground">
            Subjects keep your uploaded notes, topics, and questions separate — e.g. "Science - Grade 6".
          </p>
        </div>
        <form className="space-y-3" onSubmit={handleCreate}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Subject name" required />
          {error && <p className="text-xs text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Creating…" : "Create subject"}
          </Button>
        </form>
      </div>
    </div>
  );
}

function AppShell() {
  const [page, setPage] = useState<Page>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeBlueprintId, setActiveBlueprintId] = useState<string | null>(null);
  const [bankSearch, setBankSearch] = useState<string | undefined>(undefined);

  const goToReview = (blueprintId: string) => {
    setActiveBlueprintId(blueprintId);
    setPage("review");
  };

  const goToBankSearch = (query: string) => {
    setBankSearch(query);
    setPage("bank");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-secondary/40">
      <Sidebar
        active={page}
        onNavigate={setPage}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          page={page}
          onMenuClick={() => setSidebarOpen(true)}
          onNavigate={setPage}
          onSelectQuestion={goToBankSearch}
        />

        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
            {page === "overview" && <OverviewPage onNavigate={setPage} />}
            {page === "upload" && <UploadPage />}
            {page === "analysis" && <AnalysisPage />}
            {page === "bank" && <BankPage initialSearch={bankSearch} onPaperCreated={goToReview} />}
            {page === "builder" && <BuilderPage onSaved={goToReview} />}
            {page === "review" && (
              <ReviewExportPage blueprintId={activeBlueprintId} onNavigate={setPage} onSelectBlueprint={goToReview} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const { ready, teacher, subjects } = useAuth();

  if (!ready) {
    return <div className="flex min-h-screen items-center justify-center bg-secondary/40" />;
  }
  if (!teacher) {
    return <AuthPage />;
  }
  if (subjects.length === 0) {
    return <FirstSubjectGate />;
  }
  return <AppShell />;
}
