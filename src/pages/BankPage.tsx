import { Fragment, useEffect, useMemo, useState } from "react";
import { Search, Trash2, Library, FileStack } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  BLOOM_LABELS,
  QUESTION_TYPE_LABELS,
  QUESTION_TYPE_ORDER,
  bulkDeleteQuestions,
  createBlueprint,
  deleteQuestion,
  difficultyBucket,
  fetchGraph,
  fetchQuestions,
  listTeachers,
  type DifficultyBucket,
  type GraphNode,
  type Question,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/AuthContext";

const difficultyVariant: Record<DifficultyBucket, "success" | "warning" | "destructive"> = {
  Easy: "success",
  Medium: "warning",
  Hard: "destructive",
};

export function BankPage({
  initialSearch,
  onPaperCreated,
}: {
  initialSearch?: string;
  onPaperCreated: (blueprintId: string) => void;
}) {
  const { activeSubjectId } = useAuth();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [topics, setTopics] = useState<GraphNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(initialSearch ?? "");
  const [topicFilter, setTopicFilter] = useState("all");
  const [difficultyFilter, setDifficultyFilter] = useState("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [creatingPaper, setCreatingPaper] = useState(false);
  const [authors, setAuthors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (initialSearch !== undefined) setSearch(initialSearch);
  }, [initialSearch]);

  // who wrote the teacher-submitted questions, shown under the question text
  useEffect(() => {
    listTeachers()
      .then((ts) => setAuthors(Object.fromEntries(ts.map((t) => [t.id, t.name]))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!activeSubjectId) return;
    Promise.all([
      fetchQuestions(activeSubjectId).then(setQuestions),
      fetchGraph(activeSubjectId).then((g) => setTopics(g.nodes)),
    ]).finally(() => setLoading(false));
  }, [activeSubjectId]);

  const topicName = useMemo(() => {
    const map = new Map(topics.map((t) => [t.id, t.name]));
    return (id: string) => map.get(id) ?? id;
  }, [topics]);

  const filtered = questions.filter((q) => {
    if (search && !q.text.toLowerCase().includes(search.toLowerCase())) return false;
    if (topicFilter !== "all" && !q.topic_ids.includes(topicFilter)) return false;
    if (difficultyFilter !== "all" && difficultyBucket(q.difficulty_score) !== difficultyFilter) return false;
    return true;
  });

  // Grouped by question type (in a fixed order) so rows of the same format
  // always sit together instead of being interleaved by creation order.
  const groups = QUESTION_TYPE_ORDER.map((type) => ({
    type,
    questions: filtered.filter((q) => q.question_type === type),
  })).filter((g) => g.questions.length > 0);

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const allFilteredSelected = filtered.length > 0 && filtered.every((q) => selected.includes(q.id));

  const toggleSelectAll = () =>
    setSelected((s) => {
      if (allFilteredSelected) return s.filter((id) => !filtered.some((q) => q.id === id));
      const filteredIds = filtered.map((q) => q.id);
      return [...new Set([...s, ...filteredIds])];
    });

  const handleDelete = async (id: string) => {
    await deleteQuestion(id);
    setQuestions((qs) => qs.filter((q) => q.id !== id));
    setSelected((s) => s.filter((x) => x !== id));
  };

  const handleBulkDelete = async () => {
    const { deleted } = await bulkDeleteQuestions(selected);
    setQuestions((qs) => qs.filter((q) => !deleted.includes(q.id)));
    setSelected((s) => s.filter((id) => !deleted.includes(id)));
  };

  const handleCreatePaper = async () => {
    if (!activeSubjectId || selected.length === 0) return;
    setCreatingPaper(true);
    try {
      const chosen = questions.filter((q) => selected.includes(q.id));
      const byType = QUESTION_TYPE_ORDER.map((type) => ({
        type,
        ids: chosen.filter((q) => q.question_type === type).map((q) => q.id),
      })).filter((g) => g.ids.length > 0);

      const blueprint = await createBlueprint({
        subject_id: activeSubjectId,
        name: `Paper from Question Bank — ${new Date().toLocaleDateString()}`,
        total_marks: chosen.reduce((s, q) => s + q.marks, 0),
        sections: byType.map((g) => ({
          title: QUESTION_TYPE_LABELS[g.type],
          question_format: g.type,
          question_ids: g.ids,
        })),
      });
      setSelected([]);
      onPaperCreated(blueprint.id);
    } finally {
      setCreatingPaper(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search questions..."
              className="pl-8"
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:w-auto">
            <Select value={topicFilter} onChange={(e) => setTopicFilter(e.target.value)} className="sm:w-44">
              <option value="all">All topics</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </Select>
            <Select value={difficultyFilter} onChange={(e) => setDifficultyFilter(e.target.value)} className="sm:w-36">
              <option value="all">All difficulty</option>
              <option value="Easy">Easy</option>
              <option value="Medium">Medium</option>
              <option value="Hard">Hard</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {selected.length > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-primary/20 bg-accent px-4 py-2.5 text-sm animate-fade-in">
          <span className="font-medium text-accent-foreground">{selected.length} selected</span>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={handleCreatePaper} disabled={creatingPaper}>
              <FileStack className="h-3.5 w-3.5" /> {creatingPaper ? "Creating..." : "Create Paper from Selected"}
            </Button>
            <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={handleBulkDelete}>
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
          </div>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          {questions.length === 0 ? (
            <EmptyState
              icon={Library}
              title="No questions yet"
              description="Generate questions from your uploaded material to build your bank."
              className="m-6"
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={Library}
              title="No questions found"
              description="Try adjusting your filters or generate new questions for this topic."
              className="m-6"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-y border-border bg-secondary/40 text-left text-xs text-muted-foreground">
                    <th className="w-10 px-6 py-2.5">
                      <Checkbox checked={allFilteredSelected} onCheckedChange={toggleSelectAll} />
                    </th>
                    <th className="px-2 py-2.5 font-medium">Question</th>
                    <th className="px-4 py-2.5 font-medium">Topic</th>
                    <th className="px-4 py-2.5 font-medium">Difficulty</th>
                    <th className="px-4 py-2.5 font-medium">Marks</th>
                    <th className="px-4 py-2.5 font-medium">Bloom's</th>
                    <th className="px-4 py-2.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group) => (
                    <Fragment key={group.type}>
                      <tr className="border-b border-border bg-secondary/60">
                        <td colSpan={7} className="px-6 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-primary">
                          {QUESTION_TYPE_LABELS[group.type]} ({group.questions.length})
                        </td>
                      </tr>
                      {group.questions.map((q) => {
                        const bucket = difficultyBucket(q.difficulty_score);
                        return (
                          <tr
                            key={q.id}
                            className={cn(
                              "border-b border-border last:border-0 transition-colors duration-150 hover:bg-secondary/30",
                              selected.includes(q.id) && "bg-accent/50"
                            )}
                          >
                            <td className="px-6 py-3">
                              <Checkbox checked={selected.includes(q.id)} onCheckedChange={() => toggle(q.id)} />
                            </td>
                            <td className="max-w-md px-2 py-3">
                              <p className="line-clamp-2 text-foreground">{q.text}</p>
                              {q.author_id && authors[q.author_id] && (
                                <p className="mt-0.5 text-[11px] text-muted-foreground">By {authors[q.author_id]}</p>
                              )}
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">
                              {q.topic_ids.length > 0 ? q.topic_ids.map(topicName).join(", ") : "—"}
                            </td>
                            <td className="px-4 py-3">
                              <Badge variant={difficultyVariant[bucket]}>{bucket}</Badge>
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">{q.marks}</td>
                            <td className="px-4 py-3">
                              <Badge variant="accent">{BLOOM_LABELS[q.bloom_level]}</Badge>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-destructive hover:text-destructive"
                                  onClick={() => handleDelete(q.id)}
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Showing {filtered.length} of {questions.length} questions
      </p>
    </div>
  );
}
