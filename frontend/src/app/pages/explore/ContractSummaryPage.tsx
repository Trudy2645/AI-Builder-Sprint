import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CalendarDays,
  Coins,
  FileText,
  MapPin,
  Package,
  ShieldCheck,
  Sparkles,
  Star,
  UserX,
  UsersRound,
  Wallet,
} from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { ImageWithFallback } from "../../components/figma/ImageWithFallback";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../../components/ui/accordion";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { useApp } from "../../context/AppContext";
import { CATEGORIES } from "../../data/contracts";
import { useExploreCtx } from "../../hooks/useExploreCtx";
import {
  friendlyApiError,
  getPublicContractPreview,
  getPublicListingDetail,
  type PublicContractPreview,
  type PublicListingDetail,
} from "../../lib/api";

const localeByLanguage = { ko: "ko-KR", en: "en-US", ja: "ja-JP", zh: "zh-CN" } as const;

function DetailRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-border py-3 last:border-b-0">
      <span className="mt-0.5 shrink-0" style={{ color: "var(--ocean)" }}>{icon}</span>
      <div className="min-w-0">
        <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>{label}</div>
        <div className="text-foreground" style={{ fontSize: "14px" }}>{value}</div>
      </div>
    </div>
  );
}

export function ContractSummaryPage() {
  const { t, lang } = useApp();
  const { base } = useExploreCtx();
  const { id } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<PublicListingDetail | null>(null);
  const [preview, setPreview] = useState<PublicContractPreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    Promise.all([
      getPublicListingDetail(id, localeByLanguage[lang]),
      getPublicContractPreview(id, localeByLanguage[lang]),
    ])
      .then(([nextDetail, nextPreview]) => {
        if (!active) return;
        setDetail(nextDetail);
        setPreview(nextPreview);
      })
      .catch((reason: unknown) => active && setError(friendlyApiError(reason)));
    return () => { active = false; };
  }, [id, lang]);

  if (error) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{error}</div>;
  if (!detail || !preview) return <div className="rounded-xl border border-border bg-card p-16 text-center text-muted-foreground">AI 계약 정보를 불러오는 중입니다.</div>;

  const catKey = CATEGORIES.find((item) => item.value === detail.category)?.labelKey ?? "cat.all";
  const findingsByClause = new Map(preview.findings.filter((item) => item.clause_id).map((item) => [item.clause_id, item]));
  const summary = detail.ai_summary?.split("\n").map((line) => line.trim()).filter(Boolean) ?? [];
  const price = detail.base_price
    ? `${detail.base_price.amount_minor.toLocaleString("ko-KR")} ${detail.base_price.currency} · ${detail.base_price.unit ?? "단위 미정"}`
    : "확인 필요";
  const period = `${detail.availability.start_date ?? "미정"} ~ ${detail.availability.end_date ?? "미정"}`;
  const minimum = detail.minimum_quantity
    ? `${detail.minimum_quantity}${detail.quantity_unit ?? ""} 이상${detail.people_per_unit ? ` · 단위당 ${detail.people_per_unit}명` : ""}`
    : "별도 확인";

  return (
    <div className="mx-auto max-w-[920px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate(base)}><ArrowLeft className="size-4" />{t("summary.backToList")}</Button>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {detail.hero_image_url && <div className="h-44 overflow-hidden sm:h-56"><ImageWithFallback src={detail.hero_image_url} alt={detail.title} className="size-full object-cover" /></div>}
        <div className="p-4 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>{t(catKey)}</Badge>
            <Badge className="gap-1 border-transparent" style={{ background: detail.contract_available ? "var(--success-soft)" : "var(--muted)", color: detail.contract_available ? "var(--success)" : "var(--muted-foreground)" }}><ShieldCheck className="size-3.5" />{detail.contract_available ? "계약 가능" : "계약 마감"}</Badge>
            <span className="flex items-center gap-1 text-sm" style={{ color: "var(--warning)" }}><Star className="size-4 fill-current" />{detail.seller.rating}</span>
            <span className="flex items-center gap-1 text-sm text-muted-foreground"><MapPin className="size-4" />{detail.district}</span>
            {preview.findings.length > 0 && <Badge className="gap-1 border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}><AlertTriangle className="size-3.5" />{t("card.riskClauses")} {preview.findings.length}{t("card.riskUnit")}</Badge>}
          </div>
          <div className="mt-2 text-sm text-muted-foreground">{detail.seller.name}</div>
          <h1 className="mt-1" style={{ color: "var(--navy)" }}>{detail.title}</h1>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6">
        <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <h3 className="mb-2" style={{ color: "var(--navy)" }}>{t("summary.period")} · {t("summary.settlement")}</h3>
          <DetailRow icon={<CalendarDays className="size-4" />} label={t("summary.period")} value={period} />
          <DetailRow icon={<Package className="size-4" />} label={t("summary.quantity")} value={detail.supply_quantity_description ?? (detail.supply_quantity ? String(detail.supply_quantity) : "확인 필요")} />
          <DetailRow icon={<UsersRound className="size-4" />} label="최소 제안 기준" value={minimum} />
          <DetailRow icon={<Coins className="size-4" />} label={t("summary.unitPrice")} value={price} />
          <DetailRow icon={<Ban className="size-4" />} label={t("summary.cancellation")} value={detail.cancellation_policy ?? "확인 필요"} />
          <DetailRow icon={<UserX className="size-4" />} label={t("summary.noShow")} value={detail.no_show_policy ?? "확인 필요"} />
          <DetailRow icon={<Wallet className="size-4" />} label={t("summary.settlement")} value={detail.settlement_policy ?? "확인 필요"} />
        </div>
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border p-5" style={{ background: "var(--info-soft)", borderColor: "var(--ocean)" }}>
            <div className="flex items-center gap-1.5" style={{ color: "var(--ocean)", fontWeight: 600 }}><Sparkles className="size-4" />{t("summary.aiSummary")}</div>
            {summary.length > 0 ? <ul className="mt-3 flex flex-col gap-2">{summary.map((line, index) => <li key={`${index}-${line}`} className="flex gap-2 text-sm leading-6"><span style={{ color: "var(--ocean)", fontWeight: 700 }}>{index + 1}</span><span>{line}</span></li>)}</ul> : <p className="mt-3 text-sm text-muted-foreground">AI 요약이 아직 생성되지 않았습니다.</p>}
          </div>
          <Button className="w-full gap-1.5" style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/${detail.id}/document`)}><FileText className="size-4" />{t("summary.viewOriginal")}</Button>
          <Button variant="outline" className="w-full gap-1.5" onClick={() => navigate(base)}><ArrowLeft className="size-4" />{t("summary.backToList")}</Button>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <h3 className="mb-3" style={{ color: "var(--navy)" }}>{t("summary.keyClauses")}</h3>
        <Accordion type="single" collapsible className="w-full">
          {preview.clauses.map((clause, index) => {
            const finding = findingsByClause.get(clause.id);
            return <AccordionItem key={clause.id} value={clause.id}><AccordionTrigger className="text-left"><span className="flex items-center gap-2"><span style={{ color: "var(--ocean)", fontWeight: 600 }}>제{index + 1}조</span><span>{clause.title}</span>{finding && <Badge className="gap-1 border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}><AlertTriangle className="size-3" />{t("doc.riskBadge")}</Badge>}</span></AccordionTrigger><AccordionContent><p className="text-sm leading-7">{clause.body}</p>{finding && <div className="mt-3 rounded-lg bg-[var(--coral-soft)] p-3 text-sm"><p>{finding.explanation}</p>{finding.suggested_text && <p className="mt-2" style={{ color: "var(--teal)" }}>{finding.suggested_text}</p>}</div>}</AccordionContent></AccordionItem>;
          })}
        </Accordion>
      </div>
    </div>
  );
}
