import {
  Globe,
  Inbox,
  MessagesSquare,
  PenLine,
  FileCheck2,
  Plus,
  ArrowRight,
  BellRing,
  type LucideIcon,
} from "lucide-react";
import { useNavigate } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { useApp } from "../../context/AppContext";
import { useListings } from "../../store/ListingsContext";
import { CATEGORIES, formatKRW } from "../../data/contracts";

const SELLER_FALLBACK = "해운대 오션스테이";

interface Stat {
  key: string;
  labelKey: string;
  value: number;
  icon: LucideIcon;
  color: string;
  bg: string;
  path: string;
}

export function SellerDashboardPage() {
  const { t, companyName, isDemoSession } = useApp();
  const navigate = useNavigate();
  const { listings, publicCount } = useListings();
  const company = companyName || (isDemoSession ? SELLER_FALLBACK : "계정 정보 없음");

  const stats: Stat[] = [
    { key: "public", labelKey: "sdash.stat.public", value: publicCount, icon: Globe, color: "var(--success)", bg: "var(--success-soft)", path: "/seller/listings?status=public" },
    { key: "newReq", labelKey: "sdash.stat.newReq", value: 0, icon: Inbox, color: "var(--ocean)", bg: "var(--info-soft)", path: "/seller/received?status=new" },
    { key: "negotiating", labelKey: "sdash.stat.negotiating", value: 0, icon: MessagesSquare, color: "var(--warning)", bg: "var(--warning-soft)", path: "/seller/received?status=negotiating" },
    { key: "signing", labelKey: "sdash.stat.signing", value: 0, icon: PenLine, color: "var(--teal)", bg: "var(--success-soft)", path: "/seller/received?status=signing" },
    { key: "monthlyClosed", labelKey: "sdash.stat.monthlyClosed", value: 0, icon: FileCheck2, color: "var(--navy)", bg: "var(--info-soft)", path: "/seller/received?status=signed" },
  ];

  const recent = listings.slice(0, 5);

  return (
    <div>
      <PageHeader
        title={t("sdash.welcome").replace("{name}", company)}
        description={t("sdash.subtitle")}
        actions={
          <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate("/seller/listings/new")}>
            <Plus className="size-4" />
            {t("sdash.newListing")}
          </Button>
        }
      />

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-5">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <button key={s.key} type="button" className="rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-[var(--ocean)]" onClick={() => navigate(s.path)}>
              <div className="flex size-9 items-center justify-center rounded-lg" style={{ background: s.bg, color: s.color }}>
                <Icon className="size-5" />
              </div>
              <div className="mt-3 flex items-baseline gap-1">
                <span style={{ fontSize: "26px", fontWeight: 700, color: "var(--navy)" }}>{s.value}</span>
                <span className="text-muted-foreground" style={{ fontSize: "13px" }}>{t("sdash.unit")}</span>
              </div>
              <div className="mt-0.5 min-h-10 break-keep text-muted-foreground" style={{ fontSize: "13px" }}>{t(s.labelKey)}</div>
            </button>
          );
        })}
      </div>

      {/* Received contract requests */}
      <div className="mt-8 overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex flex-col items-start justify-between gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:px-6">
          <div className="min-w-0">
            <h3 className="flex items-start gap-2 break-words" style={{ color: "var(--navy)" }}><BellRing className="mt-1 size-4 shrink-0" style={{ color: "var(--ocean)" }} />받은 계약 요청</h3>
            <p className="mt-1 text-xs text-muted-foreground">바이어의 수정 요청과 조건 그대로 체결된 계약 알림을 확인하세요.</p>
          </div>
          <Button variant="ghost" size="sm" className="gap-1 whitespace-nowrap" onClick={() => navigate("/seller/received")}>전체 보기<ArrowRight className="size-4" /></Button>
        </div>
        <div className="flex min-h-[160px] items-center justify-center px-6 py-10 text-center text-muted-foreground">
          아직 받은 계약 요청이 없습니다.
        </div>
      </div>

      {/* Recent listings */}
      <div className="mt-8 rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <h3 className="break-words" style={{ color: "var(--navy)" }}>공고</h3>
          <Button variant="ghost" size="sm" className="gap-1 whitespace-nowrap" onClick={() => navigate("/seller/listings")}>
            {t("sdash.viewAll")}
            <ArrowRight className="size-4" />
          </Button>
        </div>
        {recent.length === 0 ? (
          <div className="flex min-h-[140px] items-center justify-center rounded-lg border border-dashed border-border text-center text-muted-foreground">
            등록된 공고가 없습니다.
          </div>
        ) : (
          <div className="flex flex-col divide-y divide-border">
            {recent.map((l) => {
              const catKey = CATEGORIES.find((c) => c.value === l.category)?.labelKey ?? "cat.all";
              return (
                <button
                  key={l.id}
                  type="button"
                  onClick={() => navigate("/seller/listings")}
                  className="flex items-start gap-3 py-3 text-left transition-colors hover:bg-secondary sm:items-center sm:gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate" style={{ fontWeight: 600, color: "var(--navy)" }}>{l.productName}</div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-muted-foreground" style={{ fontSize: "12px" }}>
                      <span>{t(catKey)}</span>
                      <span>·</span>
                      <span>{l.priceUnit} {formatKRW(l.unitPrice)}</span>
                      <span>·</span>
                      <span>{l.quantityLabel}</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
