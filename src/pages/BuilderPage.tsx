import { useEffect, useRef, useState } from "react";
import {
  FileStack,
  Clock,
  Plus,
  Trash2,
  AlertTriangle,
  Save,
  Sparkles,
  RefreshCw,
  X,
  ShieldAlert,
  BookmarkPlus,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { MatchFollowingTable } from "@/components/MatchFollowingTable";
import { DiagramImage } from "@/components/DiagramImage";
import { VisualWorksheetGrid } from "@/components/VisualWorksheetGrid";
import { LatexText } from "@/components/LatexText";
import {
  DEFAULT_MARKS,
  DIFFICULTY_LABELS,
  DIFFICULTY_LEVELS,
  LANGUAGES,
  QUESTION_TYPE_LABELS,
  QUESTION_TYPE_ORDER,
  createBlueprint,
  createTemplate,
  deleteDraft,
  difficultyBucket,
  fetchGraph,
  fetchQuestions,
  generateQuestions,
  generateSection,
  getDraft,
  listTemplates,
  putDraft,
  type BuilderDraft,
  type Difficulty,
  type DraftQuestionSpec,
  type DraftSection,
  type GeneratedQuestionResult,
  type GraphNode,
  type Language,
  type PaperTemplate,
  type QuestionType,
  type SectionMode,
} from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import { cn } from "@/lib/utils";

const questionFormats: QuestionType[] = QUESTION_TYPE_ORDER;
const sectionModes: { value: SectionMode; label: string }[] = [
  { value: "specific", label: "Specific" },
  { value: "random", label: "Random" },
];

interface QuestionResultItem {
  specId: string;
  requestedLabel: string;
  result: GeneratedQuestionResult | null;
  error: string | null;
}

interface SectionResult {
  sectionId: string;
  items: QuestionResultItem[];
}

let sectionIdCounter = 0;
const newSectionId = () => `section-${Date.now()}-${++sectionIdCounter}`;

let questionIdCounter = 0;
const newQuestionSpecId = () => `q-${Date.now()}-${++questionIdCounter}`;

function makeQuestionSpec(topics: GraphNode[]): DraftQuestionSpec {
  return { id: newQuestionSpecId(), topic_id: topics[0]?.id ?? "", difficulty: "medium" };
}

function makeSection(topics: GraphNode[]): DraftSection {
  return {
    id: newSectionId(),
    question_format: "short_answer",
    mode: "random",
    questions: [makeQuestionSpec(topics)],
    topic_ids: topics[0] ? [topics[0].id] : [],
    difficulty: "medium",
    count: 3,
    marks_per_question: DEFAULT_MARKS.short_answer,
    generated_question_ids: [],
    language: "English",
  };
}

const sectionQuestionCount = (sec: DraftSection) => (sec.mode === "specific" ? sec.questions.length : sec.count);

export function BuilderPage({
  onSaved,
  applyTemplateId,
  onTemplateApplied,
}: {
  onSaved: (blueprintId: string) => void;
  applyTemplateId?: string | null;
  onTemplateApplied?: () => void;
}) {
  const { activeSubjectId } = useAuth();
  const [topics, setTopics] = useState<GraphNode[]>([]);
  const [paperName, setPaperName] = useState(`Question Paper — ${new Date().toLocaleDateString()}`);
  const [duration, setDuration] = useState(90);
  const [sections, setSections] = useState<DraftSection[]>([]);
  const [sectionResults, setSectionResults] = useState<SectionResult[]>([]);
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [hasGenerated, setHasGenerated] = useState(false);
  const [draftLoaded, setDraftLoaded] = useState(false);
  const [templates, setTemplates] = useState<PaperTemplate[]>([]);
  const [savingTemplateName, setSavingTemplateName] = useState<string | null>(null);
  const [savingTemplate, setSavingTemplate] = useState(false);

  const draftIdRef = useRef<string>(`draft-${Date.now()}`);
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Templates are teacher-scoped (reusable across subjects), so load them once.
  useEffect(() => {
    listTemplates().then(setTemplates).catch(() => {});
  }, []);

  const topicName = (id: string) => topics.find((t) => t.id === id)?.name ?? id;
  const topicNames = (ids: string[]) => ids.map(topicName).join(", ");

  // Load topics + rehydrate any existing draft for this subject.
  useEffect(() => {
    if (!activeSubjectId) return;
    let cancelled = false;
    fetchGraph(activeSubjectId).then(async (g) => {
      if (cancelled) return;
      setTopics(g.nodes);
      const nameOf = (id: string) => g.nodes.find((t) => t.id === id)?.name ?? id;

      const [draft, allQuestions] = await Promise.all([getDraft(activeSubjectId), fetchQuestions(activeSubjectId)]);
      if (cancelled) return;

      // A pending "Use in Builder" template takes precedence over any saved
      // draft — that effect (below) sets sections once templates load, so
      // skip rehydrating/defaulting here to avoid a load race clobbering it.
      if (applyTemplateId) {
        setDraftLoaded(true);
        return;
      }

      if (draft && draft.sections.length > 0) {
        draftIdRef.current = draft.id;
        setPaperName(draft.paper_name);
        setDuration(draft.duration_minutes ?? 90);
        setSections(draft.sections);

        const byId = new Map(allQuestions.map((q) => [q.id, q]));
        const rehydrated: SectionResult[] = draft.sections.map((s) => {
          const poolLabel = s.topic_ids.map(nameOf).join(", ");
          return {
            sectionId: s.id,
            items: s.generated_question_ids
              .map((qid) => byId.get(qid))
              .filter((q): q is NonNullable<typeof q> => Boolean(q))
              .map((q, idx) => ({
                specId: s.mode === "specific" ? s.questions[idx]?.id ?? q.id : q.id,
                requestedLabel: s.mode === "specific" ? nameOf(s.questions[idx]?.topic_id ?? "") : poolLabel,
                error: null,
                result: {
                  question: q,
                  difficulty: {
                    score: q.difficulty_score ?? 5,
                    features: {},
                    shap_contributions: null,
                    method: "heuristic" as const,
                  },
                  duplicate_matches: [],
                },
              })),
          };
        });
        if (rehydrated.some((r) => r.items.length > 0)) {
          setSectionResults(rehydrated);
          setHasGenerated(true);
        }
      } else if (g.nodes.length > 0) {
        setSections([makeSection(g.nodes)]);
      }
      setDraftLoaded(true);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSubjectId]);

  // Debounce-save the section configuration to the backend draft on every edit.
  useEffect(() => {
    if (!draftLoaded || !activeSubjectId || sections.length === 0) return;
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => {
      const draft: BuilderDraft = {
        id: draftIdRef.current,
        teacher_id: "",
        subject_id: activeSubjectId,
        paper_name: paperName,
        duration_minutes: duration,
        sections,
        updated_at: new Date().toISOString(),
      };
      putDraft(draft).catch(() => {});
    }, 800);
    return () => {
      if (saveTimeout.current) clearTimeout(saveTimeout.current);
    };
  }, [sections, paperName, duration, draftLoaded, activeSubjectId]);

  const persistGeneratedIds = (sectionId: string, ids: string[]) => {
    setSections((prev) => {
      const next = prev.map((s) => (s.id === sectionId ? { ...s, generated_question_ids: ids } : s));
      if (activeSubjectId) {
        putDraft({
          id: draftIdRef.current,
          teacher_id: "",
          subject_id: activeSubjectId,
          paper_name: paperName,
          duration_minutes: duration,
          sections: next,
          updated_at: new Date().toISOString(),
        }).catch(() => {});
      }
      return next;
    });
  };

  const addSection = () => setSections((s) => [...s, makeSection(topics)]);
  const removeSection = (id: string) => {
    setSections((s) => s.filter((sec) => sec.id !== id));
    setSectionResults((r) => r.filter((sr) => sr.sectionId !== id));
  };
  const updateSection = <K extends keyof DraftSection>(id: string, key: K, value: DraftSection[K]) =>
    setSections((s) => s.map((sec) => (sec.id === id ? { ...sec, [key]: value } : sec)));

  const setSectionMode = (id: string, mode: SectionMode) => updateSection(id, "mode", mode);

  const addQuestion = (sectionId: string) =>
    setSections((s) =>
      s.map((sec) => (sec.id === sectionId ? { ...sec, questions: [...sec.questions, makeQuestionSpec(topics)] } : sec))
    );

  const removeQuestion = (sectionId: string, questionId: string) =>
    setSections((s) =>
      s.map((sec) =>
        sec.id === sectionId ? { ...sec, questions: sec.questions.filter((q) => q.id !== questionId) } : sec
      )
    );

  const updateQuestion = <K extends keyof DraftQuestionSpec>(
    sectionId: string,
    questionId: string,
    key: K,
    value: DraftQuestionSpec[K]
  ) =>
    setSections((s) =>
      s.map((sec) =>
        sec.id === sectionId
          ? { ...sec, questions: sec.questions.map((q) => (q.id === questionId ? { ...q, [key]: value } : q)) }
          : sec
      )
    );

  const toggleSectionTopic = (id: string, topicId: string) =>
    setSections((s) =>
      s.map((sec) => {
        if (sec.id !== id) return sec;
        const has = sec.topic_ids.includes(topicId);
        return { ...sec, topic_ids: has ? sec.topic_ids.filter((t) => t !== topicId) : [...sec.topic_ids, topicId] };
      })
    );

  const setSectionFormat = (id: string, format: QuestionType) =>
    setSections((s) =>
      s.map((sec) => (sec.id === id ? { ...sec, question_format: format, marks_per_question: DEFAULT_MARKS[format] } : sec))
    );

  const applyTemplate = (templateId: string) => {
    const template = templates.find((t) => t.id === templateId);
    if (!template) return;
    setSections(
      template.sections.map((ts) => ({
        id: newSectionId(),
        question_format: ts.question_format,
        mode: ts.mode,
        questions:
          ts.mode === "specific"
            ? ts.difficulties.map((d) => ({ id: newQuestionSpecId(), topic_id: topics[0]?.id ?? "", difficulty: d }))
            : [],
        topic_ids: [],
        difficulty: ts.mode === "random" ? ts.difficulty : "medium",
        count: ts.mode === "random" ? ts.count : 3,
        marks_per_question: ts.marks_per_question,
        generated_question_ids: [],
        language: ts.language,
      }))
    );
    if (template.duration_minutes != null) setDuration(template.duration_minutes);
    setSectionResults([]);
    setHasGenerated(false);
  };

  // Arriving here from the Templates page ("Use in Builder") — apply it once
  // the template list has loaded, then clear the pending id so it doesn't
  // reapply on every render or hop back if the teacher revisits Templates.
  useEffect(() => {
    if (!applyTemplateId || templates.length === 0) return;
    applyTemplate(applyTemplateId);
    onTemplateApplied?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applyTemplateId, templates]);

  const handleSaveTemplate = async () => {
    if (!savingTemplateName || !savingTemplateName.trim() || sections.length === 0) return;
    setSavingTemplate(true);
    try {
      const template = await createTemplate({
        name: savingTemplateName.trim(),
        duration_minutes: duration,
        sections: sections.map((s) => ({
          question_format: s.question_format,
          mode: s.mode,
          difficulties: s.mode === "specific" ? s.questions.map((q) => q.difficulty) : [],
          difficulty: s.mode === "random" ? s.difficulty : "medium",
          count: s.mode === "random" ? s.count : s.questions.length,
          marks_per_question: s.marks_per_question,
          language: s.language,
        })),
      });
      setTemplates((prev) => [template, ...prev]);
      setSavingTemplateName(null);
    } finally {
      setSavingTemplate(false);
    }
  };

  const plannedQuestions = sections.reduce((s, sec) => s + sectionQuestionCount(sec), 0);
  const plannedMarks = sections.reduce((s, sec) => s + sectionQuestionCount(sec) * sec.marks_per_question, 0);

  const runQuestionSpec = async (section: DraftSection, spec: DraftQuestionSpec): Promise<QuestionResultItem> => {
    const label = `${topicName(spec.topic_id)} (${DIFFICULTY_LABELS[spec.difficulty]})`;
    if (!activeSubjectId || !spec.topic_id) {
      return { specId: spec.id, requestedLabel: label, result: null, error: "Select a topic" };
    }
    try {
      const { results } = await generateQuestions({
        subject_id: activeSubjectId,
        topic: topicName(spec.topic_id),
        num_questions: 1,
        question_type: section.question_format,
        difficulty: spec.difficulty,
        marks: section.marks_per_question,
        language: section.language,
        check_duplicates: true,
        save_to_bank: true,
      });
      return {
        specId: spec.id,
        requestedLabel: label,
        result: results[0] ?? null,
        error: results.length === 0 ? "No question returned" : null,
      };
    } catch (e) {
      return { specId: spec.id, requestedLabel: label, result: null, error: e instanceof Error ? e.message : "Generation failed" };
    }
  };

  const runSpecificSection = async (section: DraftSection): Promise<SectionResult> => {
    const items = await Promise.all(section.questions.map((spec) => runQuestionSpec(section, spec)));
    const ids = items.filter((i) => i.result).map((i) => i.result!.question.id);
    persistGeneratedIds(section.id, ids);
    return { sectionId: section.id, items };
  };

  const runRandomSection = async (section: DraftSection): Promise<SectionResult> => {
    const label = `${topicNames(section.topic_ids)} (${DIFFICULTY_LABELS[section.difficulty]})`;
    if (!activeSubjectId || section.topic_ids.length === 0) {
      return { sectionId: section.id, items: [{ specId: section.id, requestedLabel: label, result: null, error: "Select at least one topic" }] };
    }
    try {
      const { results } = await generateSection({
        subject_id: activeSubjectId,
        topic_ids: section.topic_ids,
        question_type: section.question_format,
        num_questions: section.count,
        difficulty: section.difficulty,
        marks: section.marks_per_question,
        language: section.language,
        check_duplicates: true,
        save_to_bank: true,
      });
      const items: QuestionResultItem[] =
        results.length === 0
          ? [{ specId: section.id, requestedLabel: label, result: null, error: "No questions returned" }]
          : results.map((r) => ({ specId: r.question.id, requestedLabel: label, result: r, error: null }));
      persistGeneratedIds(section.id, items.filter((i) => i.result).map((i) => i.result!.question.id));
      return { sectionId: section.id, items };
    } catch (e) {
      return {
        sectionId: section.id,
        items: [{ specId: section.id, requestedLabel: label, result: null, error: e instanceof Error ? e.message : "Generation failed" }],
      };
    }
  };

  const runSection = (section: DraftSection): Promise<SectionResult> =>
    section.mode === "specific" ? runSpecificSection(section) : runRandomSection(section);

  const generatePaper = async () => {
    setGenerating(true);
    setSectionResults([]);
    setExcludedIds(new Set());
    const results: SectionResult[] = [];
    for (const section of sections) {
      results.push(await runSection(section));
      setSectionResults([...results]);
    }
    setHasGenerated(true);
    setGenerating(false);
  };

  const regenerateSection = async (sectionId: string) => {
    const section = sections.find((s) => s.id === sectionId);
    if (!section) return;
    setRegeneratingSection(sectionId);
    const fresh = await runSection(section);
    setSectionResults((prev) => prev.map((r) => (r.sectionId === sectionId ? fresh : r)));
    setRegeneratingSection(null);
  };

  const toggleExcluded = (questionId: string) =>
    setExcludedIds((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) next.delete(questionId);
      else next.add(questionId);
      return next;
    });

  const finalQuestions = sectionResults
    .flatMap((r) => r.items.map((i) => i.result?.question).filter((q): q is NonNullable<typeof q> => Boolean(q)))
    .filter((q) => !excludedIds.has(q.id));
  const finalMarks = finalQuestions.reduce((s, q) => s + q.marks, 0);
  const anySectionError = sectionResults.some((r) => r.items.some((i) => i.error));

  const handleSavePaper = async () => {
    if (finalQuestions.length === 0 || !activeSubjectId) return;
    setSaving(true);
    try {
      const blueprintSections = sections.map((sec) => {
        const sr = sectionResults.find((r) => r.sectionId === sec.id);
        const ids = (sr?.items ?? [])
          .map((i) => i.result?.question.id)
          .filter((id): id is string => Boolean(id) && !excludedIds.has(id!));
        return {
          title: QUESTION_TYPE_LABELS[sec.question_format],
          question_format: sec.question_format,
          question_ids: ids,
        };
      });
      const blueprint = await createBlueprint({
        subject_id: activeSubjectId,
        name: paperName,
        total_marks: finalMarks,
        duration_minutes: duration,
        sections: blueprintSections,
      });
      await deleteDraft(activeSubjectId);
      onSaved(blueprint.id);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-1 h-fit lg:sticky lg:top-20">
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileStack className="h-4 w-4 text-primary" />
            <CardTitle>Section Configuration</CardTitle>
          </div>
          <CardDescription>Build your paper section by section, then generate questions for all of them at once</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">Paper Name</label>
            <Input value={paperName} onChange={(e) => setPaperName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-xs font-medium text-foreground">
              <Clock className="h-3.5 w-3.5" /> Duration (min)
            </label>
            <Input value={duration} onChange={(e) => setDuration(Number(e.target.value))} type="number" />
          </div>

          {templates.length > 0 && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-foreground">Load Template</label>
              <Select defaultValue="" onChange={(e) => e.target.value && applyTemplate(e.target.value)}>
                <option value="">Choose a saved pattern…</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.sections.length} section{t.sections.length !== 1 && "s"})
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div className="space-y-3">
            {sections.map((section, idx) => (
              <div key={section.id} className="space-y-2.5 rounded-lg border border-border p-3">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-semibold text-foreground">Section {idx + 1}</label>
                  <button className="text-muted-foreground hover:text-destructive" onClick={() => removeSection(section.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-muted-foreground">Question Format</label>
                  <Select
                    value={section.question_format}
                    onChange={(e) => setSectionFormat(section.id, e.target.value as QuestionType)}
                  >
                    {questionFormats.map((qt) => (
                      <option key={qt} value={qt}>
                        {QUESTION_TYPE_LABELS[qt]}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-muted-foreground">Mode</label>
                  <div className="flex gap-1.5">
                    {sectionModes.map((m) => (
                      <button
                        key={m.value}
                        onClick={() => setSectionMode(section.id, m.value)}
                        className={cn(
                          "flex-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors",
                          section.mode === m.value
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-border text-muted-foreground hover:bg-secondary/50"
                        )}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    {section.mode === "specific"
                      ? "Choose the topic and difficulty for each question individually."
                      : "Pick a topic pool and one difficulty — questions are drawn from it automatically."}
                  </p>
                </div>

                {section.mode === "specific" ? (
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-medium text-muted-foreground">
                      Questions ({section.questions.length})
                    </label>
                    {topics.length === 0 && <p className="text-[11px] text-muted-foreground">No topics yet — upload material first.</p>}
                    <div className="space-y-1.5">
                      {section.questions.map((q, qIdx) => (
                        <div key={q.id} className="flex items-center gap-1.5">
                          <span className="w-4 shrink-0 text-[10px] text-muted-foreground">{qIdx + 1}.</span>
                          <Select
                            className="flex-1 text-xs"
                            value={q.topic_id}
                            onChange={(e) => updateQuestion(section.id, q.id, "topic_id", e.target.value)}
                            disabled={topics.length === 0}
                          >
                            {topics.map((t) => (
                              <option key={t.id} value={t.id}>
                                {t.name}
                              </option>
                            ))}
                          </Select>
                          <Select
                            className="w-[92px] shrink-0 text-xs"
                            value={q.difficulty}
                            onChange={(e) => updateQuestion(section.id, q.id, "difficulty", e.target.value as Difficulty)}
                          >
                            {DIFFICULTY_LEVELS.map((d) => (
                              <option key={d} value={d}>
                                {DIFFICULTY_LABELS[d]}
                              </option>
                            ))}
                          </Select>
                          <button
                            className="shrink-0 text-muted-foreground hover:text-destructive disabled:opacity-30"
                            onClick={() => removeQuestion(section.id, q.id)}
                            disabled={section.questions.length <= 1}
                            title="Remove question"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <button
                      className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                      onClick={() => addQuestion(section.id)}
                    >
                      <Plus className="h-3 w-3" /> Add question
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-muted-foreground">
                        Topic Coverage ({section.topic_ids.length} selected)
                      </label>
                      <div className="max-h-32 space-y-1 overflow-y-auto rounded-md border border-border p-2 scrollbar-thin">
                        {topics.length === 0 && <p className="text-[11px] text-muted-foreground">No topics yet — upload material first.</p>}
                        {topics.map((t) => (
                          <label key={t.id} className="flex items-center gap-2 text-xs text-foreground">
                            <Checkbox
                              checked={section.topic_ids.includes(t.id)}
                              onCheckedChange={() => toggleSectionTopic(section.id, t.id)}
                            />
                            {t.name}
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-muted-foreground">Difficulty</label>
                      <div className="flex gap-1.5">
                        {DIFFICULTY_LEVELS.map((d) => (
                          <button
                            key={d}
                            onClick={() => updateSection(section.id, "difficulty", d as Difficulty)}
                            className={cn(
                              "flex-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors",
                              section.difficulty === d
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-border text-muted-foreground hover:bg-secondary/50"
                            )}
                          >
                            {DIFFICULTY_LABELS[d]}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] font-medium text-muted-foreground">Questions</label>
                      <Input
                        type="number"
                        min={1}
                        value={section.count}
                        onChange={(e) => updateSection(section.id, "count", Math.max(1, Number(e.target.value)))}
                      />
                    </div>
                  </>
                )}

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-muted-foreground">Marks each</label>
                  <Input
                    type="number"
                    min={1}
                    value={section.marks_per_question}
                    onChange={(e) => updateSection(section.id, "marks_per_question", Math.max(1, Number(e.target.value)))}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-muted-foreground">Language</label>
                  <Select
                    value={section.language}
                    onChange={(e) => updateSection(section.id, "language", e.target.value as Language)}
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </Select>
                </div>

                <p className="text-[11px] text-muted-foreground">
                  = {sectionQuestionCount(section)} question{sectionQuestionCount(section) !== 1 && "s"} ·{" "}
                  {sectionQuestionCount(section) * section.marks_per_question} marks
                </p>
              </div>
            ))}
          </div>

          <Button variant="outline" size="sm" className="w-full" onClick={addSection}>
            <Plus className="h-3.5 w-3.5" /> Add Section
          </Button>

          {savingTemplateName !== null ? (
            <div className="space-y-1.5 rounded-lg border border-border p-2.5">
              <label className="text-[11px] font-medium text-muted-foreground">Template name</label>
              <Input
                autoFocus
                value={savingTemplateName}
                onChange={(e) => setSavingTemplateName(e.target.value)}
                placeholder="e.g. Weekly Quiz Pattern"
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSaveTemplate} disabled={savingTemplate || !savingTemplateName.trim()}>
                  {savingTemplate ? "Saving..." : "Save"}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setSavingTemplateName(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setSavingTemplateName("")}
              disabled={sections.length === 0}
            >
              <BookmarkPlus className="h-3.5 w-3.5" /> Save as Template
            </Button>
          )}

          <div className="rounded-lg border border-border bg-secondary/40 p-3 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Planned</span>
              <span className="font-medium text-foreground">
                {plannedQuestions} question{plannedQuestions !== 1 && "s"} · {plannedMarks} marks
              </span>
            </div>
          </div>

          <Button className="w-full" onClick={generatePaper} disabled={generating || sections.length === 0}>
            <Sparkles className="h-4 w-4" /> {generating ? "Generating..." : "Generate Questions"}
          </Button>
        </CardContent>
      </Card>

      <div className="space-y-4 lg:col-span-2">
        {!hasGenerated ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
              <FileStack className="h-8 w-8 text-muted-foreground" />
              <p className="mt-3 text-sm font-medium text-foreground">No paper generated yet</p>
              <p className="mt-1 text-xs text-muted-foreground">Configure your sections and click "Generate Questions" to preview</p>
            </CardContent>
          </Card>
        ) : (
          <>
            <Card className={cn(anySectionError ? "border-warning/30 bg-warning/[0.03]" : "border-success/30 bg-success/[0.03]")}>
              <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {anySectionError ? "Generated with some issues" : "Paper generated"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {finalMarks} marks · {duration} min · {finalQuestions.length} question{finalQuestions.length !== 1 && "s"}
                    {excludedIds.size > 0 && ` · ${excludedIds.size} excluded`}
                  </p>
                </div>
                <Button size="sm" onClick={handleSavePaper} disabled={saving || finalQuestions.length === 0}>
                  <Save className="h-3.5 w-3.5" /> {saving ? "Saving..." : "Save Paper"}
                </Button>
              </CardContent>
            </Card>

            {sectionResults.map((sr, idx) => {
              const section = sections.find((s) => s.id === sr.sectionId);
              if (!section) return null;
              return (
                <Card key={sr.sectionId}>
                  <CardHeader className="flex-row items-center justify-between space-y-0">
                    <div>
                      <CardTitle>Section {idx + 1} — {QUESTION_TYPE_LABELS[section.question_format]}</CardTitle>
                      <CardDescription>
                        {sectionQuestionCount(section)} question{sectionQuestionCount(section) !== 1 && "s"} ·{" "}
                        {section.marks_per_question} marks each · {section.mode === "specific" ? "Specific" : "Random"}
                      </CardDescription>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => regenerateSection(sr.sectionId)} disabled={regeneratingSection === sr.sectionId}>
                      <RefreshCw className={cn("h-3.5 w-3.5", regeneratingSection === sr.sectionId && "animate-spin")} /> Regenerate
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {sr.items.map((item) => {
                      if (item.error || !item.result) {
                        return (
                          <p key={item.specId} className="flex items-center gap-1.5 text-xs text-destructive">
                            <AlertTriangle className="h-3.5 w-3.5" /> {item.requestedLabel}: {item.error ?? "Generation failed"}
                          </p>
                        );
                      }
                      const res = item.result;
                      const excluded = excludedIds.has(res.question.id);
                      const bestMatch = res.duplicate_matches[0];
                      const isDuplicate = Boolean(bestMatch?.is_duplicate);
                      const bucket = difficultyBucket(res.question.difficulty_score);
                      const topicLabel = res.question.topic_ids.length > 0 ? topicNames(res.question.topic_ids) : item.requestedLabel;
                      return (
                        <div
                          key={res.question.id}
                          className={cn(
                            "flex items-start gap-3 rounded-lg border p-3.5",
                            excluded ? "border-border bg-secondary/30 opacity-50" : isDuplicate ? "border-warning/40 bg-warning/[0.03]" : "border-border bg-white"
                          )}
                        >
                          <Checkbox checked={!excluded} onCheckedChange={() => toggleExcluded(res.question.id)} />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm text-foreground">
                              <LatexText text={res.question.text} />
                            </p>
                            {res.question.question_type === "stem_diagram" && res.question.diagram && (
                              <DiagramImage diagram={res.question.diagram} />
                            )}
                            {res.question.question_type === "visual_worksheet" && res.question.grid_layout && (
                              <VisualWorksheetGrid layout={res.question.grid_layout} showAnswers />
                            )}
                            {res.question.question_type === "mcq" && res.question.options && (
                              <ul className="mt-1.5 space-y-0.5 text-xs text-muted-foreground">
                                {res.question.options.map((opt, oi) => (
                                  <li key={oi} className={cn(opt === res.question.correct_answer && "font-medium text-success")}>
                                    {String.fromCharCode(97 + oi)}) {opt}
                                  </li>
                                ))}
                              </ul>
                            )}
                            {res.question.question_type === "match_following" && res.question.match_pairs && (
                              <MatchFollowingTable question={res.question} showAnswers />
                            )}
                            {res.question.question_type === "true_false" && (
                              <p className="mt-1 text-xs text-muted-foreground">Answer: {res.question.is_true ? "True" : "False"}</p>
                            )}
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              <Badge variant="outline">{topicLabel}</Badge>
                              <Badge variant="outline">{res.question.marks} marks</Badge>
                              <Badge variant={bucket === "Hard" ? "destructive" : bucket === "Medium" ? "warning" : "success"}>{bucket}</Badge>
                              {isDuplicate && (
                                <Badge variant="warning">
                                  <ShieldAlert className="h-3 w-3" /> {Math.round(bestMatch.final_score * 100)}% similar to existing
                                </Badge>
                              )}
                            </div>
                          </div>
                          <button
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => toggleExcluded(res.question.id)}
                            title={excluded ? "Include" : "Exclude"}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
