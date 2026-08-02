import {
  MapPin,
  CalendarDays,
  Package,
  CheckCircle2,
  ImagePlus,
  Link,
} from "lucide-react";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Input } from "../ui/input";
import { Badge } from "../ui/badge";
import { Separator } from "../ui/separator";
import { useApp } from "../../context/AppContext";
import { CATEGORIES, formatKRW } from "../../data/contracts";
import type { ListingDraft } from "../../store/ListingsContext";

const catKey = (c: ListingDraft["category"]) =>
  CATEGORIES.find((x) => x.value === c)?.labelKey ?? "cat.all";

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2" style={{ fontSize: "13px" }}>
      <span className="whitespace-nowrap text-muted-foreground">{label}</span>
      <span className="max-w-[75%] whitespace-pre-wrap break-words text-right leading-5">{value}</span>
    </div>
  );
}

/** 오른쪽 실시간 미리보기: 바이어 계약 카드 + 요약 화면. */
function BuyerPreview({ draft }: { draft: ListingDraft }) {
  const { t } = useApp();
  const price = parseInt(draft.unitPrice, 10) || 0;
  const period =
    draft.availabilityStart && draft.availabilityEnd ? `${draft.availabilityStart} ~ ${draft.availabilityEnd}` : t("wz.tbd");
  const title = draft.productName || t("lf.productName");

  return (
    <div className="flex flex-col gap-5">
      {/* Contract card preview */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        {draft.imageUrl ? (
          <img
            src={draft.imageUrl}
            alt=""
            className="h-36 w-full object-cover"
          />
        ) : (
          <div className="flex h-36 items-center justify-center" style={{ background: "var(--info-soft)" }}>
            <ImagePlus className="size-8" style={{ color: "var(--ocean)" }} />
          </div>
        )}
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
              <Badge className="ml-auto gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--success)", color: "#fff" }}>
                <CheckCircle2 className="size-3" />
                {t("status.available")}
              </Badge>
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
                <div className="whitespace-nowrap" style={{ color: "var(--ocean)", fontSize: "12px", fontWeight: 700 }}>
                  계약 요약
                </div>
                <p className="mt-1 line-clamp-2 text-foreground" style={{ fontSize: "13px", lineHeight: 1.5 }}>{draft.headline}</p>
              </div>
            )}
          </div>
      </div>

      {/* Summary preview */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
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
  );
}

interface PublishSettingsStepProps {
  draft: ListingDraft;
  onChange: (patch: Partial<ListingDraft>) => void;
}

export function PublishSettingsStep({ draft, onChange }: PublishSettingsStepProps) {
  const { t } = useApp();
  const handleImageFile = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onChange({ imageUrl: String(reader.result) });
    reader.readAsDataURL(file);
  };

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      {/* Left: settings form */}
      <div className="flex flex-col gap-4">
        <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <div className="mb-4">
            <h3 style={{ color: "var(--navy)" }}>바이어 카드 편집</h3>
            <p className="mt-1 text-muted-foreground" style={{ fontSize: "13px" }}>
              바이어 계약 탐색 화면에 보이는 대표 이미지와 짧은 설명을 설정하세요.
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="imageUrl">대표 이미지 URL</Label>
            <div className="relative">
              <Link className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="imageUrl"
                className="pl-9"
                value={draft.imageUrl}
                placeholder="https://..."
                onChange={(e) => onChange({ imageUrl: e.target.value })}
              />
            </div>
          </div>

          <div className="mt-3 flex flex-col gap-1.5">
            <Label htmlFor="imageFile">또는 이미지 파일 선택</Label>
            <Input
              id="imageFile"
              type="file"
              accept="image/*"
              onChange={(e) => handleImageFile(e.target.files?.[0])}
            />
          </div>

          <div className="mt-4 flex flex-col gap-1.5">
            <Label htmlFor="headline">계약 요약</Label>
            <Textarea
              id="headline"
              rows={3}
              value={draft.headline}
              placeholder={t("pub.headlinePh")}
              onChange={(e) => onChange({ headline: e.target.value })}
            />
          </div>
        </div>

        <div className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          공고는 저장과 동시에 바이어에게 공개됩니다. 공개 여부를 따로 설정하지 않습니다.
        </div>
      </div>

      {/* Right: live preview */}
      <div>
        <div className="xl:sticky xl:top-6">
          <div className="mb-3">
            <h3 style={{ color: "var(--navy)" }}>바이어에게 보이는 화면</h3>
            <p className="mt-1 text-muted-foreground" style={{ fontSize: "13px" }}>
              왼쪽에서 수정한 내용이 카드와 계약 요약에 바로 반영됩니다.
            </p>
          </div>
          <BuyerPreview draft={draft} />
        </div>
      </div>
    </div>
  );
}
