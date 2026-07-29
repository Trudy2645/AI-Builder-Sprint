import {
  Clock,
  MessageSquareReply,
  MessagesSquare,
  PenLine,
  CheckCircle2,
  XCircle,
  FilePenLine,
  type LucideIcon,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import type { RequestStatus } from "../../store/RequestsContext";

const config: Record<RequestStatus, { icon: LucideIcon; color: string; bg: string }> = {
  draft: { icon: FilePenLine, color: "var(--muted-foreground)", bg: "var(--muted)" },
  reviewing: { icon: Clock, color: "var(--warning)", bg: "var(--warning-soft)" },
  responded: { icon: MessageSquareReply, color: "var(--ocean)", bg: "var(--info-soft)" },
  negotiating: { icon: MessagesSquare, color: "var(--teal)", bg: "var(--success-soft)" },
  signing: { icon: PenLine, color: "var(--navy)", bg: "var(--info-soft)" },
  completed: { icon: CheckCircle2, color: "var(--success)", bg: "var(--success-soft)" },
  closed: { icon: XCircle, color: "var(--muted-foreground)", bg: "var(--muted)" },
};

export function StatusBadge({ status }: { status: RequestStatus }) {
  const { t } = useApp();
  const { icon: Icon, color, bg } = config[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1"
      style={{ background: bg, color, fontSize: "12px", fontWeight: 600 }}
    >
      <Icon className="size-3.5 shrink-0" />
      {t(status === "draft" ? "lstatus.draft" : `rstatus.${status}`)}
    </span>
  );
}
