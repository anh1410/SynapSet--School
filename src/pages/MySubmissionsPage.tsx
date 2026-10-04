import { useCallback, useEffect, useMemo, useState } from "react";
import { History, Inbox, Pencil, PlusCircle, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QuestionPreview } from "@/components/QuestionPreview";
import { StatusBadge, SubmissionHistory } from "@/components/SubmissionBits";
import {
  QUESTION_TYPE_LABELS,
  deleteSubmission,
  gradeLabel,
  listSubmissions,
  timeAgo,
  type Submission,
  type SubmissionStatus,
} from "@/lib/api";

type Filter = "all" | SubmissionStatus;

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "submitted", label: "Waiting" },
  { id: "changes_requested", label: "Changes requested" },
  { id: "accepted", label: "Accepted" },
  { id: "rejected", label: "Rejected" },
];

function SubmissionCard({
  sub,
  onEdit,
  onDelete,
}: {
  sub: Submission;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [showHistory, setShowHistory] = useState(false);
  const editable = sub.status === "submitted" || sub.status === "changes_requested";
  const needsAction = sub.status === "changes_requested";

  return (
    <Card className={needsAction ? "border-primary/40" : undefined}>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusBadge status={sub.status} />
          <Badge variant="secondary">{QUESTION_TYPE_LABELS[sub.question.question_type]}</Badge>
          <Badge variant="outline">
            {sub.question.marks} mark{sub.question.marks === 1 ? "" : "s"}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {sub.subject_name}
            {sub.subject_grade ? ` · ${gradeLabel(sub.subject_grade)}` : ""}
          </span>
          <span className="ml-auto text-[11px] text-muted-foreground">Updated {timeAgo(sub.updated_at)}</span>
        </div>

        <QuestionPreview question={sub.question} />

        {sub.admin_comment && (sub.status === "changes_requested" || sub.status === "rejected") && (
          <div className="rounded-lg border border-border bg-secondary/40 p-2.5 text-xs">
            <p className="font-medium text-foreground">
              {sub.status === "changes_requested" ? "What your admin wants changed" : "Why it was rejected"}
            </p>
            <p className="mt-0.5 whitespace-pre-wrap text-muted-foreground">{sub.admin_comment}</p>
          </div>
        )}

        {sub.status === "accepted" && (
          <p className="text-xs text-success">It's in the question bank. You earn a credit each time it's used in an exam.</p>
        )}

        {showHistory && <SubmissionHistory history={sub.history} />}

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          {editable && (
            <Button size="sm" variant={needsAction ? "primary" : "outline"} onClick={onEdit}>
              <Pencil className="h-3.5 w-3.5" /> {needsAction ? "Revise & resubmit" : "Edit"}
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setShowHistory((v) => !v)}>
            <History className="h-3.5 w-3.5" /> {showHistory ? "Hide history" : "History"}
          </Button>
          {sub.status !== "accepted" && (
            <Button size="sm" variant="ghost" className="ml-auto text-destructive hover:text-destructive" onClick={onDelete}>
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/** The teacher's own questions and where each one stands with the admin. */
export function MySubmissionsPage({ onNew, onEdit }: { onNew: () => void; onEdit: (sub: Submission) => void }) {
  const [subs, setSubs] = useState<Submission[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(() => {
    listSubmissions()
      .then((s) => {
        setSubs(s);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load your questions."));
  }, []);

  useEffect(load, [load]);

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: 0, submitted: 0, changes_requested: 0, accepted: 0, rejected: 0 };
    for (const s of subs ?? []) {
      c.all++;
      c[s.status]++;
    }
    return c;
  }, [subs]);

  const visible = (subs ?? []).filter((s) => filter === "all" || s.status === filter);

  const handleDelete = async (sub: Submission) => {
    if (!window.confirm("Delete this question? This can't be undone.")) return;
    try {
      await deleteSubmission(sub.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete the question.");
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">My Questions</h1>
          <p className="text-sm text-muted-foreground">Everything you've sent to your admin, and what they decided.</p>
        </div>
        <Button onClick={onNew}>
          <PlusCircle className="h-4 w-4" /> Submit a question
        </Button>
      </div>

      {counts.changes_requested > 0 && (
        <p className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm text-foreground">
          {counts.changes_requested} question{counts.changes_requested === 1 ? " needs" : "s need"} your attention — your admin
          asked for changes.
        </p>
      )}

      {error && <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p>}

      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList className="h-auto flex-wrap">
          {FILTERS.map((f) => (
            <TabsTrigger key={f.id} value={f.id}>
              {f.label}
              <span className="ml-1.5 text-[10px] text-muted-foreground">{counts[f.id]}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {subs === null && !error ? (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={filter === "all" ? "You haven't submitted anything yet" : "Nothing here"}
          description={
            filter === "all"
              ? "Send your first question and it will appear here with its review status."
              : "No questions with this status."
          }
          action={
            filter === "all" ? (
              <Button size="sm" onClick={onNew}>
                <PlusCircle className="h-3.5 w-3.5" /> Submit a question
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {visible.map((s) => (
            <SubmissionCard key={s.id} sub={s} onEdit={() => onEdit(s)} onDelete={() => handleDelete(s)} />
          ))}
        </div>
      )}
    </div>
  );
}
