import { useEffect, useState } from "react";
import { BookOpen, Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/lib/AuthContext";
import {
  ApiError,
  GRADES,
  deleteSubject,
  gradeLabel,
  groupSubjectsByGrade,
  listTeachers,
  updateSubject,
  createSubject,
  type AdminTeacher,
  type Subject,
} from "@/lib/api";

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

export function SubjectsPage() {
  const { subjects, refreshSubjects } = useAuth();
  const [teachers, setTeachers] = useState<AdminTeacher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newGrade, setNewGrade] = useState<string>("1");
  const [adding, setAdding] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editGrade, setEditGrade] = useState<string>("1");

  const loadTeachers = () =>
    listTeachers()
      .then(setTeachers)
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoading(false));

  useEffect(() => {
    loadTeachers();
  }, []);

  const teachersFor = (subjectId: string) =>
    teachers.filter((t) => t.role === "teacher" && t.subject_ids.includes(subjectId));

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setAdding(true);
    setError(null);
    try {
      await createSubject(name, newGrade);
      await refreshSubjects();
      setNewName("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setAdding(false);
    }
  };

  const startEdit = (s: Subject) => {
    setEditingId(s.id);
    setEditName(s.name);
    setEditGrade(s.grade ?? "1");
    setError(null);
  };

  const saveEdit = async (id: string) => {
    const name = editName.trim();
    if (!name) return;
    setError(null);
    try {
      await updateSubject(id, { name, grade: editGrade });
      await refreshSubjects();
      setEditingId(null);
    } catch (err) {
      setError(errorText(err));
    }
  };

  const handleDelete = async (s: Subject) => {
    const assigned = teachersFor(s.id).length;
    const ok = window.confirm(
      `Delete "${s.name}"${s.grade ? ` (${gradeLabel(s.grade)})` : ""}?\n\n` +
        `It will be removed from the school${assigned ? ` and from ${assigned} teacher${assigned > 1 ? "s" : ""}` : ""}. ` +
        `Its uploaded materials and questions will no longer be reachable from the app.`
    );
    if (!ok) return;
    setError(null);
    try {
      await deleteSubject(s.id);
      await refreshSubjects();
      await loadTeachers();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const groups = groupSubjectsByGrade(subjects);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Add a subject</CardTitle>
          <CardDescription>
            Subjects belong to the whole school. Create one per grade, then assign it to teachers on the Teachers page.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-wrap items-end gap-3" onSubmit={handleAdd}>
            <div className="min-w-[12rem] flex-1">
              <label className="mb-1 block text-xs font-medium text-foreground">Subject name</label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Maths" required />
            </div>
            <div className="w-40">
              <label className="mb-1 block text-xs font-medium text-foreground">Grade</label>
              <Select value={newGrade} onChange={(e) => setNewGrade(e.target.value)}>
                {GRADES.map((g) => (
                  <option key={g} value={g}>
                    {gradeLabel(g)}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" disabled={adding || !newName.trim()}>
              <Plus className="h-4 w-4" />
              {adding ? "Adding…" : "Add subject"}
            </Button>
          </form>
          {error && <p className="mt-3 text-xs text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : groups.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No subjects yet"
          description="Add your first subject above, for example Maths for Grade 5."
        />
      ) : (
        groups.map((group) => (
          <Card key={group.grade ?? "none"}>
            <CardHeader className="pb-2">
              <CardTitle>{group.grade ? gradeLabel(group.grade) : "No grade set yet"}</CardTitle>
              {!group.grade && (
                <CardDescription>
                  These subjects were created before grades existed. Edit each one to give it a grade.
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="divide-y divide-border">
              {group.subjects.map((s) => {
                const assigned = teachersFor(s.id);
                const editing = editingId === s.id;
                return (
                  <div key={s.id} className="flex flex-wrap items-center gap-3 py-3">
                    {editing ? (
                      <>
                        <Input
                          className="min-w-[10rem] flex-1"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          autoFocus
                        />
                        <div className="w-36">
                          <Select value={editGrade} onChange={(e) => setEditGrade(e.target.value)}>
                            {GRADES.map((g) => (
                              <option key={g} value={g}>
                                {gradeLabel(g)}
                              </option>
                            ))}
                          </Select>
                        </div>
                        <Button size="sm" onClick={() => saveEdit(s.id)} disabled={!editName.trim()}>
                          <Check className="h-3.5 w-3.5" /> Save
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                          <X className="h-3.5 w-3.5" /> Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <div className="min-w-[10rem] flex-1">
                          <p className="text-sm font-medium text-foreground">{s.name}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            {assigned.length === 0 ? (
                              <span className="text-xs text-muted-foreground">No teachers assigned</span>
                            ) : (
                              assigned.map((t) => (
                                <Badge key={t.id} variant="secondary">
                                  {t.name}
                                </Badge>
                              ))
                            )}
                          </div>
                        </div>
                        <Button size="sm" variant="ghost" onClick={() => startEdit(s)}>
                          <Pencil className="h-3.5 w-3.5" /> Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive hover:text-destructive"
                          onClick={() => handleDelete(s)}
                        >
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </Button>
                      </>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
