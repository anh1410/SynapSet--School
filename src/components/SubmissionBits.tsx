import { CheckCircle2, Clock, MessageSquareWarning, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  SUBMISSION_STATUS_LABELS,
  timeAgo,
  type Submission,
  type SubmissionEvent,
  type SubmissionStatus,
} from "@/lib/api";

const STATUS_VARIANT: Record<SubmissionStatus, "warning" | "default" | "success" | "destructive"> = {
  submitted: "warning",
  changes_requested: "default",
  accepted: "success",
  rejected: "destructive",
};

const STATUS_ICON = {
  submitted: Clock,
  changes_requested: MessageSquareWarning,
  accepted: CheckCircle2,
  rejected: XCircle,
} as const;

export function StatusBadge({ status }: { status: SubmissionStatus }) {
  const Icon = STATUS_ICON[status];
  return (
    <Badge variant={STATUS_VARIANT[status]}>
      <Icon className="h-3 w-3" />
      {SUBMISSION_STATUS_LABELS[status]}
    </Badge>
  );
}

const EVENT_LABEL: Record<SubmissionEvent["kind"], string> = {
  submitted: "submitted this question",
  edited: "edited it",  // an admin fixing a waiting question, or the teacher revising their own
  resubmitted: "revised it and resubmitted",
  changes_requested: "asked for changes",
  accepted: "accepted it into the bank",
  rejected: "rejected it",
};

/** Who did what, newest last - the audit trail an admin or teacher can read at a glance. */
export function SubmissionHistory({ history }: { history: Submission["history"] }) {
  return (
    <ol className="space-y-2 border-l border-border pl-3">
      {history.map((ev, i) => (
        <li key={i} className="text-xs">
          <p className="text-foreground">
            <span className="font-medium">{ev.by_name}</span> {EVENT_LABEL[ev.kind]}
            <span className="ml-1.5 text-muted-foreground">{timeAgo(ev.at)}</span>
          </p>
          {ev.comment && <p className="mt-0.5 whitespace-pre-wrap text-muted-foreground">“{ev.comment}”</p>}
        </li>
      ))}
    </ol>
  );
}
