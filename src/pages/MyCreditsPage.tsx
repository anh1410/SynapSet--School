import { useEffect, useMemo, useState } from "react";
import { Award, FileCheck2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { LatexText } from "@/components/LatexText";
import { QUESTION_TYPE_LABELS, gradeLabel, listCredits, type Credit } from "@/lib/api";

/** One credit per question of yours that made it into an exported exam paper.
 *  Shows which question and the exam's name; the paper itself stays private. */
export function MyCreditsPage() {
  const [credits, setCredits] = useState<Credit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCredits()
      .then((r) => setCredits(r.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load your credits."));
  }, []);

  // One card per exam, newest first. A paper's id isn't exposed to teachers, so exams
  // are grouped by name + subject, which is how they read to the teacher anyway.
  const exams = useMemo(() => {
    const byExam = new Map<string, { name: string; subject: string; grade: string | null; items: Credit[] }>();
    for (const c of credits ?? []) {
      const key = `${c.exam_name}\u0000${c.subject_name}\u0000${c.subject_grade ?? ""}`;
      const group = byExam.get(key) ?? { name: c.exam_name, subject: c.subject_name, grade: c.subject_grade, items: [] };
      group.items.push(c);
      byExam.set(key, group);
    }
    return [...byExam.values()];
  }, [credits]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">My Credits</h1>
          <p className="text-sm text-muted-foreground">
            You earn one credit each time a question of yours is used in an exam paper, once that paper is exported.
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-border bg-white px-4 py-2.5 shadow-subtle">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-success/10 text-success">
            <Award className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xl font-semibold leading-none text-foreground">{credits?.length ?? "–"}</p>
            <p className="text-[11px] text-muted-foreground">credit{credits?.length === 1 ? "" : "s"} earned</p>
          </div>
        </div>
      </div>

      {error && <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p>}

      {credits === null && !error ? (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : exams.length === 0 && !error ? (
        <EmptyState
          icon={Award}
          title="No credits yet"
          description="When your admin uses one of your accepted questions in an exam paper and exports it, it will show up here."
          className="mx-auto max-w-lg"
        />
      ) : (
        <div className="space-y-3">
          {exams.map((exam) => (
            <Card key={`${exam.name}-${exam.subject}-${exam.grade}`}>
              <CardHeader className="pb-2">
                <div className="flex flex-wrap items-center gap-2">
                  <FileCheck2 className="h-4 w-4 text-primary" />
                  <CardTitle>{exam.name}</CardTitle>
                  <span className="text-xs text-muted-foreground">
                    {exam.subject}
                    {exam.grade ? ` · ${gradeLabel(exam.grade)}` : ""}
                  </span>
                  <Badge variant="success" className="ml-auto">
                    {exam.items.length} credit{exam.items.length === 1 ? "" : "s"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {exam.items.map((c) => (
                  <div key={c.id} className="rounded-lg border border-border bg-secondary/30 p-3">
                    <p className="text-sm text-foreground">
                      <LatexText text={c.question_text} />
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge variant="secondary">{QUESTION_TYPE_LABELS[c.question_type]}</Badge>
                      <Badge variant="outline">
                        {c.marks} mark{c.marks === 1 ? "" : "s"}
                      </Badge>
                      <span className="text-[11px] text-muted-foreground">
                        Credited {new Date(c.earned_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
