import {
  Trash2,
  PlusCircle,
  CircleDollarSign,
  CalendarClock,
  TrendingUp,
  TrendingDown,
  type LucideIcon,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import type { ChangeLabel } from "../../data/negotiation";

// 변경 라벨은 색상 + 아이콘 + 텍스트로 구분한다 (색상만으로 구분하지 않음).
const config: Record<ChangeLabel, { icon: LucideIcon; color: string; bg: string; key: string }> = {
  deleted: { icon: Trash2, color: "var(--coral)", bg: "var(--coral-soft)", key: "chg.deleted" },
  added: { icon: PlusCircle, color: "var(--teal)", bg: "var(--success-soft)", key: "chg.added" },
  priceChange: { icon: CircleDollarSign, color: "var(--ocean)", bg: "var(--info-soft)", key: "chg.price" },
  periodChange: { icon: CalendarClock, color: "var(--ocean)", bg: "var(--info-soft)", key: "chg.period" },
  riskUp: { icon: TrendingUp, color: "var(--warning)", bg: "var(--warning-soft)", key: "chg.riskUp" },
  riskDown: { icon: TrendingDown, color: "var(--success)", bg: "var(--success-soft)", key: "chg.riskDown" },
};

export function ChangeLabelBadge({ label }: { label: ChangeLabel }) {
  const { t } = useApp();
  const { icon: Icon, color, bg, key } = config[label];
  return (
    <span
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5"
      style={{ background: bg, color, fontSize: "11px", fontWeight: 600 }}
    >
      <Icon className="size-3" />
      {t(key)}
    </span>
  );
}
