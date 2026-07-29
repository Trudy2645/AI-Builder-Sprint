import {
  FileEdit,
  Sparkles,
  Globe,
  PauseCircle,
  CalendarX,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "../ui/badge";
import { useApp } from "../../context/AppContext";
import type { ListingStatus } from "../../store/ListingsContext";

// 색상만으로 구분하지 않도록 아이콘 + 텍스트 라벨을 함께 표시한다.
const config: Record<ListingStatus, { icon: LucideIcon; color: string; bg: string }> = {
  draft: { icon: FileEdit, color: "var(--muted-foreground)", bg: "var(--muted)" },
  needsReview: { icon: Sparkles, color: "var(--warning)", bg: "var(--warning-soft)" },
  public: { icon: Globe, color: "var(--success)", bg: "var(--success-soft)" },
  paused: { icon: PauseCircle, color: "var(--ocean)", bg: "var(--info-soft)" },
  expired: { icon: CalendarX, color: "var(--coral)", bg: "var(--coral-soft)" },
};

export function ListingStatusBadge({ status }: { status: ListingStatus }) {
  const { t } = useApp();
  const { icon: Icon, color, bg } = config[status];
  return (
    <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: bg, color }}>
      <Icon className="size-3.5" />
      {t(`lstatus.${status}`)}
    </Badge>
  );
}
