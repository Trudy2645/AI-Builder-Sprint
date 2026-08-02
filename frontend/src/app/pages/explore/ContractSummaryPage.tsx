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
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { ImageWithFallback } from "../../components/figma/ImageWithFallback";
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
import { CATEGORIES, getContract, riskCount, type Contract } from "../../data/contracts";
import { friendlyApiError, getPublicListing } from "../../lib/api";

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
  const [serverContract, setServerContract] = useState<Contract | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const demoContract = getContract(id);

  useEffect(() => {
    if (demoContract || !id) return;
    void getPublicListing(id).then((listing) => setServerContract({
      id: listing.id,
      seller: listing.seller.name,
      title: listing.title,
      category: listing.category,
      district: listing.district,
      start: listing.availability.start_date ?? "미정",
      end: listing.availability.end_date ?? "미정",
      unitPrice: listing.base_price?.amount_minor ?? 0,
      priceUnit: listing.base_price?.unit ?? "기준 단가",
      quantityLabel: listing.supply_quantity_description ?? "미정",
      capacity: Number.MAX_SAFE_INTEGER,
      available: listing.contract_available,
      popularity: 0,
      createdOrder: 0,
      recommendScore: 0,
      image: listing.hero_image_url ?? "",
      aiSummary: listing.ai_summary?.split("\n") ?? ["AI 요약이 아직 준비되지 않았습니다."],
      details: {
        period: `${listing.availability.start_date ?? "미정"} ~ ${listing.availability.end_date ?? "미정"}`,
        supplyQuantity: listing.supply_quantity_description ?? "미정",
        unitPrice: `${(listing.base_price?.amount_minor ?? 0).toLocaleString("ko-KR")} ${listing.base_price?.currency ?? "KRW"}`,
        cancellation: listing.cancellation_policy ?? "미정",
        noShow: listing.no_show_policy ?? "미정",
        settlement: listing.settlement_policy ?? "미정",
      },
      clauses: listing.clauses.map((clause) => ({ no: `제${clause.clause_order}조`, title: clause.title, text: clause.body })),
    })).catch((error: unknown) => setLoadError(friendlyApiError(error)));
  }, [demoContract, id]);
  const contract = demoContract ?? serverContract;

  if (!contract) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">
        {loadError ?? "계약 조건을 불러오는 중입니다…"}
      </div>
    );
  }

  const risks = riskCount(contract);
  const catKey = CATEGORIES.find((c) => c.value === contract.category)?.labelKey ?? "cat.all";
  const d = contract.details;

  return (
    <div className="mx-auto max-w-[920px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate(base)}>
        <ArrowLeft className="size-4" />
        {t("summary.backToList")}
      </Button>

      {/* Hero */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="relative h-44 w-full overflow-hidden bg-secondary sm:h-56">
          <ImageWithFallback src={contract.image} alt={contract.title} className="size-full object-cover" />
        </div>
        <div className="p-4 sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>
              {t(catKey)}
            </Badge>
            <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: contract.available ? "var(--success-soft)" : "var(--muted)", color: contract.available ? "var(--success)" : "var(--muted-foreground)" }}>
              <ShieldCheck className="size-3.5" />{contract.available ? "계약 가능" : "계약 마감"}
            </Badge>
            <span className="flex items-center gap-1 whitespace-nowrap text-sm" style={{ color: "var(--warning)" }}><Star className="size-4 fill-current" />4.8</span>
            <span className="flex items-center gap-1 whitespace-nowrap text-muted-foreground" style={{ fontSize: "13px" }}>
              <MapPin className="size-4" />{contract.district}
            </span>
            {risks > 0 && (
              <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}>
                <AlertTriangle className="size-3.5" />
                {t("card.riskClauses")} {risks}{t("card.riskUnit")}
              </Badge>
            )}
          </div>
          <div className="mt-2 whitespace-nowrap text-muted-foreground" style={{ fontSize: "14px" }}>{contract.seller}</div>
          <h1 className="mt-1" style={{ color: "var(--navy)" }}>{contract.title}</h1>
        </div>
      </div>

      {/* Details + AI summary */}
      <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6">
        <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <h3 className="mb-2" style={{ color: "var(--navy)" }}>{t("summary.period")} · {t("summary.settlement")}</h3>
          <DetailRow icon={<CalendarDays className="size-4" />} label={t("summary.period")} value={d.period} />
          <DetailRow icon={<Package className="size-4" />} label={t("summary.quantity")} value={d.supplyQuantity} />
          <DetailRow icon={<UsersRound className="size-4" />} label="최소 제안 기준" value={contract.category === "accommodation" ? "10실 이상 · 객실당 기준 인원 2명" : "최소 20명"} />
          <DetailRow icon={<Coins className="size-4" />} label={t("summary.unitPrice")} value={d.unitPrice} />
          <DetailRow icon={<Ban className="size-4" />} label={t("summary.cancellation")} value={d.cancellation} />
          <DetailRow icon={<UserX className="size-4" />} label={t("summary.noShow")} value={d.noShow} />
          <DetailRow icon={<Wallet className="size-4" />} label={t("summary.settlement")} value={d.settlement} />
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-xl border p-5" style={{ background: "var(--info-soft)", borderColor: "var(--ocean)" }}>
            <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 600 }}>
              <Sparkles className="size-4" />
              {t("summary.aiSummary")}
            </div>
            <ul className="mt-3 flex flex-col gap-2">
              {contract.aiSummary.map((line, i) => (
                <li key={i} className="flex gap-2 text-foreground" style={{ fontSize: "14px", lineHeight: 1.5 }}>
                  <span style={{ color: "var(--ocean)", fontWeight: 700 }}>{i + 1}</span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col gap-2">
            <Button className="w-full gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/${contract.id}/document`)}>
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
          {contract.clauses.map((cl) => (
            <AccordionItem key={cl.no} value={cl.no}>
              <AccordionTrigger className="text-left">
                <span className="flex items-center gap-2">
                  <span className="whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 600 }}>{cl.no}</span>
                  <span>{cl.title}</span>
                  {cl.risk && (
                    <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}>
                      <AlertTriangle className="size-3" />
                      {t("doc.riskBadge")}
                    </Badge>
                  )}
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <p className="text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{cl.text}</p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </div>
  );
}
