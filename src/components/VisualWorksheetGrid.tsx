import { useImageUrl, type GridItem, type GridLayout } from "@/lib/api";
import { cn } from "@/lib/utils";

function GridCell({ item, responseStyle, showAnswers }: { item: GridItem; responseStyle: GridLayout["response_style"]; showAnswers: boolean }) {
  const url = useImageUrl(item.visual.image_id);
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-md border border-border p-2">
      <div className="flex h-20 w-full items-center justify-center overflow-hidden rounded bg-secondary/40">
        {url ? (
          <img src={url} alt={item.visual.subject} className="h-full w-full object-contain" />
        ) : (
          <span className="text-[10px] text-muted-foreground">{item.visual.subject}</span>
        )}
      </div>
      {item.label && <p className="text-xs text-foreground">{item.label}</p>}
      {responseStyle === "circle_choice" && (
        <span className={cn("text-lg leading-none", showAnswers && item.is_correct && "text-success")}>◯</span>
      )}
      {responseStyle === "blank_line" && <span className="w-full border-b border-foreground/40 pt-2" />}
      {showAnswers && item.is_correct && <span className="text-[10px] font-medium text-success">Correct</span>}
    </div>
  );
}

/** Renders a visual_worksheet question's grid of images (LKG/UKG format), mirroring
 *  MatchFollowingTable.tsx's {question, showAnswers?} shape. Images are fetched
 *  authenticated via useImageUrl since <img src> can't carry a bearer token. */
export function VisualWorksheetGrid({ layout, showAnswers = false }: { layout: GridLayout; showAnswers?: boolean }) {
  const cols = layout.kind === "grid_2x4" ? 4 : layout.kind === "two_column_match" ? 2 : layout.items.length || 1;

  return (
    <div className="mt-2 space-y-2">
      {layout.instruction && <p className="text-xs font-medium text-muted-foreground">{layout.instruction}</p>}
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {layout.items.map((item, i) => (
          <GridCell key={i} item={item} responseStyle={layout.response_style} showAnswers={showAnswers} />
        ))}
      </div>
    </div>
  );
}
