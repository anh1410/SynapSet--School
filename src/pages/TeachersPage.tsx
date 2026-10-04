import { useEffect, useState } from "react";
import { Check, KeyRound, Plus, ShieldCheck, ShieldOff, Trash2, UserCheck, UserX, Users, BookOpen, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/lib/AuthContext";
import {
  ApiError,
  createTeacher,
  deleteTeacher,
  gradeLabel,
  groupSubjectsByGrade,
  listTeachers,
  setTeacherSubjects,
  subjectLabel,
  updateTeacher,
  type AdminTeacher,
  type Subject,
} from "@/lib/api";

const MIN_PASSWORD = 8;
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Please try again.");

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function SubjectChecklist({
  subjects,
  selected,
  onToggle,
}: {
  subjects: Subject[];
  selected: string[];
  onToggle: (id: string) => void;
}) {
  if (subjects.length === 0) {
    return <p className="text-xs text-muted-foreground">No subjects exist yet. Create some on the Subjects page first.</p>;
  }
  return (
    <div className="max-h-64 space-y-3 overflow-y-auto rounded-md border border-border p-3 scrollbar-thin">
      {groupSubjectsByGrade(subjects).map((group) => (
        <div key={group.grade ?? "none"}>
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {group.grade ? gradeLabel(group.grade) : "No grade set"}
          </p>
          <div className="grid gap-1.5 sm:grid-cols-2">
            {group.subjects.map((s) => (
              <label key={s.id} className="flex items-center gap-2 text-xs text-foreground">
                <Checkbox checked={selected.includes(s.id)} onCheckedChange={() => onToggle(s.id)} />
                {s.name}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

export function TeachersPage() {
  const { teacher: me, subjects } = useAuth();
  const [teachers, setTeachers] = useState<AdminTeacher[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newSubjects, setNewSubjects] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);

  const [panel, setPanel] = useState<{ id: string; kind: "subjects" | "password" } | null>(null);
  const [draftSubjects, setDraftSubjects] = useState<string[]>([]);
  const [draftPassword, setDraftPassword] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    listTeachers()
      .then(setTeachers)
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoading(false));
  }, []);

  const replace = (updated: AdminTeacher) => setTeachers((ts) => ts.map((t) => (t.id === updated.id ? updated : t)));

  const run = async (id: string, action: () => Promise<void>) => {
    setBusyId(id);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createTeacher({ name: name.trim(), email: email.trim(), password, subject_ids: newSubjects });
      setTeachers((ts) => [...ts, created]);
      setNotice(`Created ${created.name}. Share the password you set with them so they can log in as ${created.email}.`);
      setName("");
      setEmail("");
      setPassword("");
      setNewSubjects([]);
      setShowAdd(false);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setCreating(false);
    }
  };

  const openPanel = (t: AdminTeacher, kind: "subjects" | "password") => {
    if (panel?.id === t.id && panel.kind === kind) {
      setPanel(null);
      return;
    }
    setPanel({ id: t.id, kind });
    setDraftSubjects(t.subject_ids);
    setDraftPassword("");
    setError(null);
    setNotice(null);
  };

  const saveSubjects = (t: AdminTeacher) =>
    run(t.id, async () => {
      replace(await setTeacherSubjects(t.id, draftSubjects));
      setPanel(null);
      setNotice(`Updated subjects for ${t.name}.`);
    });

  const savePassword = (t: AdminTeacher) =>
    run(t.id, async () => {
      await updateTeacher(t.id, { password: draftPassword });
      setPanel(null);
      setNotice(`Password reset for ${t.name}. Share the new password with them.`);
    });

  const toggleActive = (t: AdminTeacher) =>
    run(t.id, async () => {
      replace(await updateTeacher(t.id, { active: !t.active }));
      setNotice(t.active ? `${t.name} can no longer log in.` : `${t.name} can log in again.`);
    });

  const toggleRole = (t: AdminTeacher) => {
    const makingAdmin = t.role === "teacher";
    const ok = window.confirm(
      makingAdmin
        ? `Make ${t.name} an admin?\n\nAdmins can upload materials, generate questions, build papers and manage every teacher and subject.`
        : `Make ${t.name} a regular teacher again?`
    );
    if (!ok) return;
    return run(t.id, async () => {
      replace(await updateTeacher(t.id, { role: makingAdmin ? "admin" : "teacher" }));
    });
  };

  const handleDelete = (t: AdminTeacher) => {
    if (!window.confirm(`Delete ${t.name} (${t.email})?\n\nTheir account is removed permanently. Deactivate instead if they might come back.`))
      return;
    return run(t.id, async () => {
      await deleteTeacher(t.id);
      setTeachers((ts) => ts.filter((x) => x.id !== t.id));
      setPanel(null);
    });
  };

  const sorted = [...teachers].sort((a, b) =>
    a.role === b.role ? a.name.localeCompare(b.name) : a.role === "admin" ? -1 : 1
  );
  const subjectById = new Map(subjects.map((s) => [s.id, s]));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Teachers</h1>
          <p className="text-sm text-muted-foreground">
            Only you decide which subjects each teacher has. Teachers can't add, pick or remove subjects themselves.
          </p>
        </div>
        <Button onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showAdd ? "Cancel" : "Add teacher"}
        </Button>
      </div>

      {notice && <p className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">{notice}</p>}
      {error && <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>}

      {showAdd && (
        <Card>
          <CardHeader>
            <CardTitle>New teacher account</CardTitle>
            <CardDescription>Teachers can't sign themselves up. Create the account here and give them the password.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreate}>
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-foreground">Full name</label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Ms. Rao" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-foreground">Email</label>
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="rao@school.edu" />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-foreground">Password (min {MIN_PASSWORD})</label>
                  <Input
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={MIN_PASSWORD}
                    placeholder="Shown so you can share it"
                  />
                  {password.length > 0 && password.length < MIN_PASSWORD && (
                    <p className="mt-1 text-[11px] text-destructive">
                      Too short: {password.length} of {MIN_PASSWORD} characters. Add {MIN_PASSWORD - password.length} more.
                    </p>
                  )}
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-foreground">Subjects (optional, you can change these any time)</label>
                <SubjectChecklist subjects={subjects} selected={newSubjects} onToggle={(id) => setNewSubjects((l) => toggle(l, id))} />
              </div>
              <Button type="submit" disabled={creating || !name.trim() || !email.trim() || password.length < MIN_PASSWORD}>
                {creating ? "Creating…" : "Create teacher"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : sorted.length === 0 ? (
        <EmptyState icon={Users} title="No teachers yet" description="Add a teacher to give them subjects." />
      ) : (
        <div className="space-y-3">
          {sorted.map((t) => {
            const isMe = t.id === me?.id;
            const busy = busyId === t.id;
            const open = panel?.id === t.id ? panel.kind : null;
            return (
              <Card key={t.id} className={t.active ? undefined : "opacity-70"}>
                <CardContent className="space-y-3 p-4">
                  <div className="flex flex-wrap items-start gap-3">
                    <Avatar initials={initialsFor(t.name)} />
                    <div className="min-w-[12rem] flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-foreground">{t.name}</p>
                        {isMe && <Badge variant="outline">You</Badge>}
                        <Badge variant={t.role === "admin" ? "default" : "secondary"}>
                          {t.role === "admin" ? "Admin" : "Teacher"}
                        </Badge>
                        {!t.active && <Badge variant="destructive">Deactivated</Badge>}
                        {t.credit_count > 0 && (
                          <Badge variant="success" title="Questions of theirs used in exported papers">
                            {t.credit_count} credit{t.credit_count === 1 ? "" : "s"}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">{t.email}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        {t.role === "admin" ? (
                          <span className="text-xs text-muted-foreground">Can access every subject</span>
                        ) : t.subject_ids.length === 0 ? (
                          <span className="text-xs text-muted-foreground">No subjects assigned yet</span>
                        ) : (
                          t.subject_ids.map((sid) => {
                            const s = subjectById.get(sid);
                            return s ? (
                              <Badge key={sid} variant="outline">
                                {subjectLabel(s)}
                              </Badge>
                            ) : null;
                          })
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {t.role === "teacher" && (
                        <Button size="sm" variant={open === "subjects" ? "secondary" : "ghost"} disabled={busy} onClick={() => openPanel(t, "subjects")}>
                          <BookOpen className="h-3.5 w-3.5" /> Subjects
                        </Button>
                      )}
                      <Button size="sm" variant={open === "password" ? "secondary" : "ghost"} disabled={busy} onClick={() => openPanel(t, "password")}>
                        <KeyRound className="h-3.5 w-3.5" /> Password
                      </Button>
                      {!isMe && (
                        <>
                          <Button size="sm" variant="ghost" disabled={busy} onClick={() => toggleRole(t)}>
                            {t.role === "admin" ? <ShieldOff className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                            {t.role === "admin" ? "Make teacher" : "Make admin"}
                          </Button>
                          <Button size="sm" variant="ghost" disabled={busy} onClick={() => toggleActive(t)}>
                            {t.active ? <UserX className="h-3.5 w-3.5" /> : <UserCheck className="h-3.5 w-3.5" />}
                            {t.active ? "Deactivate" : "Activate"}
                          </Button>
                          <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" disabled={busy} onClick={() => handleDelete(t)}>
                            <Trash2 className="h-3.5 w-3.5" /> Delete
                          </Button>
                        </>
                      )}
                    </div>
                  </div>

                  {open === "subjects" && (
                    <div className="space-y-3 border-t border-border pt-3">
                      <p className="text-xs font-medium text-foreground">Subjects {t.name} can use</p>
                      <SubjectChecklist subjects={subjects} selected={draftSubjects} onToggle={(id) => setDraftSubjects((l) => toggle(l, id))} />
                      <div className="flex gap-2">
                        <Button size="sm" disabled={busy} onClick={() => saveSubjects(t)}>
                          <Check className="h-3.5 w-3.5" /> Save subjects
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setPanel(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}

                  {open === "password" && (
                    <div className="space-y-3 border-t border-border pt-3">
                      <p className="text-xs font-medium text-foreground">New password for {t.name}</p>
                      <div className="flex flex-wrap items-center gap-2">
                        <Input
                          className="max-w-xs"
                          value={draftPassword}
                          onChange={(e) => setDraftPassword(e.target.value)}
                          minLength={MIN_PASSWORD}
                          placeholder={`At least ${MIN_PASSWORD} characters`}
                          autoFocus
                        />
                        <Button size="sm" disabled={busy || draftPassword.length < MIN_PASSWORD} onClick={() => savePassword(t)}>
                          <Check className="h-3.5 w-3.5" /> Save password
                        </Button>
                        {draftPassword.length > 0 && draftPassword.length < MIN_PASSWORD && (
                          <span className="text-[11px] text-destructive">
                            Too short: {draftPassword.length} of {MIN_PASSWORD} characters
                          </span>
                        )}
                        <Button size="sm" variant="ghost" onClick={() => setPanel(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
