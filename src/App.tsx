import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { OverviewPage } from "@/pages/OverviewPage";
import { UploadPage } from "@/pages/UploadPage";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { BankPage } from "@/pages/BankPage";
import { BuilderPage } from "@/pages/BuilderPage";
import { TemplatesPage } from "@/pages/TemplatesPage";
import { ReviewExportPage } from "@/pages/ReviewExportPage";
import { AuthPage } from "@/pages/AuthPage";
import { SubjectsPage } from "@/pages/SubjectsPage";
import { TeachersPage } from "@/pages/TeachersPage";
import { MySubjectsPage } from "@/pages/MySubjectsPage";
import { MySubmissionsPage } from "@/pages/MySubmissionsPage";
import { ActivityLogPage } from "@/pages/ActivityLogPage";
import { MyCreditsPage } from "@/pages/MyCreditsPage";
import { SubmitQuestionPage } from "@/pages/SubmitQuestionPage";
import { SubmissionsInboxPage } from "@/pages/SubmissionsInboxPage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/lib/AuthContext";
import { ApiError, GRADES, gradeLabel, submissionSummary, type Submission } from "@/lib/api";
import { GraduationCap } from "lucide-react";

export type Page =
  | "overview"
  | "upload"
  | "analysis"
  | "bank"
  | "builder"
  | "templates"
  | "review"
  | "subjects"
  | "teachers"
  | "submissions"
  | "activity"
  | "mySubjects"
  | "mySubmissions"
  | "myCredits"
  | "submitQuestion";

function FirstSubjectGate() {
  const { createSubject } = useAuth();
  const [name, setName] = useState("");
  const [grade, setGrade] = useState<string>("1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await createSubject(trimmed, grade);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the subject. Please try again.");
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
            Subjects keep uploaded notes, topics, and questions separate, one per grade — e.g. "Science" for Grade 6.
          </p>
        </div>
        <form className="space-y-3" onSubmit={handleCreate}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Subject name" required />
          <Select value={grade} onChange={(e) => setGrade(e.target.value)}>
            {GRADES.map((g) => (
              <option key={g} value={g}>
                {gradeLabel(g)}
              </option>
            ))}
          </Select>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Creating…" : "Create subject"}
          </Button>
        </form>
      </div>
    </div>
  );
}

function AdminShell() {
  const [page, setPage] = useState<Page>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeBlueprintId, setActiveBlueprintId] = useState<string | null>(null);
  const [bankSearch, setBankSearch] = useState<string | undefined>(undefined);
  const [pendingTemplateId, setPendingTemplateId] = useState<string | null>(null);
  const [pendingReviews, setPendingReviews] = useState(0);

  const refreshPending = useCallback(() => {
    submissionSummary()
      .then((s) => setPendingReviews(s.submitted))
      .catch(() => {});
  }, []);

  useEffect(refreshPending, [refreshPending]);

  const goToReview = (blueprintId: string) => {
    setActiveBlueprintId(blueprintId);
    setPage("review");
  };

  const goToBankSearch = (query: string) => {
    setBankSearch(query);
    setPage("bank");
  };

  const useTemplate = (templateId: string) => {
    setPendingTemplateId(templateId);
    setPage("builder");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-secondary/40">
      <Sidebar
        active={page}
        onNavigate={setPage}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        badges={{ submissions: pendingReviews }}
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
            {page === "builder" && (
              <BuilderPage
                onSaved={goToReview}
                applyTemplateId={pendingTemplateId}
                onTemplateApplied={() => setPendingTemplateId(null)}
              />
            )}
            {page === "templates" && <TemplatesPage onUseTemplate={useTemplate} />}
            {page === "review" && (
              <ReviewExportPage blueprintId={activeBlueprintId} onNavigate={setPage} onSelectBlueprint={goToReview} />
            )}
            {page === "subjects" && <SubjectsPage />}
            {page === "teachers" && <TeachersPage />}
            {page === "activity" && <ActivityLogPage />}
            {page === "submissions" && <SubmissionsInboxPage onChanged={refreshPending} />}
          </div>
        </main>
      </div>
    </div>
  );
}

/** What a teacher gets: their assigned subjects, nothing from the admin toolset
 *  (no uploads, generation, bank, builder). The server enforces this too. */
function TeacherShell() {
  const [page, setPage] = useState<Page>("mySubjects");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [editing, setEditing] = useState<Submission | null>(null);
  const [attention, setAttention] = useState(0);

  const refreshAttention = useCallback(() => {
    submissionSummary()
      .then((s) => setAttention(s.changes_requested))
      .catch(() => {});
  }, []);

  useEffect(refreshAttention, [refreshAttention, page]);

  const startNew = () => {
    setEditing(null);
    setPage("submitQuestion");
  };
  const startEdit = (sub: Submission) => {
    setEditing(sub);
    setPage("submitQuestion");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-secondary/40">
      <Sidebar
        active={page}
        onNavigate={(p) => (p === "submitQuestion" ? startNew() : setPage(p))}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        badges={{ mySubmissions: attention }}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar page={page} onMenuClick={() => setSidebarOpen(true)} onNavigate={setPage} onSelectQuestion={() => {}} />

        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
            {page === "mySubjects" && <MySubjectsPage onSubmit={startNew} />}
            {page === "myCredits" && <MyCreditsPage />}
            {page === "mySubmissions" && <MySubmissionsPage onNew={startNew} onEdit={startEdit} />}
            {page === "submitQuestion" && (
              <SubmitQuestionPage
                key={editing?.id ?? "new"}
                editing={editing}
                onDone={() => {
                  setEditing(null);
                  setPage("mySubmissions");
                }}
                onCancel={() => {
                  setEditing(null);
                  setPage(editing ? "mySubmissions" : "mySubjects");
                }}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const { ready, teacher, isAdmin, subjects } = useAuth();

  if (!ready) {
    return <div className="flex min-h-screen items-center justify-center bg-secondary/40" />;
  }
  if (!teacher) {
    return <AuthPage />;
  }
  if (!isAdmin) {
    return <TeacherShell />;
  }
  if (subjects.length === 0) {
    return <FirstSubjectGate />;
  }
  return <AdminShell />;
}
