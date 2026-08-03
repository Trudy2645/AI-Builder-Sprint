import { useMemo } from "react";
import { ArrowRight, FilePenLine } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { useApp } from "../../context/AppContext";
import { useRequests, type RequestStatus, type SentRequest } from "../../store/RequestsContext";

type NegotiatingTab = "all" | "reviewing" | "negotiating";

const TABS: NegotiatingTab[] = ["all", "reviewing", "negotiating"];
const NEGOTIATING_STATUSES: RequestStatus[] = ["reviewing", "negotiating"];

const tabLabelKey: Record<NegotiatingTab, string> = {
  all: "sneg.tab.all",
  reviewing: "sneg.tab.reviewing",
  negotiating: "sneg.tab.negotiating",
};

const statusTone: Record<"reviewing" | "negotiating", { bg: string; color: string; labelKey: string }> = {
  reviewing: { bg: "var(--info-soft)", color: "var(--ocean)", labelKey: "sneg.status.reviewing" },
  negotiating: { bg: "var(--warning-soft)", color: "var(--warning)", labelKey: "sneg.status.negotiating" },
};

function statusFor(request: SentRequest): "reviewing" | "negotiating" {
  return request.status === "reviewing" ? "reviewing" : "negotiating";
}

function periodFor(request: SentRequest): string {
  if (!request.serviceStartDate && !request.serviceEndDate) return "-";
  return `${request.serviceStartDate ?? "-"} ~ ${request.serviceEndDate ?? "-"}`;
}

export function SellerNegotiatingPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const selected = params.get("status") as NegotiatingTab | null;
  const tab: NegotiatingTab = selected && TABS.includes(selected) ? selected : "all";
  const { requests, loading } = useRequests();

  const sourceRows = useMemo(
    () => requests.filter((request) => NEGOTIATING_STATUSES.includes(request.status)),
    [requests],
  );
  const rows = tab === "all" ? sourceRows : sourceRows.filter((request) => request.status === tab);
  const counts = TABS.reduce<Record<NegotiatingTab, number>>((acc, current) => {
    acc[current] = current === "all" ? sourceRows.length : sourceRows.filter((request) => request.status === current).length;
    return acc;
  }, { all: 0, reviewing: 0, negotiating: 0 });

  const openRequest = (request: SentRequest) => {
    navigate(`/seller/received?contractId=${request.contractId}`);
  };

  return (
    <div>
      <PageHeader title={t("sneg.title")} description={t("sneg.subtitle")} />

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((current) => {
          const active = tab === current;
          return (
            <button
              key={current}
              type="button"
              onClick={() => (current === "all" ? setParams({}) : setParams({ status: current }))}
              className="flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 transition-colors"
              style={{
                fontSize: "13px",
                borderColor: active ? "var(--navy)" : "var(--border)",
                background: active ? "var(--navy)" : "var(--card)",
                color: active ? "#fff" : "var(--foreground)",
              }}
            >
              {t(tabLabelKey[current])}
              <span
                className="rounded-full px-1.5"
                style={{
                  fontSize: "11px",
                  background: active ? "rgba(255,255,255,0.25)" : "var(--muted)",
                  color: active ? "#fff" : "var(--muted-foreground)",
                }}
              >
                {counts[current]}
              </span>
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="rounded-xl border border-border bg-card p-16 text-center text-muted-foreground">{t("sneg.loading")}</div>
      ) : (
        <>
          {rows.length === 0 && (
            <div className="rounded-xl border border-border bg-card p-10 text-center text-muted-foreground lg:hidden">{t("sneg.empty")}</div>
          )}

          {rows.length > 0 && (
            <div className="space-y-3 lg:hidden">
              {rows.map((request) => {
                const status = statusFor(request);
                return (
                  <div key={request.id} className="rounded-xl border border-border bg-card p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="line-clamp-2 text-base" style={{ color: "var(--navy)" }}>{request.title}</h3>
                        <p className="mt-1 truncate text-sm text-muted-foreground">{request.buyer ?? t("sneg.buyerFallback")}</p>
                      </div>
                      <Badge className="shrink-0 gap-1 whitespace-nowrap border-transparent" style={{ background: statusTone[status].bg, color: statusTone[status].color }}>
                        <FilePenLine className="size-3" />
                        {t(statusTone[status].labelKey)}
                      </Badge>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-3 border-y border-border py-3 text-sm">
                      <div><div className="text-xs text-muted-foreground">{t("sneg.col.period")}</div><div className="mt-1">{periodFor(request)}</div></div>
                      <div className="text-right"><div className="text-xs text-muted-foreground">{t("sneg.col.date")}</div><div className="mt-1 whitespace-nowrap">{request.createdAt}</div></div>
                    </div>
                    <Button className="mt-3 w-full gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => openRequest(request)}>
                      {t("sneg.open")}
                      <ArrowRight className="size-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}

          <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
            {rows.length === 0 ? (
              <div className="p-16 text-center text-muted-foreground">{t("sneg.empty")}</div>
            ) : (
              <Table className="table-fixed">
                <colgroup>
                  <col className="w-[18%]" />
                  <col className="w-[30%]" />
                  <col className="w-[20%]" />
                  <col className="w-[12%]" />
                  <col className="w-[10%]" />
                  <col className="w-[10%]" />
                </colgroup>
                <TableHeader className="bg-muted/20">
                  <TableRow>
                    <TableHead className="h-12 whitespace-nowrap px-3">{t("sneg.col.buyer")}</TableHead>
                    <TableHead className="h-12 whitespace-nowrap px-3">{t("sneg.col.contract")}</TableHead>
                    <TableHead className="h-12 whitespace-nowrap px-3">{t("sneg.col.period")}</TableHead>
                    <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("sneg.col.status")}</TableHead>
                    <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("sneg.col.date")}</TableHead>
                    <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("sneg.col.action")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((request) => {
                    const status = statusFor(request);
                    return (
                      <TableRow key={request.id} className="h-16">
                        <TableCell className="whitespace-nowrap px-3 py-3" style={{ fontWeight: 600 }}>{request.buyer ?? t("sneg.buyerFallback")}</TableCell>
                        <TableCell className="min-w-0 px-3 py-3">
                          <span className="block truncate">{request.title}</span>
                        </TableCell>
                        <TableCell className="whitespace-nowrap px-3 py-3 text-muted-foreground">{periodFor(request)}</TableCell>
                        <TableCell className="px-3 py-3 text-center">
                          <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: statusTone[status].bg, color: statusTone[status].color }}>
                            <FilePenLine className="size-3" />
                            {t(statusTone[status].labelKey)}
                          </Badge>
                        </TableCell>
                        <TableCell className="whitespace-nowrap px-3 py-3 text-center text-muted-foreground">{request.createdAt}</TableCell>
                        <TableCell className="px-3 py-3 text-center">
                          <Button size="sm" className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => openRequest(request)}>
                            {t("sneg.open")}
                            <ArrowRight className="size-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
