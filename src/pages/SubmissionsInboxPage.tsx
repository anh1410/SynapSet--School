import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, History, Inbox, MessageSquareWarning, Search, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QuestionPreview } from "@/components/QuestionPreview";
import { StatusBadge, SubmissionHistory } from "@/components/SubmissionBits";
import { useAuth } from "@/lib/AuthContext";
import {
  GRADES,
  QUESTION_TYPE_LABELS,
  QUESTION_TYPE_ORDER,
  gradeLabel,
  listSubmissions,
  listTeachers,
  reviewSubmission,
  submissionSummary,
  subjectLabel,
  timeAgo,
  type AdminTeacher,
  type QuestionType,
  type Submission,
  type SubmissionFilters,
  type SubmissionStatus,
  type SubmissionSummary,
} from "@/lib/api";

const TABS: { id: SubmissionStatus; label: string }[] = [
  { id: "submitted", label: "To review" },
  { id: "changes_requested", label: "Sent back" },
  { id: "accepted", label: "Accepted" },
  { id: "rejected", label: "Rejected" },
];

const textareaClass =
  "flex w-full rounded-lg border border-input bg-white px-3 py-2 text-sm shadow-subtle placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-primary";

type Mode = "changes" | "reject" | null;

function ReviewCard({
  sub,
  selected,
  onSelect,
  onReview,
}: {
  sub: Submission;
  selected: boolean;
  onSelect: (on: boolean) => void;
  onReview: (decision: "accept" | "reject" | "request_changes", comment?: string) => Promise<void>;
}) {
  const [mode, setMode] = useState<Mode>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const pending = sub.status === "submitted";

  const run = async (decision: "accept" | "reject" | "request_changes", note?: string) => {
    setBusy(true);
    setError(null);
    try {
      await onReview(decision, note);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't go through. Please try again.");
      setBusy(false);
    }
  };

  const copies = sub.duplicate_hits;

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-1.5">
          {pending && <Checkbox checked={selected} onCheckedChange={onSelect} className="mr-1" />}
          <StatusBadge status={sub.status} />
          <Badge variant="secondary">{QUESTION_TYPE_LABELS[sub.question.question_type]}</Badge>
          <Badge variant="outline">
            {sub.question.marks} mark{sub.question.marks === 1 ? "" : "s"}
          </Badge>
          {sub.revision > 1 && <Badge variant="accent">Revision {sub.revision}</Badge>}
          <span className="text-xs text-muted-foreground">
            {sub.subject_name}
            {sub.subject_grade ? ` · ${gradeLabel(sub.subject_grade)}` : ""}
          </span>
          <span className="ml-auto text-[11px] text-muted-foreground">
            by <span className="font-medium text-foreground">{sub.teacher_name}</span> · {timeAgo(sub.updated_at)}
          </span>
        </div>

        {copies.length > 0 && (
          <div className="rounded-lg border border-warning/30 bg-warning/10 p-2.5 text-xs">
            <p className="flex items-center gap-1.5 font-medium text-foreground">
              <AlertTriangle className="h-3.5 w-3.5 text-warning" />
              Looks similar to {copies.length === 1 ? "a question" : `${copies.length} questions`} you already have
            </p>
            <ul className="mt-1.5 space-y-1">
              {copies.map((h) => (
                <li key={h.question_id} className="flex items-start gap-2 text-muted-foreground">
                  <Badge variant={h.where === "bank" ? "default" : "secondary"} className="shrink-0">
                    {h.where === "bank" ? "In the bank" : "Also waiting"} · {Math.round(h.similarity * 100)}%
                  </Badge>
                  <span className="line-clamp-2">{h.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <QuestionPreview question={sub.question} />

        {sub.admin_comment && !pending && (
          <p className="rounded-lg bg-secondary/40 p-2.5 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Your note: </span>
            {sub.admin_comment}
          </p>
        )}

        {showHistory && <SubmissionHistory history={sub.history} />}

        {mode && (
          <div className="space-y-2 rounded-lg border border-border bg-secondary/30 p-3">
            <label className="block text-xs font-medium text-foreground">
              {mode === "changes" ? "What should the teacher change?" : "Reason (optional, the teacher will see it)"}
            </label>
            <textarea
              className={textareaClass}
              rows={2}
              value={comment}
              autoFocus
              onChange={(e) => setComment(e.target.value)}
              placeholder={mode === "changes" ? "e.g. Option C is also correct — please fix." : "e.g. Not in this term's syllabus."}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={mode === "reject" ? "destructive" : "primary"}
                disabled={busy || (mode === "changes" && !comment.trim())}
                onClick={() => run(mode === "changes" ? "request_changes" : "reject", comment)}
              >
                {mode === "changes" ? "Send back" : "Reject question"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => {
                  setMode(null);
                  setComment("");
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          {pending && !mode && (
            <>
              <Button size="sm" disabled={busy} onClick={() => run("accept")}>
                <Check className="h-3.5 w-3.5" /> Accept into bank
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => setMode("changes")}>
                <MessageSquareWarning className="h-3.5 w-3.5" /> Request changes
              </Button>
              <Button size="sm" variant="ghost" disabled={busy} className="text-destructive hover:text-destructive" onClick={() => setMode("reject")}>
                <X className="h-3.5 w-3.5" /> Reject
              </Button>
            </>
          )}
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setShowHistory((v) => !v)}>
            <History className="h-3.5 w-3.5" /> {showHistory ? "Hide history" : "History"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/** The admin's inbox: every teacher's submissions, organised by status with filters,
 *  similarity warnings, and accept / request-changes / reject. */
export function SubmissionsInboxPage({ onChanged }: { onChanged: () => void }) {
  const { subjects } = useAuth();
  const [status, setStatus] = useState<SubmissionStatus>("submitted");
  const [grade, setGrade] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [type, setType] = useState<QuestionType | "">("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [subs, setSubs] = useState<Submission[] | null>(null);
  const [summary, setSummary] = useState<SubmissionSummary | null>(null);
  const [teachers, setTeachers] = useState<AdminTeacher[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 250);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    listTeachers()
      .then(setTeachers)
      .catch(() => setTeachers([]));
  }, []);

  const filters: SubmissionFilters = useMemo(
    () => ({
      status,
      grade: grade || undefined,
      subject_id: subjectId || undefined,
      teacher_id: teacherId || undefined,
      question_type: type || undefined,
      q: debounced || undefined,
    }),
    [status, grade, subjectId, teacherId, type, debounced]
  );

  const load = useCallback(() => {
    Promise.all([listSubmissions(filters), submissionSummary()])
      .then(([list, sum]) => {
        setSubs(list);
        setSummary(sum);
        setError(null);
        setSelected((prev) => new Set(list.filter((s) => prev.has(s.id) && s.status === "submitted").map((s) => s.id)));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load submissions."));
  }, [filters]);

  useEffect(() => {
    setSubs(null);
    load();
  }, [load]);

  const afterReview = () => {
    load();
    onChanged();
  };

  const subjectOptions = subjects.filter((s) => !grade || s.grade === grade);
  const hasFilters = !!(grade || subjectId || teacherId || type || search);

  const acceptSelected = async () => {
    setBulkBusy(true);
    setError(null);
    const failed: string[] = [];
    for (const id of selected) {
      try {
        await reviewSubmission(id, "accept");
      } catch (err) {
        failed.push(err instanceof Error ? err.message : "failed");
      }
    }
    setBulkBusy(false);
    if (failed.length) setError(`${failed.length} of ${selected.size} couldn't be accepted: ${failed[0]}`);
    setSelected(new Set());
    afterReview();
  };

  const toggle = (id: string, on: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  const pendingIds = (subs ?? []).filter((s) => s.status === "submitted").map((s) => s.id);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Teacher Submissions</h1>
        <p className="text-sm text-muted-foreground">
          Questions your teachers sent in. Accepted ones join the Question Bank and credit their author when used in an exam.
        </p>
      </div>

      <Tabs value={status} onValueChange={(v) => setStatus(v as SubmissionStatus)}>
        <TabsList className="h-auto flex-wrap">
          {TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
              {summary && (
                <span
                  className={`ml-1.5 rounded-full px-1.5 text-[10px] ${
                    t.id === "submitted" && summary.submitted > 0 ? "bg-primary text-primary-foreground" : "text-muted-foreground"
                  }`}
                >
                  {summary[t.id]}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <div className="relative lg:col-span-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="Search text…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Select
          value={grade}
          onChange={(e) => {
            setGrade(e.target.value);
            setSubjectId("");
          }}
        >
          <option value="">All grades</option>
          {GRADES.map((g) => (
            <option key={g} value={g}>
              {gradeLabel(g)}
            </option>
          ))}
        </Select>
        <Select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
          <option value="">All subjects</option>
          {subjectOptions.map((s) => (
            <option key={s.id} value={s.id}>
              {subjectLabel(s)}
            </option>
          ))}
        </Select>
        <Select value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
          <option value="">All teachers</option>
          {teachers
            .filter((t) => t.role === "teacher")
            .map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
        </Select>
        <Select value={type} onChange={(e) => setType(e.target.value as QuestionType | "")}>
          <option value="">All types</option>
          {QUESTION_TYPE_ORDER.map((t) => (
            <option key={t} value={t}>
              {QUESTION_TYPE_LABELS[t]}
            </option>
          ))}
        </Select>
      </div>
      {hasFilters && (
        <button
          className="text-xs text-primary hover:underline"
          onClick={() => {
            setGrade("");
            setSubjectId("");
            setTeacherId("");
            setType("");
            setSearch("");
          }}
        >
          Clear filters
        </button>
      )}

      {error && <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p>}

      {status === "submitted" && pendingIds.length > 1 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-white px-3 py-2">
          <Checkbox
            checked={selected.size === pendingIds.length}
            onCheckedChange={(on) => setSelected(on ? new Set(pendingIds) : new Set())}
          />
          <span className="text-xs text-muted-foreground">
            {selected.size === 0 ? "Select all" : `${selected.size} selected`}
          </span>
          {selected.size > 0 && (
            <Button size="sm" disabled={bulkBusy} onClick={acceptSelected}>
              <Check className="h-3.5 w-3.5" /> {bulkBusy ? "Accepting…" : `Accept ${selected.size} selected`}
            </Button>
          )}
        </div>
      )}

      {subs === null && !error ? (
        <div className="space-y-3">
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
        </div>
      ) : (subs ?? []).length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={hasFilters ? "No submissions match these filters" : status === "submitted" ? "All caught up" : "Nothing here"}
          description={
            hasFilters
              ? "Try clearing a filter."
              : status === "submitted"
                ? "No questions are waiting for your review."
                : "No questions with this status yet."
          }
        />
      ) : (
        <div className="space-y-3">
          {(subs ?? []).map((s) => (
            <ReviewCard
              key={s.id}
              sub={s}
              selected={selected.has(s.id)}
              onSelect={(on) => toggle(s.id, on)}
              onReview={async (decision, comment) => {
                await reviewSubmission(s.id, decision, comment);
                afterReview();
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
