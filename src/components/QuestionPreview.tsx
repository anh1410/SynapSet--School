import { Check } from "lucide-react";
import { DiagramImage } from "@/components/DiagramImage";
import { LatexText } from "@/components/LatexText";
import { MatchFollowingTable } from "@/components/MatchFollowingTable";
import { VisualWorksheetGrid } from "@/components/VisualWorksheetGrid";
import { cn } from "@/lib/utils";
import { toLetter, type Question } from "@/lib/api";

/** Read-only rendering of a question of any type, with its diagram / picture grid.
 *  Shared by the teacher's form preview, their submission list and the admin inbox. */
export function QuestionPreview({ question, showAnswer = true }: { question: Question; showAnswer?: boolean }) {
  const q = question;
  const isWorksheet = q.question_type === "visual_worksheet";

  return (
    <div className="space-y-1.5 text-sm text-foreground">
      {/* A worksheet's text is shown as the grid's instruction instead */}
      {!isWorksheet && (
        <p className="whitespace-pre-wrap">
          <LatexText text={q.text} />
        </p>
      )}

      {q.diagram && <DiagramImage diagram={q.diagram} />}

      {q.question_type === "mcq" && q.options && (
        <ul className="space-y-1">
          {q.options.map((opt, i) => {
            const correct = showAnswer && opt === q.correct_answer;
            return (
              <li
                key={i}
                className={cn(
                  "flex items-start gap-2 rounded-md px-2 py-1 text-xs",
                  correct ? "bg-success/10 text-success" : "text-foreground"
                )}
              >
                <span className="font-medium">{toLetter(i)})</span>
                <span className="flex-1">
                  <LatexText text={opt} />
                </span>
                {correct && <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
              </li>
            );
          })}
        </ul>
      )}

      {q.question_type === "match_following" && q.match_pairs && (
        <MatchFollowingTable question={q} showAnswers={showAnswer} />
      )}

      {isWorksheet && q.grid_layout && <VisualWorksheetGrid layout={q.grid_layout} showAnswers={showAnswer} />}

      {q.question_type === "true_false" && showAnswer && q.is_true != null && (
        <p className="text-xs font-medium text-success">Answer: {q.is_true ? "True" : "False"}</p>
      )}

      {q.question_type !== "mcq" && q.question_type !== "true_false" && showAnswer && q.correct_answer && (
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-success">Answer: </span>
          <LatexText text={q.correct_answer} />
        </p>
      )}
    </div>
  );
}
