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
import {
  DEFAULT_MARKS,
  DIFFICULTY_LABELS,
  DIFFICULTY_LEVELS,
  QUESTION_TYPE_LABELS,
  QUESTION_TYPE_ORDER,
  createBlueprint,
  createTemplate,
  deleteDraft,
  difficultyBucket,
  fetchGraph,
  fetchQuestions,
  generateSection,
  getDraft,
  listTemplates,
  putDraft,
  type BuilderDraft,
  type Difficulty,
  type DraftSection,
  type GeneratedQuestionResult,
  type GraphNode,
  type PaperTemplate,
  type QuestionType,
} from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import { cn } from "@/lib/utils";

const questionFormats: QuestionType[] = QUESTION_TYPE_ORDER;

interface SectionResult {
  sectionId: string;
  results: GeneratedQuestionResult[];
  error: string | null;
}

let sectionIdCounter = 0;
const newSectionId = () => `section-${Date.now()}-${++sectionIdCounter}`;

function makeSection(topics: GraphNode[]): DraftSection {
  return {
    id: newSectionId(),
    question_format: "short_answer",
    count: 3,
    topic_ids: topics[0] ? [topics[0].id] : [],
    difficulty: "medium",
    marks_per_question: DEFAULT_MARKS.short_answer,
    generated_question_ids: [],
  };
}

export function BuilderPage({ onSaved }: { onSaved: (blueprintId: string) => void }) {
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

  // Load topics + rehydrate any existing draft for this subject.
  useEffect(() => {
    if (!activeSubjectId) return;
    let cancelled = false;
    fetchGraph(activeSubjectId).then(async (g) => {
      if (cancelled) return;
      setTopics(g.nodes);

      const [draft, allQuestions] = await Promise.all([getDraft(activeSubjectId), fetchQuestions(activeSubjectId)]);
      if (cancelled) return;

      if (draft && draft.sections.length > 0) {
        draftIdRef.current = draft.id;
        setPaperName(draft.paper_name);
        setDuration(draft.duration_minutes ?? 90);
        setSections(draft.sections);

        const byId = new Map(allQuestions.map((q) => [q.id, q]));
        const rehydrated: SectionResult[] = draft.sections.map((s) => ({
          sectionId: s.id,
          error: null,
          results: s.generated_question_ids
            .map((qid) => byId.get(qid))
            .filter((q): q is NonNullable<typeof q> => Boolean(q))
            .map((q) => ({
              question: q,
              difficulty: {
                score: q.difficulty_score ?? 5,
                features: {},
                shap_contributions: null,
                method: "heuristic" as const,
              },
              duplicate_matches: [],
            })),
        }));
        if (rehydrated.some((r) => r.results.length > 0)) {
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
        count: ts.count,
        topic_ids: [],
        difficulty: ts.difficulty,
        marks_per_question: ts.marks_per_question,
        generated_question_ids: [],
      }))
    );
    if (template.duration_minutes != null) setDuration(template.duration_minutes);
    setSectionResults([]);
    setHasGenerated(false);
  };

  const handleSaveTemplate = async () => {
    if (!savingTemplateName || !savingTemplateName.trim() || sections.length === 0) return;
    setSavingTemplate(true);
    try {
      const template = await createTemplate({
        name: savingTemplateName.trim(),
        duration_minutes: duration,
        sections: sections.map((s) => ({
          question_format: s.question_format,
          count: s.count,
          difficulty: s.difficulty,
          marks_per_question: s.marks_per_question,
        })),
      });
      setTemplates((prev) => [template, ...prev]);
      setSavingTemplateName(null);
    } finally {
      setSavingTemplate(false);
    }
  };

  const topicName = (id: string) => topics.find((t) => t.id === id)?.name ?? id;

  const plannedQuestions = sections.reduce((s, sec) => s + sec.count, 0);
  const plannedMarks = sections.reduce((s, sec) => s + sec.count * sec.marks_per_question, 0);

  const runSection = async (section: DraftSection): Promise<SectionResult> => {
    if (!activeSubjectId || section.topic_ids.length === 0) {
      return { sectionId: section.id, results: [], error: "Select at least one topic" };
    }
    try {
      const { results } = await generateSection({
        subject_id: activeSubjectId,
        topic_ids: section.topic_ids,
        question_type: section.question_format,
        num_questions: section.count,
        difficulty: section.difficulty,
        marks: section.marks_per_question,
        check_duplicates: true,
        save_to_bank: true,
      });
      persistGeneratedIds(section.id, results.map((r) => r.question.id));
      return { sectionId: section.id, results, error: results.length === 0 ? "No questions returned" : null };
    } catch (e) {
      return { sectionId: section.id, results: [], error: e instanceof Error ? e.message : "Generation failed" };
    }
  };

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

  const finalQuestions = sectionResults.flatMap((r) => r.results.map((res) => res.question)).filter((q) => !excludedIds.has(q.id));
  const finalMarks = finalQuestions.reduce((s, q) => s + q.marks, 0);
  const anySectionError = sectionResults.some((r) => r.error);

  const handleSavePaper = async () => {
    if (finalQuestions.length === 0 || !activeSubjectId) return;
    setSaving(true);
    try {
      const blueprintSections = sections.map((sec) => {
        const sr = sectionResults.find((r) => r.sectionId === sec.id);
        const ids = (sr?.results ?? []).map((r) => r.question.id).filter((id) => !excludedIds.has(id));
        return {
          title: `${QUESTION_TYPE_LABELS[sec.question_format]} — ${sec.topic_ids.map(topicName).join(", ")}`,
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

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">Questions</label>
                    <Input
                      type="number"
                      min={1}
                      value={section.count}
                      onChange={(e) => updateSection(section.id, "count", Math.max(1, Number(e.target.value)))}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">Marks each</label>
                    <Input
                      type="number"
                      min={1}
                      value={section.marks_per_question}
                      onChange={(e) => updateSection(section.id, "marks_per_question", Math.max(1, Number(e.target.value)))}
                    />
                  </div>
                </div>

                <p className="text-[11px] text-muted-foreground">
                  = {section.count} question{section.count !== 1 && "s"} · {section.count * section.marks_per_question} marks
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
                        {section.topic_ids.map(topicName).join(", ")} · {DIFFICULTY_LABELS[section.difficulty]} · {section.marks_per_question} marks each
                      </CardDescription>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => regenerateSection(sr.sectionId)} disabled={regeneratingSection === sr.sectionId}>
                      <RefreshCw className={cn("h-3.5 w-3.5", regeneratingSection === sr.sectionId && "animate-spin")} /> Regenerate
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {sr.error && (
                      <p className="flex items-center gap-1.5 text-xs text-destructive">
                        <AlertTriangle className="h-3.5 w-3.5" /> {sr.error}
                      </p>
                    )}
                    {sr.results.map((res) => {
                      const excluded = excludedIds.has(res.question.id);
                      const bestMatch = res.duplicate_matches[0];
                      const isDuplicate = Boolean(bestMatch?.is_duplicate);
                      const bucket = difficultyBucket(res.question.difficulty_score);
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
                            <p className="text-sm text-foreground">{res.question.text}</p>
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
