import { matchColumns, type Question } from "@/lib/api";

/** Two-column "Column A / Column B" layout for match-the-following questions,
 *  matching the exported PDF/DOCX layout. Column B is pre-shuffled server-side
 *  (match_right_order) so it isn't just Column A's answers in order. */
export function MatchFollowingTable({ question, showAnswers = false }: { question: Question; showAnswers?: boolean }) {
  const { columnA, columnB, correctLetter } = matchColumns(question);
  const rows = Math.max(columnA.length, columnB.length);

  return (
    <div className="mt-2 overflow-hidden rounded-md border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-warning/20">
            <th className="border-r border-border px-2 py-1 text-left font-semibold text-foreground">Column A</th>
            <th className="px-2 py-1 text-left font-semibold text-foreground">Column B</th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <tr key={i} className="border-t border-border">
              <td className="border-r border-border px-2 py-1 text-foreground">
                {columnA[i] ? `${columnA[i].label} ${columnA[i].text}` : ""}
              </td>
              <td className="px-2 py-1 text-foreground">{columnB[i] ? `${columnB[i].label} ${columnB[i].text}` : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {showAnswers && (
        <p className="border-t border-border bg-success/5 px-2 py-1 text-xs font-medium text-success">
          Answer: {columnA.map((a, i) => `${a.label} → ${correctLetter[i]}`).join(", ")}
        </p>
      )}
    </div>
  );
}
