import { useEffect, useMemo, useRef, useState } from "react";
import { Plus, Trash2, Send, Save, ArrowLeft, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ImageUpload } from "@/components/ImageUpload";
import { LatexText } from "@/components/LatexText";
import { QuestionPreview } from "@/components/QuestionPreview";
import { useAuth } from "@/lib/AuthContext";
import {
  DEFAULT_MARKS,
  DIFFICULTY_LABELS,
  DIFFICULTY_LEVELS,
  QUESTION_TYPE_LABELS,
  QUESTION_TYPE_ORDER,
  createSubmission,
  difficultyBucket,
  listSubjectTopics,
  subjectLabel,
  toLetter,
  updateSubmission,
  type Difficulty,
  type GridLayoutKind,
  type Question,
  type QuestionType,
  type ResponseStyle,
  type Submission,
  type SubmittedQuestion,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const textareaClass =
  "flex w-full rounded-lg border border-input bg-white px-3 py-2 text-sm shadow-subtle transition-all duration-200 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-primary";

const MAX_OPTIONS = 8;
const MAX_PAIRS = 10;
const MAX_WORKSHEET_ITEMS = 8;

const GRID_KIND_LABELS: Record<GridLayoutKind, string> = {
  grid_2x4: "Grid (4 per row)",
  two_column_match: "Two columns",
  single_row: "Single row",
};
const RESPONSE_STYLE_LABELS: Record<ResponseStyle, string> = {
  circle_choice: "Circle the right ones",
  blank_line: "Write a word on a line",
  match_lines: "Draw matching lines",
};

interface WorksheetItem {
  image_id: string | null;
  label: string;
  is_correct: boolean;
}

interface FormState {
  subjectId: string;
  type: QuestionType;
  text: string;
  marks: number;
  difficulty: Difficulty;
  topicIds: string[];
  options: string[];
  correctIndex: number | null;
  answer: string;
  pairs: { left: string; right: string }[];
  isTrue: boolean | null;
  diagramId: string | null;
  diagramCaption: string;
  gridKind: GridLayoutKind;
  responseStyle: ResponseStyle;
  items: WorksheetItem[];
}

const blankItems = (n = 4): WorksheetItem[] =>
  Array.from({ length: n }, () => ({ image_id: null, label: "", is_correct: false }));

function emptyForm(subjectId: string): FormState {
  return {
    subjectId,
    type: "mcq",
    text: "",
    marks: DEFAULT_MARKS.mcq,
    difficulty: "medium",
    topicIds: [],
    options: ["", "", "", ""],
    correctIndex: null,
    answer: "",
    pairs: [
      { left: "", right: "" },
      { left: "", right: "" },
    ],
    isTrue: null,
    diagramId: null,
    diagramCaption: "",
    gridKind: "grid_2x4",
    responseStyle: "circle_choice",
    items: blankItems(),
  };
}

function formFromSubmission(sub: Submission): FormState {
  const q = sub.question;
  const base = emptyForm(sub.subject_id);
  const options = q.options && q.options.length > 0 ? q.options : base.options;
  const idx = q.correct_answer != null ? options.indexOf(q.correct_answer) : -1;
  const grid = q.grid_layout;
  return {
    ...base,
    type: q.question_type,
    // a worksheet's instruction lives in grid_layout.instruction; its text mirrors it
    text: q.question_type === "visual_worksheet" ? (grid?.instruction ?? q.text) : q.text,
    marks: q.marks,
    difficulty: difficultyBucket(q.difficulty_score).toLowerCase() as Difficulty,
    topicIds: q.topic_ids,
    options,
    correctIndex: idx >= 0 ? idx : null,
    answer: q.question_type === "mcq" ? "" : (q.correct_answer ?? ""),
    pairs: q.match_pairs && q.match_pairs.length > 0 ? q.match_pairs.map((p) => ({ ...p })) : base.pairs,
    isTrue: q.is_true,
    diagramId: q.diagram?.image_id ?? null,
    diagramCaption: q.diagram?.caption ?? "",
    gridKind: grid?.kind ?? base.gridKind,
    responseStyle: grid?.response_style ?? base.responseStyle,
    items: grid
      ? grid.items.map((it) => ({
          image_id: it.visual.image_id,
          label: it.label ?? "",
          is_correct: !!it.is_correct,
        }))
      : base.items,
  };
}

/** Only sends what the chosen type actually uses; the server re-validates everything. */
function toSubmitted(f: FormState): SubmittedQuestion {
  const out: SubmittedQuestion = {
    text: f.text.trim(),
    question_type: f.type,
    marks: f.marks,
    difficulty: f.difficulty,
    topic_ids: f.topicIds,
  };

  if (f.type === "mcq") {
    const kept = f.options.map((o, i) => ({ text: o.trim(), i })).filter((o) => o.text);
    out.options = kept.map((o) => o.text);
    out.correct_answer = kept.find((o) => o.i === f.correctIndex)?.text ?? null;
  }
  if (["short_answer", "long_answer", "numerical", "fill_in_blank", "stem_diagram"].includes(f.type)) {
    out.correct_answer = f.answer.trim();
  }
  if (f.type === "match_following") {
    out.match_pairs = f.pairs.map((p) => ({ left: p.left.trim(), right: p.right.trim() }));
  }
  if (f.type === "true_false") out.is_true = f.isTrue;

  if (f.type === "visual_worksheet") {
    out.grid_layout = {
      kind: f.gridKind,
      response_style: f.responseStyle,
      items: f.items
        .filter((it) => it.image_id)
        .map((it) => ({
          image_id: it.image_id as string,
          label: it.label.trim() || null,
          is_correct: f.responseStyle === "circle_choice" ? it.is_correct : null,
        })),
    };
  } else if (f.diagramId) {
    out.diagram = { image_id: f.diagramId, caption: f.diagramCaption.trim() || null };
  }
  return out;
}

/** The first thing wrong with the form, in plain words, or null. Mirrors the server's rules
 *  so the teacher gets an answer before sending; the server stays the authority. */
function problemWith(f: FormState): string | null {
  const isWorksheet = f.type === "visual_worksheet";
  if (!f.text.trim()) return isWorksheet ? "Write the instruction for the worksheet." : "Type the question.";
  if (!Number.isInteger(f.marks) || f.marks < 1 || f.marks > 100) return "Marks must be between 1 and 100.";

  if (f.type === "mcq") {
    const filled = f.options.map((o) => o.trim()).filter(Boolean);
    if (filled.length < 2) return "Add at least two options.";
    if (new Set(filled.map((o) => o.toLowerCase())).size !== filled.length) return "Two options are the same.";
    const correct = f.correctIndex != null ? f.options[f.correctIndex]?.trim() : "";
    if (!correct) return "Mark which option is correct.";
  }
  if (f.type === "fill_in_blank" && !f.text.includes("___")) return 'Put a blank (___) in the sentence. Use "Insert blank".';
  if (["short_answer", "long_answer", "numerical", "fill_in_blank", "stem_diagram"].includes(f.type) && !f.answer.trim()) {
    return f.type === "fill_in_blank" ? "Type the word that fills the blank." : "Type the model answer.";
  }
  if (f.type === "match_following") {
    if (f.pairs.length < 2) return "Add at least two pairs.";
    if (f.pairs.some((p) => !p.left.trim() || !p.right.trim())) return "Fill in both sides of every pair.";
  }
  if (f.type === "true_false" && f.isTrue == null) return "Choose whether the statement is true or false.";
  if (isWorksheet) {
    const withPicture = f.items.filter((it) => it.image_id);
    if (withPicture.length < 2) return "Add pictures to at least two items.";
    if (f.responseStyle === "circle_choice" && !withPicture.some((it) => it.is_correct)) {
      return "Tick which picture(s) are the right answer.";
    }
  }
  return null;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-foreground">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Teacher's form for proposing a question (or revising one an admin sent back).
 *  Everything adapts to the chosen type; nothing here can set admin-only fields. */
export function SubmitQuestionPage({
  editing,
  onDone,
  onCancel,
}: {
  editing: Submission | null;
  onDone: (sub: Submission) => void;
  onCancel: () => void;
}) {
  const { subjects, activeSubjectId } = useAuth();
  const [form, setForm] = useState<FormState>(() =>
    editing ? formFromSubmission(editing) : emptyForm(activeSubjectId ?? subjects[0]?.id ?? "")
  );
  const [marksTouched, setMarksTouched] = useState(!!editing);
  const [topics, setTopics] = useState<{ id: string; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showProblem, setShowProblem] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);

  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  useEffect(() => {
    if (!form.subjectId) return;
    let cancelled = false;
    listSubjectTopics(form.subjectId)
      .then((t) => !cancelled && setTopics(t))
      .catch(() => !cancelled && setTopics([]));
    return () => {
      cancelled = true;
    };
  }, [form.subjectId]);

  const changeType = (type: QuestionType) => {
    setForm((f) => ({ ...f, type, marks: marksTouched ? f.marks : DEFAULT_MARKS[type], diagramId: type === "visual_worksheet" ? null : f.diagramId }));
  };

  const changeSubject = (subjectId: string) => set({ subjectId, topicIds: [] });

  const insertBlank = () => {
    const el = textRef.current;
    const start = el?.selectionStart ?? form.text.length;
    const end = el?.selectionEnd ?? form.text.length;
    const next = `${form.text.slice(0, start)}___${form.text.slice(end)}`;
    set({ text: next });
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + 3, start + 3);
    });
  };

  const problem = problemWith(form);
  const isWorksheet = form.type === "visual_worksheet";
  const subject = subjects.find((s) => s.id === form.subjectId);

  // Built from the form, only to feed the same renderer the admin will see.
  const preview: Question = useMemo(() => {
    const s = toSubmitted(form);
    return {
      id: "preview",
      subject_id: form.subjectId,
      text: s.text,
      question_type: s.question_type,
      marks: s.marks,
      bloom_level: 2,
      topic_ids: s.topic_ids,
      co_ids: [],
      unit: null,
      options: s.options ?? null,
      correct_answer: s.correct_answer ?? null,
      match_pairs: s.match_pairs ?? null,
      match_right_order: null,
      is_true: s.is_true ?? null,
      difficulty_score: null,
      embedding_id: null,
      is_duplicate_of: null,
      source_document: null,
      created_at: new Date().toISOString(),
      diagram: s.diagram
        ? { kind: "image", source_code: "", image_id: s.diagram.image_id, caption: s.diagram.caption ?? null, render_error: null }
        : null,
      grid_layout: s.grid_layout
        ? {
            kind: s.grid_layout.kind,
            response_style: s.grid_layout.response_style,
            instruction: s.text,
            items: s.grid_layout.items.map((it) => ({
              visual: { subject: it.label ?? "", style: "uploaded", action: null, background: null, full_prompt: "", image_id: it.image_id },
              label: it.label ?? null,
              is_correct: it.is_correct ?? null,
            })),
          }
        : null,
    };
  }, [form]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setShowProblem(true);
    if (problem) return;
    setBusy(true);
    setError(null);
    try {
      const body = toSubmitted(form);
      const saved = editing ? await updateSubmission(editing.id, body) : await createSubmission(form.subjectId, body);
      onDone(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send the question. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const resubmitting = editing?.status === "changes_requested";

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <button
            type="button"
            onClick={onCancel}
            className="mb-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" /> Back
          </button>
          <h1 className="text-lg font-semibold text-foreground">{editing ? "Edit your question" : "Submit a question"}</h1>
          <p className="text-sm text-muted-foreground">
            Your admin reviews every question before it can be used in an exam paper.
          </p>
        </div>
      </div>

      {editing?.status === "changes_requested" && editing.admin_comment && (
        <div className="flex gap-2.5 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div>
            <p className="font-medium text-foreground">Your admin asked for changes</p>
            <p className="mt-0.5 whitespace-pre-wrap text-muted-foreground">{editing.admin_comment}</p>
          </div>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-5">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>About the question</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Subject">
                <Select value={form.subjectId} onChange={(e) => changeSubject(e.target.value)} disabled={!!editing}>
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {subjectLabel(s)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Question type">
                <Select value={form.type} onChange={(e) => changeType(e.target.value as QuestionType)}>
                  {QUESTION_TYPE_ORDER.map((t) => (
                    <option key={t} value={t}>
                      {QUESTION_TYPE_LABELS[t]}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Marks">
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={Number.isNaN(form.marks) ? "" : form.marks}
                  onChange={(e) => {
                    setMarksTouched(true);
                    set({ marks: e.target.value === "" ? NaN : Number(e.target.value) });
                  }}
                />
              </Field>
              {!isWorksheet && (
                <Field label="Difficulty" hint="How hard this is for a student of this grade.">
                  <div className="flex gap-1.5">
                    {DIFFICULTY_LEVELS.map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => set({ difficulty: d })}
                        className={cn(
                          "h-9 flex-1 rounded-lg border text-sm font-medium transition-colors",
                          form.difficulty === d
                            ? d === "easy"
                              ? "border-success bg-success/10 text-success"
                              : d === "medium"
                                ? "border-warning bg-warning/10 text-warning"
                                : "border-destructive bg-destructive/10 text-destructive"
                            : "border-border text-muted-foreground hover:border-primary/40"
                        )}
                      >
                        {DIFFICULTY_LABELS[d]}
                      </button>
                    ))}
                  </div>
                </Field>
              )}
              {topics.length > 0 && (
                <div className="sm:col-span-2">
                  <Field label="Topics (optional)" hint="Helps your admin put the question in the right part of a paper.">
                    <div className="flex flex-wrap gap-1.5">
                      {topics.map((t) => {
                        const on = form.topicIds.includes(t.id);
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() =>
                              set({ topicIds: on ? form.topicIds.filter((id) => id !== t.id) : [...form.topicIds, t.id] })
                            }
                            className={cn(
                              "rounded-full border px-2.5 py-1 text-xs transition-colors",
                              on
                                ? "border-primary bg-primary/10 font-medium text-primary"
                                : "border-border text-muted-foreground hover:border-primary/40"
                            )}
                          >
                            {t.name}
                          </button>
                        );
                      })}
                    </div>
                  </Field>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>{isWorksheet ? "Worksheet" : "Question"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field
                label={isWorksheet ? "Instruction for the child" : "Question text"}
                hint={
                  isWorksheet
                    ? 'e.g. "Circle the animal that lives in water."'
                    : "For maths use $ signs, e.g. $x^2 + 3x = 10$."
                }
              >
                <textarea
                  ref={textRef}
                  className={textareaClass}
                  rows={isWorksheet ? 2 : 3}
                  value={form.text}
                  onChange={(e) => set({ text: e.target.value })}
                  placeholder={form.type === "fill_in_blank" ? "The capital of India is ___." : "Type your question here"}
                />
                {form.type === "fill_in_blank" && (
                  <Button type="button" size="sm" variant="outline" onClick={insertBlank}>
                    Insert blank (___)
                  </Button>
                )}
                {form.text.includes("$") && (
                  <p className="rounded-md bg-secondary/50 px-2.5 py-1.5 text-xs text-muted-foreground">
                    Preview: <LatexText text={form.text} className="text-foreground" />
                  </p>
                )}
              </Field>

              {!isWorksheet && (
                <Field label="Diagram or picture (optional)" hint="Upload a drawing, graph or photo the question refers to.">
                  <ImageUpload imageId={form.diagramId} onChange={(id) => set({ diagramId: id })} label="Add diagram" />
                  {form.diagramId && (
                    <Input
                      value={form.diagramCaption}
                      onChange={(e) => set({ diagramCaption: e.target.value })}
                      placeholder="Caption (optional), e.g. Figure 1"
                      maxLength={200}
                      className="mt-2 max-w-xs"
                    />
                  )}
                </Field>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>
                {form.type === "mcq" && "Options"}
                {form.type === "match_following" && "Pairs to match"}
                {form.type === "true_false" && "Answer"}
                {isWorksheet && "Pictures"}
                {!["mcq", "match_following", "true_false", "visual_worksheet"].includes(form.type) &&
                  (form.type === "fill_in_blank" ? "Answer for the blank" : "Model answer")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {form.type === "mcq" && (
                <>
                  <p className="text-[11px] text-muted-foreground">Tap the circle next to the correct option.</p>
                  {form.options.map((opt, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => set({ correctIndex: i })}
                        title="Mark as correct"
                        className={cn(
                          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold transition-colors",
                          form.correctIndex === i
                            ? "border-success bg-success text-white"
                            : "border-border text-muted-foreground hover:border-success/60"
                        )}
                      >
                        {toLetter(i)}
                      </button>
                      <Input
                        value={opt}
                        onChange={(e) => set({ options: form.options.map((o, j) => (j === i ? e.target.value : o)) })}
                        placeholder={`Option ${toLetter(i)}`}
                        className="flex-1"
                      />
                      <button
                        type="button"
                        disabled={form.options.length <= 2}
                        onClick={() =>
                          set({
                            options: form.options.filter((_, j) => j !== i),
                            correctIndex:
                              form.correctIndex == null || form.correctIndex === i
                                ? null
                                : form.correctIndex > i
                                  ? form.correctIndex - 1
                                  : form.correctIndex,
                          })
                        }
                        title="Remove option"
                        className="shrink-0 text-muted-foreground hover:text-destructive disabled:pointer-events-none disabled:opacity-30"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={form.options.length >= MAX_OPTIONS}
                    onClick={() => set({ options: [...form.options, ""] })}
                  >
                    <Plus className="h-3.5 w-3.5" /> Add option
                  </Button>
                </>
              )}

              {["short_answer", "long_answer", "numerical", "fill_in_blank", "stem_diagram"].includes(form.type) && (
                <textarea
                  className={textareaClass}
                  rows={form.type === "long_answer" ? 5 : 2}
                  value={form.answer}
                  onChange={(e) => set({ answer: e.target.value })}
                  placeholder={form.type === "fill_in_blank" ? "The word(s) that go in the blank" : "What a full-marks answer looks like"}
                />
              )}

              {form.type === "true_false" && (
                <div className="flex gap-2">
                  <Button type="button" variant={form.isTrue === true ? "primary" : "outline"} onClick={() => set({ isTrue: true })}>
                    The statement is True
                  </Button>
                  <Button type="button" variant={form.isTrue === false ? "primary" : "outline"} onClick={() => set({ isTrue: false })}>
                    The statement is False
                  </Button>
                </div>
              )}

              {form.type === "match_following" && (
                <>
                  <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-x-2 text-[11px] font-medium text-muted-foreground">
                    <span>Column A</span>
                    <span />
                    <span>Matches with (Column B)</span>
                    <span />
                  </div>
                  {form.pairs.map((pair, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <Input
                        value={pair.left}
                        onChange={(e) => set({ pairs: form.pairs.map((p, j) => (j === i ? { ...p, left: e.target.value } : p)) })}
                        className="flex-1"
                      />
                      <span className="text-xs text-muted-foreground">→</span>
                      <Input
                        value={pair.right}
                        onChange={(e) => set({ pairs: form.pairs.map((p, j) => (j === i ? { ...p, right: e.target.value } : p)) })}
                        className="flex-1"
                      />
                      <button
                        type="button"
                        disabled={form.pairs.length <= 2}
                        onClick={() => set({ pairs: form.pairs.filter((_, j) => j !== i) })}
                        title="Remove pair"
                        className="shrink-0 text-muted-foreground hover:text-destructive disabled:pointer-events-none disabled:opacity-30"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={form.pairs.length >= MAX_PAIRS}
                    onClick={() => set({ pairs: [...form.pairs, { left: "", right: "" }] })}
                  >
                    <Plus className="h-3.5 w-3.5" /> Add pair
                  </Button>
                  <p className="text-[11px] text-muted-foreground">Column B is shuffled automatically on the paper.</p>
                </>
              )}

              {isWorksheet && (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Layout">
                      <Select value={form.gridKind} onChange={(e) => set({ gridKind: e.target.value as GridLayoutKind })}>
                        {(Object.keys(GRID_KIND_LABELS) as GridLayoutKind[]).map((k) => (
                          <option key={k} value={k}>
                            {GRID_KIND_LABELS[k]}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label="How the child answers">
                      <Select value={form.responseStyle} onChange={(e) => set({ responseStyle: e.target.value as ResponseStyle })}>
                        {(Object.keys(RESPONSE_STYLE_LABELS) as ResponseStyle[]).map((k) => (
                          <option key={k} value={k}>
                            {RESPONSE_STYLE_LABELS[k]}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {form.items.map((it, i) => (
                      <div key={i} className="space-y-1.5 rounded-lg border border-border p-2">
                        <ImageUpload
                          compact
                          imageId={it.image_id}
                          onChange={(id) => set({ items: form.items.map((x, j) => (j === i ? { ...x, image_id: id } : x)) })}
                        />
                        <Input
                          value={it.label}
                          onChange={(e) => set({ items: form.items.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) })}
                          placeholder="Label (optional)"
                          className="h-8 text-xs"
                        />
                        <div className="flex items-center justify-between">
                          {form.responseStyle === "circle_choice" ? (
                            <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-muted-foreground">
                              <input
                                type="checkbox"
                                checked={it.is_correct}
                                onChange={(e) =>
                                  set({ items: form.items.map((x, j) => (j === i ? { ...x, is_correct: e.target.checked } : x)) })
                                }
                              />
                              Correct
                            </label>
                          ) : (
                            <span />
                          )}
                          <button
                            type="button"
                            disabled={form.items.length <= 2}
                            onClick={() => set({ items: form.items.filter((_, j) => j !== i) })}
                            title="Remove item"
                            className="text-muted-foreground hover:text-destructive disabled:pointer-events-none disabled:opacity-30"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={form.items.length >= MAX_WORKSHEET_ITEMS}
                    onClick={() => set({ items: [...form.items, ...blankItems(1)] })}
                  >
                    <Plus className="h-3.5 w-3.5" /> Add picture slot
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle>How it will look</CardTitle>
                <div className="flex items-center gap-1.5">
                  <Badge variant="secondary">{QUESTION_TYPE_LABELS[form.type]}</Badge>
                  <Badge variant="outline">{Number.isNaN(form.marks) ? "–" : form.marks} mark{form.marks === 1 ? "" : "s"}</Badge>
                </div>
              </div>
              {subject && <p className="text-xs text-muted-foreground">{subjectLabel(subject)}</p>}
            </CardHeader>
            <CardContent>
              {form.text.trim() || form.items.some((i) => i.image_id) ? (
                <QuestionPreview question={preview} />
              ) : (
                <p className="text-xs text-muted-foreground">Start typing and your question appears here.</p>
              )}
            </CardContent>
          </Card>

          {showProblem && problem && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">{problem}</p>
          )}
          {error && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">{error}</p>
          )}

          <div className="flex gap-2">
            <Button type="submit" disabled={busy} className="flex-1">
              {editing ? <Save className="h-4 w-4" /> : <Send className="h-4 w-4" />}
              {busy ? "Sending…" : resubmitting ? "Resubmit for review" : editing ? "Save changes" : "Submit for review"}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel} disabled={busy}>
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
