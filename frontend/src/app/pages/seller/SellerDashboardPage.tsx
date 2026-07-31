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
import { Badge } from "../../components/ui/badge";
import { useApp } from "../../context/AppContext";
import { useListings } from "../../store/ListingsContext";
import { CATEGORIES, formatKRW } from "../../data/contracts";
import { receivedRequests, type ReceivedRequest } from "../../data/receivedRequests";

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

const requestStatusLabel: Record<ReceivedRequest["status"], string> = {
  new: "새 요청",
  negotiating: "협상 중",
  signing: "서명 대기",
  signed: "체결 완료",
};

const requestStatusTone: Record<ReceivedRequest["status"], { bg: string; color: string }> = {
  new: { bg: "var(--info-soft)", color: "var(--ocean)" },
  negotiating: { bg: "var(--warning-soft)", color: "var(--warning)" },
  signing: { bg: "var(--success-soft)", color: "var(--teal)" },
  signed: { bg: "var(--success-soft)", color: "var(--success)" },
};

export function SellerDashboardPage() {
  const { t, companyName, isDemoSession } = useApp();
  const navigate = useNavigate();
  const { listings, publicCount } = useListings();
  const company = companyName || (isDemoSession ? SELLER_FALLBACK : "계정 정보 없음");
  const sellerRequests = isDemoSession ? receivedRequests : [];
  const newRequestCount = sellerRequests.filter((request) => request.status === "new").length;
  const negotiatingCount = sellerRequests.filter((request) => request.status === "negotiating").length;
  const signingCount = sellerRequests.filter((request) => request.status === "signing").length;
  const signedThisMonthCount = sellerRequests.filter((request) => request.status === "signed" && request.createdAt.startsWith("2026.07")).length;

  const stats: Stat[] = [
    { key: "public", labelKey: "sdash.stat.public", value: publicCount, icon: Globe, color: "var(--success)", bg: "var(--success-soft)", path: "/seller/listings?status=public" },
    { key: "newReq", labelKey: "sdash.stat.newReq", value: newRequestCount, icon: Inbox, color: "var(--ocean)", bg: "var(--info-soft)", path: "/seller/received?status=new" },
    { key: "negotiating", labelKey: "sdash.stat.negotiating", value: negotiatingCount, icon: MessagesSquare, color: "var(--warning)", bg: "var(--warning-soft)", path: "/seller/received?status=negotiating" },
    { key: "signing", labelKey: "sdash.stat.signing", value: signingCount, icon: PenLine, color: "var(--teal)", bg: "var(--success-soft)", path: "/seller/received?status=signing" },
    { key: "monthlyClosed", labelKey: "sdash.stat.monthlyClosed", value: signedThisMonthCount, icon: FileCheck2, color: "var(--navy)", bg: "var(--info-soft)", path: "/seller/received?status=signed" },
  ];

  const recent = listings.slice(0, 5);
  const recentRequests = sellerRequests.slice(0, 4);

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
        <div className="hidden overflow-x-auto lg:block">
          <div className="grid min-w-[900px] grid-cols-[1fr_1.2fr_1.7fr_1fr_1fr_.8fr] gap-4 border-b bg-muted/40 px-6 py-3 text-xs font-semibold text-muted-foreground">
            <div>요청 ID</div><div>바이어</div><div>계약명</div><div>기간·수량</div><div>상태</div><div>작업</div>
          </div>
          {recentRequests.map((row) => (
            <div key={row.id} className="grid min-w-[900px] grid-cols-[1fr_1.2fr_1.7fr_1fr_1fr_.8fr] items-center gap-4 border-b px-6 py-4 last:border-b-0">
              <div className="text-xs font-semibold" style={{ color: "var(--ocean)" }}>{row.id}</div>
              <div className="truncate font-semibold">{row.buyer}</div>
              <div className="truncate text-sm">{row.contractTitle}</div>
              <div className="text-sm text-muted-foreground">{row.period}</div>
              <div><Badge className="whitespace-nowrap border-transparent" style={{ background: requestStatusTone[row.status].bg, color: requestStatusTone[row.status].color }}>{requestStatusLabel[row.status]}</Badge></div>
              <Button size="sm" variant="outline" className="whitespace-nowrap" onClick={() => navigate(`/seller/received?status=${row.status}`)}>상세 보기</Button>
            </div>
          ))}
        </div>
        <div className="divide-y divide-border lg:hidden">
          {recentRequests.map((row) => (
            <div key={row.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-xs font-semibold" style={{ color: "var(--ocean)" }}>{row.id}</div>
                  <div className="mt-1 truncate font-semibold">{row.contractTitle}</div>
                  <div className="mt-1 text-sm text-muted-foreground">{row.buyer} · {row.period}</div>
                </div>
                <Badge className="shrink-0 whitespace-nowrap border-transparent" style={{ background: requestStatusTone[row.status].bg, color: requestStatusTone[row.status].color }}>{requestStatusLabel[row.status]}</Badge>
              </div>
              <Button size="sm" variant="outline" className="mt-3 w-full whitespace-nowrap" onClick={() => navigate(`/seller/received?status=${row.status}`)}>상세 보기</Button>
            </div>
          ))}
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
      </div>
    </div>
  );
}
