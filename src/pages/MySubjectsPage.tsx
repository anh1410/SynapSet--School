import { BookOpen, PlusCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/lib/AuthContext";
import { gradeLabel, groupSubjectsByGrade } from "@/lib/api";

/** What a teacher sees: only the subjects an admin has assigned to them. They
 *  can't add, pick or remove subjects - that is the admin's call. */
export function MySubjectsPage({ onSubmit }: { onSubmit: () => void }) {
  const { teacher, subjects } = useAuth();
  const name = teacher?.name ?? "";

  if (subjects.length === 0) {
    return (
      <EmptyState
        icon={BookOpen}
        title="No subjects assigned yet"
        description="Your school admin chooses which subjects and grades you teach. They will show up here as soon as you're assigned."
        className="mx-auto mt-8 max-w-lg"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Welcome{name ? `, ${name}` : ""}</h1>
          <p className="text-sm text-muted-foreground">
            You teach {subjects.length} subject{subjects.length !== 1 && "s"}. Your admin manages this list.
          </p>
        </div>
        <Button onClick={onSubmit}>
          <PlusCircle className="h-4 w-4" /> Submit a question
        </Button>
      </div>

      {groupSubjectsByGrade(subjects).map((group) => (
        <Card key={group.grade ?? "none"}>
          <CardHeader className="pb-2">
            <CardTitle>{group.grade ? gradeLabel(group.grade) : "Other"}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {group.subjects.map((s) => (
              <div key={s.id} className="flex items-center gap-2.5 rounded-lg border border-border bg-secondary/30 px-3 py-2.5">
                <BookOpen className="h-4 w-4 shrink-0 text-primary" />
                <span className="text-sm font-medium text-foreground">{s.name}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
