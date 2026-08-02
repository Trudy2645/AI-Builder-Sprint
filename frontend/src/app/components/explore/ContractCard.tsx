import { MapPin, CalendarDays, Package, AlertTriangle, CheckCircle2, XCircle, ArrowRight, Calculator } from "lucide-react";
import { useNavigate } from "react-router";
import { ImageWithFallback } from "../figma/ImageWithFallback";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { useApp } from "../../context/AppContext";
import { CATEGORIES, formatKRW, riskCount, type Contract } from "../../lib/catalog";

const catKey = (c: Contract) => CATEGORIES.find((x) => x.value === c.category)?.labelKey ?? "cat.all";

export function ContractCard({ contract, base, guests, from, to }: { contract: Contract; base: string; guests?: string; from?: string; to?: string }) {
  const { t } = useApp();
  const navigate = useNavigate();
  const risks = contract.attentionRequiredCount ?? riskCount(contract);
  const guestCount = parseInt(guests ?? "", 10) || 0;
  const isAccommodation = contract.category === "accommodation";
  const units = isAccommodation ? Math.ceil(guestCount / 2) : guestCount;
  const requestedFrom = from ? new Date(from) : undefined;
  const requestedTo = to ? new Date(to) : undefined;
  const calculatedNights = requestedFrom && requestedTo
    ? Math.max(1, Math.ceil((requestedTo.getTime() - requestedFrom.getTime()) / 86400000))
    : isAccommodation ? 2 : 1;
  const estimate = units * calculatedNights * contract.unitPrice;

  return (
    <div className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card transition-shadow hover:shadow-md">
      <div className="relative h-40 w-full overflow-hidden bg-secondary">
        <ImageWithFallback
          src={contract.image}
          alt={`${contract.seller} - ${contract.title}`}
          className="size-full object-cover"
        />
        <div className="absolute left-3 top-3">
          {contract.available ? (
            <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--success)", color: "#fff" }}>
              <CheckCircle2 className="size-3.5" />
              {t("status.available")}
            </Badge>
          ) : (
            <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: "var(--muted-foreground)", color: "#fff" }}>
              <XCircle className="size-3.5" />
              {t("status.closed")}
            </Badge>
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Badge variant="outline" className="whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>
            {t(catKey(contract))}
          </Badge>
          <span className="flex min-w-0 items-center gap-1 text-muted-foreground" style={{ fontSize: "12px" }}>
            <MapPin className="size-3.5" />
            {contract.district}
          </span>
        </div>

        <div>
          <div className="truncate text-muted-foreground" style={{ fontSize: "12px" }} title={contract.seller}>
            {contract.seller}
          </div>
          <h3 className="mt-0.5 line-clamp-2" style={{ color: "var(--navy)" }}>
            {contract.title}
          </h3>
        </div>

        <div className="flex flex-col gap-1.5 text-muted-foreground" style={{ fontSize: "13px" }}>
          <span className="flex min-w-0 items-start gap-1.5">
            <CalendarDays className="size-4 shrink-0" />
            <span className="break-words">{contract.start} ~ {contract.end}</span>
          </span>
          <span className="flex min-w-0 items-start gap-1.5">
            <Package className="size-4 shrink-0" />
            <span className="break-words">{contract.quantityLabel}</span>
          </span>
        </div>

        <div className="flex items-end justify-between">
          <div>
            <span className="text-muted-foreground" style={{ fontSize: "12px" }}>{contract.priceUnit} </span>
            <span style={{ color: "var(--navy)", fontWeight: 700, fontSize: "18px" }}>
              {formatKRW(contract.unitPrice)}
            </span>
          </div>
        </div>

        {guestCount > 0 && (
          <div className="rounded-lg border p-2.5" style={{ borderColor: "var(--teal)", background: "var(--success-soft)" }}>
            <div className="flex items-start gap-1.5 break-keep" style={{ color: "var(--teal)", fontSize: "12px", fontWeight: 700 }}>
              <Calculator className="mt-0.5 size-3.5 shrink-0" />
              {guestCount}명 기준 예상 금액
            </div>
            <div className="mt-1" style={{ color: "var(--navy)", fontWeight: 700 }}>{formatKRW(estimate)}</div>
            <div className="text-muted-foreground" style={{ fontSize: "11px" }}>
              {isAccommodation ? `${units}실 × ${calculatedNights}박` : `${units}명`} × {formatKRW(contract.unitPrice)}
            </div>
          </div>
        )}

        {risks > 0 && (
          <div className="flex items-start gap-1.5 break-keep" style={{ color: "var(--coral)", fontSize: "13px" }}>
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            {t("card.riskClauses")} {risks}{t("card.riskUnit")}
          </div>
        )}

        <Button
          className="mt-auto w-full gap-1.5 whitespace-nowrap"
          style={{ background: "var(--navy)" }}
          onClick={() => navigate(`${base}/${contract.id}`)}
        >
          {t("card.viewTerms")}
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
