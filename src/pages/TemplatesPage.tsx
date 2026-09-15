import { useEffect, useState } from "react";
import { LayoutTemplate, Trash2, Clock, ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  DIFFICULTY_LABELS,
  QUESTION_TYPE_LABELS,
  deleteTemplate,
  listTemplates,
  type PaperTemplate,
  type TemplateSection,
} from "@/lib/api";

function sectionSummary(section: TemplateSection): string {
  const format = QUESTION_TYPE_LABELS[section.question_format];
  if (section.mode === "specific") {
    const n = section.difficulties.length;
    const mix = section.difficulties.map((d) => DIFFICULTY_LABELS[d]).join(", ");
    return `${format} · ${n} question${n !== 1 ? "s" : ""} · Specific (${mix || "no questions"})`;
  }
  return `${format} · ${section.count} question${section.count !== 1 ? "s" : ""} · Random (${DIFFICULTY_LABELS[section.difficulty]})`;
}

export function TemplatesPage({ onUseTemplate }: { onUseTemplate: (templateId: string) => void }) {
  const [templates, setTemplates] = useState<PaperTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteTemplate(id);
      setTemplates((ts) => ts.filter((t) => t.id !== id));
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Paper Templates</h1>
        <p className="text-sm text-muted-foreground">
          Reusable section patterns saved from the Question Paper Builder — load one to start a new paper from it.
        </p>
      </div>

      {templates.length === 0 ? (
        <Card>
          <CardContent className="p-0">
            <EmptyState
              icon={LayoutTemplate}
              title="No templates yet"
              description='Build a paper in the Question Paper Builder, then use "Save as Template" to reuse its section pattern later.'
              className="m-6"
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {templates.map((t) => (
            <Card key={t.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{t.name}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>
                        {t.sections.length} section{t.sections.length !== 1 && "s"}
                      </span>
                      {t.duration_minutes != null && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {t.duration_minutes} min
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => onUseTemplate(t.id)}>
                      Use in Builder <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      onClick={() => handleDelete(t.id)}
                      disabled={deletingId === t.id}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {t.sections.map((s, i) => (
                    <Badge key={i} variant="outline">
                      {sectionSummary(s)}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
