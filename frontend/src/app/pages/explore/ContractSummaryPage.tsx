import {
  ArrowLeft,
  FileText,
  CalendarDays,
  Package,
  Coins,
  Ban,
  UserX,
  Wallet,
  Sparkles,
  MapPin,
  AlertTriangle,
  ShieldCheck,
  UsersRound,
  Star,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../components/ui/accordion";
import { useApp } from "../../context/AppContext";
import { useExploreCtx } from "../../hooks/useExploreCtx";
import { CATEGORIES } from "../../lib/catalog";
import { friendlyApiError, getPublicListing, type PublicListingDetail } from "../../lib/api";

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
  const { t } = useApp();
  const { base } = useExploreCtx();
  const { id } = useParams();
  const navigate = useNavigate();
  const [listing, setListing] = useState<PublicListingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      setLoadError("공고 식별자가 없습니다.");
      return;
    }
    let active = true;
    setLoading(true);
    setLoadError(null);
    getPublicListing(id)
      .then((result) => {
        if (active) setListing(result);
      })
      .catch((error: unknown) => {
        if (active) {
          setListing(null);
          setLoadError(friendlyApiError(error));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-[920px] space-y-6" aria-busy="true">
        <div className="h-8 w-28 animate-pulse rounded bg-muted" />
        <div className="h-96 animate-pulse rounded-xl bg-muted" />
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div className="h-96 animate-pulse rounded-xl bg-muted" />
          <div className="h-64 animate-pulse rounded-xl bg-muted" />
        </div>
      </div>
    );
  }

  if (loadError || !listing) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">
        <p>{loadError ?? t("explore.empty")}</p>
        <Button variant="outline" className="mt-4" onClick={() => navigate(base)}>
          <ArrowLeft className="mr-1.5 size-4" />
          {t("summary.backToList")}
        </Button>
      </div>
    );
  }

  const risks = listing.attention_required_count;
  const catKey = CATEGORIES.find((c) => c.value === listing.category)?.labelKey ?? "cat.all";
  const rating = Number(listing.seller.rating);
  const hasRating = Number.isFinite(rating) && Number(listing.seller.rating_count) > 0;
  const ratingLabel = hasRating ? rating.toFixed(1) : null;
  const summaryLines = listing.ai_summary
    ?.split(/\r?\n/)
    .map((line) => line.replace(/^[-*•]\s*/, "").trim())
    .filter(Boolean) ?? [];

  const formatDate = (value: string | null) => value ? value.replace(/-/g, ".") : "정보 없음";
  const period = `${formatDate(listing.availability.start_date)} ~ ${formatDate(listing.availability.end_date)}`;
  const quantityUnit = listing.quantity_unit ?? "";
  const quantityDescription = listing.supply_quantity_description
    ?? (listing.supply_quantity ? `${listing.supply_quantity}${quantityUnit}` : "정보 없음");
  const minimumCriteria = listing.minimum_quantity
    ? `${listing.minimum_quantity}${quantityUnit} 이상${listing.people_per_unit ? ` · ${quantityUnit}당 기준 인원 ${listing.people_per_unit}명` : ""}`
    : listing.minimum_people
      ? `${listing.minimum_people}명 이상`
      : "정보 없음";
  const price = listing.base_price
    ? `${listing.base_price.unit ? `${listing.base_price.unit} ` : ""}${listing.base_price.currency === "KRW" ? `${listing.base_price.amount_minor.toLocaleString("ko-KR")}원` : `${listing.base_price.amount_minor.toLocaleString("ko-KR")} ${listing.base_price.currency}`}`
    : "정보 없음";
  const clauseHighlight = (highlight: "critical" | "warning" | "info" | null) => highlight === "critical" || highlight === "warning";

  return (
    <div className="mx-auto max-w-[920px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate(base)}>
        <ArrowLeft className="size-4" />
        {t("summary.backToList")}
      </Button>

      {/* Hero */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="relative h-44 w-full overflow-hidden bg-secondary sm:h-56">
          {listing.hero_image_url ? (
            <img src={listing.hero_image_url} alt={listing.title} className="size-full object-cover" />
          ) : (
            <div className="flex size-full items-center justify-center bg-secondary text-sm text-muted-foreground">
              대표 이미지가 없습니다.
            </div>
          )}
        </div>
        <div className="p-4 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>
              {t(catKey)}
            </Badge>
            <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: listing.contract_available ? "var(--success-soft)" : "var(--muted)", color: listing.contract_available ? "var(--success)" : "var(--muted-foreground)" }}>
              <ShieldCheck className="size-3.5" />{listing.contract_available ? "계약 가능" : "계약 마감"}
            </Badge>
            {ratingLabel && (
              <span className="flex items-center gap-1 whitespace-nowrap text-sm" style={{ color: "var(--warning)" }}><Star className="size-4 fill-current" />{ratingLabel}</span>
            )}
            <span className="flex items-center gap-1 whitespace-nowrap text-muted-foreground" style={{ fontSize: "13px" }}>
              <MapPin className="size-4" />{listing.district}
            </span>
            {risks > 0 && (
              <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}>
                <AlertTriangle className="size-3.5" />
                {t("card.riskClauses")} {risks}{t("card.riskUnit")}
              </Badge>
            )}
          </div>
          <div className="mt-2 whitespace-nowrap text-muted-foreground" style={{ fontSize: "14px" }}>{listing.seller.name}</div>
          <h1 className="mt-1" style={{ color: "var(--navy)" }}>{listing.title}</h1>
        </div>
      </div>

      {/* Details + AI summary */}
      <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6">
        <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <h3 className="mb-2" style={{ color: "var(--navy)" }}>{t("summary.period")} · {t("summary.settlement")}</h3>
          <DetailRow icon={<CalendarDays className="size-4" />} label={t("summary.period")} value={period} />
          <DetailRow icon={<Package className="size-4" />} label={t("summary.quantity")} value={quantityDescription} />
          <DetailRow icon={<UsersRound className="size-4" />} label="최소 제안 기준" value={minimumCriteria} />
          <DetailRow icon={<Coins className="size-4" />} label={t("summary.unitPrice")} value={price} />
          <DetailRow icon={<Ban className="size-4" />} label={t("summary.cancellation")} value={listing.cancellation_policy ?? "정보 없음"} />
          <DetailRow icon={<UserX className="size-4" />} label={t("summary.noShow")} value={listing.no_show_policy ?? "정보 없음"} />
          <DetailRow icon={<Wallet className="size-4" />} label={t("summary.settlement")} value={listing.settlement_policy ?? "정보 없음"} />
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-xl border p-5" style={{ background: "var(--info-soft)", borderColor: "var(--ocean)" }}>
            <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 600 }}>
              <Sparkles className="size-4" />
              {t("summary.aiSummary")}
            </div>
            <ul className="mt-3 flex flex-col gap-2">
              {summaryLines.length > 0 ? summaryLines.map((line, i) => (
                <li key={i} className="flex gap-2 text-foreground" style={{ fontSize: "14px", lineHeight: 1.5 }}>
                  <span style={{ color: "var(--ocean)", fontWeight: 700 }}>{i + 1}</span>
                  <span>{line}</span>
                </li>
              )) : (
                <li className="text-sm text-muted-foreground">AI 요약이 아직 준비되지 않았습니다.</li>
              )}
            </ul>
          </div>

          <div className="flex flex-col gap-2">
            <Button className="w-full gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/${listing.id}/document`)}>
              <FileText className="size-4" />
              {t("summary.viewOriginal")}
            </Button>
            <Button variant="outline" className="w-full gap-1.5 whitespace-nowrap" onClick={() => navigate(base)}>
              <ArrowLeft className="size-4" />
              {t("summary.backToList")}
            </Button>
          </div>
        </div>
      </div>

      {/* Key clauses accordion */}
      <div className="mt-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <h3 className="mb-3" style={{ color: "var(--navy)" }}>{t("summary.keyClauses")}</h3>
        <Accordion type="single" collapsible className="w-full">
          {listing.clauses.map((cl) => (
            <AccordionItem key={cl.id} value={cl.id}>
              <AccordionTrigger className="text-left">
                <span className="flex items-center gap-2">
                  <span>{cl.title}</span>
                  {clauseHighlight(cl.highlight) && (
                    <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}>
                      <AlertTriangle className="size-3" />
                      {t("doc.riskBadge")}
                    </Badge>
                  )}
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <p className="text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{cl.body}</p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </div>
  );
}
