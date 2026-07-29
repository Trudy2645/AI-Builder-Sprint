import {
  MapPin,
  CalendarDays,
  Package,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Eye,
} from "lucide-react";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Switch } from "../ui/switch";
import { Badge } from "../ui/badge";
import { Separator } from "../ui/separator";
import { useApp } from "../../context/AppContext";
import { CATEGORIES, formatKRW } from "../../data/contracts";
import { analyzeDraft } from "./RiskReviewStep";
import type { ListingDraft } from "../../store/ListingsContext";

const catKey = (c: ListingDraft["category"]) =>
  CATEGORIES.find((x) => x.value === c)?.labelKey ?? "cat.all";

function ToggleRow({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border py-4 last:border-b-0">
      <div className="min-w-0">
        <div style={{ fontSize: "14px", fontWeight: 600 }}>{label}</div>
        <p className="mt-0.5 text-muted-foreground" style={{ fontSize: "12px" }}>{desc}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} className="mt-0.5 shrink-0" />
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2" style={{ fontSize: "13px" }}>
      <span className="whitespace-nowrap text-muted-foreground">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}

/** 오른쪽 실시간 미리보기: 바이어 계약 카드 + 요약 화면. */
function BuyerPreview({ draft }: { draft: ListingDraft }) {
  const { t } = useApp();
  const risks = analyzeDraft(draft).length;
  const price = parseInt(draft.unitPrice, 10) || 0;
  const period =
    draft.start && draft.end ? `${draft.start} ~ ${draft.end}` : t("wz.tbd");
  const title = draft.productName || t("lf.productName");

  return (
    <div className="flex flex-col gap-5">
      {/* Contract card preview */}
      <div>
        <div className="mb-2 flex items-center gap-1.5 whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>
          <Eye className="size-3.5" />
          {t("pub.previewCard")}
        </div>
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="flex items-center justify-center" style={{ height: "96px", background: "var(--info-soft)" }}>
            <Package className="size-8" style={{ color: "var(--ocean)" }} />
          </div>
          <div className="flex flex-col gap-2 p-4">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>
                {t(catKey(draft.category))}
              </Badge>
              {draft.district && (
                <span className="flex items-center gap-1 whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>
                  <MapPin className="size-3.5" />
                  {draft.district}
                </span>
              )}
              {draft.available ? (
                <Badge className="ml-auto gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--success)", color: "#fff" }}>
                  <CheckCircle2 className="size-3" />
                  {t("status.available")}
                </Badge>
              ) : (
                <Badge className="ml-auto gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--muted-foreground)", color: "#fff" }}>
                  <XCircle className="size-3" />
                  {t("status.closed")}
                </Badge>
              )}
            </div>
            <h3 className="line-clamp-2" style={{ color: "var(--navy)" }}>{title}</h3>
            <div className="flex flex-col gap-1 text-muted-foreground" style={{ fontSize: "13px" }}>
              <span className="flex items-center gap-1.5">
                <CalendarDays className="size-4 shrink-0" />
                <span className="whitespace-nowrap">{period}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <Package className="size-4 shrink-0" />
                <span className="whitespace-nowrap">{draft.quantity || t("wz.tbd")}</span>
              </span>
            </div>
            <div>
              <span className="text-muted-foreground" style={{ fontSize: "12px" }}>{draft.priceUnit} </span>
              <span style={{ color: "var(--navy)", fontWeight: 700, fontSize: "18px" }}>{formatKRW(price)}</span>
            </div>
            {draft.headline && (
              <div className="rounded-lg p-2.5" style={{ background: "var(--info-soft)" }}>
                <div className="flex items-center gap-1 whitespace-nowrap" style={{ color: "var(--ocean)", fontSize: "12px", fontWeight: 600 }}>
                  <Sparkles className="size-3.5" />
                  {t("card.aiSummary")}
                </div>
                <p className="mt-1 line-clamp-2 text-foreground" style={{ fontSize: "13px", lineHeight: 1.5 }}>{draft.headline}</p>
              </div>
            )}
            {draft.showRisk && risks > 0 && (
              <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--coral)", fontSize: "13px" }}>
                <AlertTriangle className="size-4" />
                {t("card.riskClauses")} {risks}{t("card.riskUnit")}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Summary preview */}
      <div>
        <div className="mb-2 flex items-center gap-1.5 whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>
          <Eye className="size-3.5" />
          {t("pub.previewSummary")}
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <SummaryRow label={t("summary.period")} value={period} />
          <Separator />
          <SummaryRow label={t("summary.quantity")} value={draft.quantity || t("wz.tbd")} />
          <Separator />
          <SummaryRow label={t("summary.unitPrice")} value={`${draft.priceUnit} ${formatKRW(price)}`} />
          <Separator />
          <SummaryRow label={t("summary.cancellation")} value={draft.cancellation || t("wz.tbd")} />
          <Separator />
          <SummaryRow label={t("summary.noShow")} value={draft.noShow || t("wz.tbd")} />
          <Separator />
          <SummaryRow label={t("summary.settlement")} value={draft.settlement || t("wz.tbd")} />
        </div>
      </div>
    </div>
  );
}

interface PublishSettingsStepProps {
  draft: ListingDraft;
  onChange: (patch: Partial<ListingDraft>) => void;
}

export function PublishSettingsStep({ draft, onChange }: PublishSettingsStepProps) {
  const { t } = useApp();

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      {/* Left: settings form */}
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="headline">{t("pub.headline")}</Label>
          <Textarea
            id="headline"
            rows={3}
            value={draft.headline}
            placeholder={t("pub.headlinePh")}
            onChange={(e) => onChange({ headline: e.target.value })}
          />
        </div>

        <div className="mt-4">
          <ToggleRow
            label={t("pub.available")}
            desc={t("pub.availableDesc")}
            checked={draft.available}
            onChange={(v) => onChange({ available: v })}
          />
          <ToggleRow
            label={t("pub.showRisk")}
            desc={t("pub.showRiskDesc")}
            checked={draft.showRisk}
            onChange={(v) => onChange({ showRisk: v })}
          />
        </div>
      </div>

      {/* Right: live preview */}
      <div>
        <div className="xl:sticky xl:top-6">
          <div className="mb-3 flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 700 }}>
            <Eye className="size-4" />
            {t("pub.previewTitle")}
          </div>
          <BuyerPreview draft={draft} />
        </div>
      </div>
    </div>
  );
}
