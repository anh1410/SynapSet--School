import { useState } from "react";
import { ChevronDown, Settings2, BookOpen } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { subjectLabel } from "@/lib/api";

export function SubjectSwitcher({ onManage }: { onManage: () => void }) {
  const { subjects, activeSubjectId, setActiveSubjectId } = useAuth();
  const [open, setOpen] = useState(false);

  const active = subjects.find((s) => s.id === activeSubjectId);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-lg border border-border bg-white px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-secondary/50"
      >
        <BookOpen className="h-3.5 w-3.5 text-primary" />
        <span className="max-w-[11rem] truncate">{active ? subjectLabel(active) : "No subject"}</span>
        <ChevronDown className="h-3 w-3 text-muted-foreground" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-1.5 max-h-80 w-64 overflow-y-auto rounded-lg border border-border bg-white py-1.5 shadow-lg animate-fade-in">
            {subjects.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setActiveSubjectId(s.id);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-secondary/60 ${
                  s.id === activeSubjectId ? "font-semibold text-primary" : "text-foreground"
                }`}
              >
                {subjectLabel(s)}
              </button>
            ))}
            {subjects.length > 0 && <div className="my-1 border-t border-border" />}
            <button
              onClick={() => {
                setOpen(false);
                onManage();
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-primary hover:bg-secondary/60"
            >
              <Settings2 className="h-3.5 w-3.5" />
              Manage subjects
            </button>
          </div>
        </>
      )}
    </div>
  );
}
