import { useImageUrl, type DiagramSpec } from "@/lib/api";

/** Renders a stem_diagram question's rendered image, or the render error /
 *  source code as a fallback when rendering failed server-side. */
export function DiagramImage({ diagram }: { diagram: DiagramSpec }) {
  const url = useImageUrl(diagram.image_id);

  if (diagram.render_error) {
    return (
      <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
        Diagram failed to render: {diagram.render_error}
      </div>
    );
  }

  if (!url) return null;

  return (
    <figure className="mt-2 max-w-xs">
      <img src={url} alt={diagram.caption ?? "diagram"} className="rounded-md border border-border" />
      {diagram.caption && <figcaption className="mt-1 text-[11px] text-muted-foreground">{diagram.caption}</figcaption>}
    </figure>
  );
}
