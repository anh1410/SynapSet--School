import { Plus, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { MatchPair, Question } from "@/lib/api";

const textareaClass =
  "flex w-full rounded-lg border border-input bg-white px-3 py-1.5 text-sm shadow-subtle transition-all duration-200 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-primary";

/** Inline editor for a single question, UI switched by question_type.
 *  Used both in the Builder's post-generation review cards and in Review & Export's inline editing. */
export function QuestionEditor({
  question,
  onChange,
}: {
  question: Question;
  onChange: (next: Question) => void;
}) {
  const update = (patch: Partial<Question>) => onChange({ ...question, ...patch });

  const updateOption = (index: number, value: string) => {
    const options = [...(question.options ?? [])];
    options[index] = value;
    update({ options });
  };

  const updatePair = (index: number, patch: Partial<MatchPair>) => {
    const pairs = [...(question.match_pairs ?? [])];
    pairs[index] = { ...pairs[index], ...patch };
    update({ match_pairs: pairs });
  };

  const addPair = () => update({ match_pairs: [...(question.match_pairs ?? []), { left: "", right: "" }] });
  const removePair = (index: number) =>
    update({ match_pairs: (question.match_pairs ?? []).filter((_, i) => i !== index) });

  return (
    <div className="space-y-2.5">
      <textarea
        className={textareaClass}
        rows={2}
        value={question.text}
        onChange={(e) => update({ text: e.target.value })}
      />

      {question.question_type === "mcq" && (
        <div className="space-y-1.5">
          {(question.options ?? ["", "", "", ""]).map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-4 text-xs text-muted-foreground">{String.fromCharCode(97 + i)})</span>
              <Input value={opt} onChange={(e) => updateOption(i, e.target.value)} className="flex-1" />
              <button
                type="button"
                onClick={() => update({ correct_answer: opt })}
                title="Mark as correct"
                className={`h-6 w-6 shrink-0 rounded-full border text-[10px] font-semibold ${
                  question.correct_answer === opt
                    ? "border-success bg-success/10 text-success"
                    : "border-border text-muted-foreground hover:border-success/50"
                }`}
              >
                ✓
              </button>
            </div>
          ))}
        </div>
      )}

      {(question.question_type === "short_answer" ||
        question.question_type === "long_answer" ||
        question.question_type === "numerical" ||
        question.question_type === "fill_in_blank") && (
        <div>
          <label className="mb-1 block text-[11px] font-medium text-muted-foreground">
            {question.question_type === "fill_in_blank" ? "Blank answer" : "Model answer"}
          </label>
          <textarea
            className={textareaClass}
            rows={question.question_type === "long_answer" ? 3 : 1}
            value={question.correct_answer ?? ""}
            onChange={(e) => update({ correct_answer: e.target.value })}
          />
        </div>
      )}

      {question.question_type === "true_false" && (
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant={question.is_true === true ? "primary" : "outline"}
            onClick={() => update({ is_true: true })}
          >
            True
          </Button>
          <Button
            type="button"
            size="sm"
            variant={question.is_true === false ? "primary" : "outline"}
            onClick={() => update({ is_true: false })}
          >
            False
          </Button>
        </div>
      )}

      {question.question_type === "match_following" && (
        <div className="space-y-1.5">
          {(question.match_pairs ?? []).map((pair, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input value={pair.left} onChange={(e) => updatePair(i, { left: e.target.value })} className="flex-1" />
              <span className="text-xs text-muted-foreground">→</span>
              <Input value={pair.right} onChange={(e) => updatePair(i, { right: e.target.value })} className="flex-1" />
              <button
                type="button"
                onClick={() => removePair(i)}
                className="shrink-0 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={addPair}>
            <Plus className="h-3.5 w-3.5" /> Add pair
          </Button>
        </div>
      )}
    </div>
  );
}
