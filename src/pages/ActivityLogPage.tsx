import { useCallback, useEffect, useState } from "react";
import { ScrollText, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { AUDIT_AREAS, listAudit, listTeachers, type AdminTeacher, type AuditEntry } from "@/lib/api";

const PAGE_SIZE = 50;

const VERB_VARIANT: Record<string, "destructive" | "success" | "warning" | "default" | "secondary"> = {
  delete: "destructive",
  reject: "destructive",
  accept: "success",
  create: "success",
  export: "success",
  edit: "warning",
  update: "warning",
  request_changes: "warning",
  subjects: "warning",
};

function ActionBadge({ action }: { action: string }) {
  const [area, verb] = action.split(".");
  const label = AUDIT_AREAS.find((a) => a.id === area)?.label ?? area;
  return (
    <Badge variant={VERB_VARIANT[verb] ?? "secondary"} title={action}>
      {label} · {verb.replace("_", " ")}
    </Badge>
  );
}

/** Admin-only trail of who changed what: bank deletions and edits, paper changes,
 *  submission decisions, teacher and subject changes. Newest first. */
export function ActivityLogPage() {
  const [items, setItems] = useState<AuditEntry[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [area, setArea] = useState("");
  const [actorId, setActorId] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [people, setPeople] = useState<AdminTeacher[]>([]);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 250);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    listTeachers()
      .then(setPeople)
      .catch(() => setPeople([]));
  }, []);

  const filters = { area: area || undefined, actor_id: actorId || undefined, q: debounced || undefined };

  const load = useCallback(() => {
    setItems(null);
    listAudit({ area: area || undefined, actor_id: actorId || undefined, q: debounced || undefined, limit: PAGE_SIZE })
      .then((page) => {
        setItems(page.items);
        setHasMore(page.has_more);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load the activity log."));
  }, [area, actorId, debounced]);

  useEffect(load, [load]);

  const loadMore = async () => {
    if (!items || items.length === 0) return;
    setLoadingMore(true);
    try {
      const page = await listAudit({ ...filters, before: items[items.length - 1].at, limit: PAGE_SIZE });
      setItems([...items, ...page.items]);
      setHasMore(page.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load more.");
    } finally {
      setLoadingMore(false);
    }
  };

  const hasFilters = !!(area || actorId || search);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-foreground">Activity Log</h1>
        <p className="text-sm text-muted-foreground">Who changed what in the school, newest first. Only admins can see this.</p>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" placeholder="Search the log…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Select value={area} onChange={(e) => setArea(e.target.value)}>
          <option value="">Everything</option>
          {AUDIT_AREAS.map((a) => (
            <option key={a.id} value={a.id}>
              {a.label}
            </option>
          ))}
        </Select>
        <Select value={actorId} onChange={(e) => setActorId(e.target.value)}>
          <option value="">Everyone</option>
          {people.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
              {t.role === "admin" ? " (admin)" : ""}
            </option>
          ))}
        </Select>
      </div>
      {hasFilters && (
        <button
          className="text-xs text-primary hover:underline"
          onClick={() => {
            setArea("");
            setActorId("");
            setSearch("");
          }}
        >
          Clear filters
        </button>
      )}

      {error && <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p>}

      {items === null && !error ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : (items ?? []).length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title={hasFilters ? "Nothing matches these filters" : "Nothing logged yet"}
          description={
            hasFilters ? "Try clearing a filter." : "Changes made from now on, like deleting a question or exporting a paper, show up here."
          }
        />
      ) : (
        <Card>
          <CardContent className="divide-y divide-border p-0">
            {(items ?? []).map((e) => (
              <div key={e.id} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3">
                <div className="w-40 shrink-0 text-xs text-muted-foreground">
                  {new Date(e.at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-sm text-foreground">{e.summary}</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <ActionBadge action={e.action} />
                    <span className="text-xs text-muted-foreground">by {e.actor_name}</span>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {hasMore && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
            {loadingMore ? "Loading…" : "Load older entries"}
          </Button>
        </div>
      )}
    </div>
  );
}
