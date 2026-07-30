import { FilePenLine, ArrowRight } from "lucide-react";
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
import { receivedRequests, type ReceivedRequest } from "../../data/receivedRequests";

type RequestTab = "all" | ReceivedRequest["status"];
const TABS: RequestTab[] = ["all", "new", "negotiating", "signing", "signed"];
const statusLabel: Record<RequestTab, string> = {
  all: "전체",
  new: "새 요청",
  negotiating: "협상 중",
  signing: "서명 대기",
  signed: "체결 완료",
};
const statusTone: Record<ReceivedRequest["status"], { bg: string; color: string; label: string }> = {
  new: { bg: "var(--info-soft)", color: "var(--ocean)", label: "새 요청" },
  negotiating: { bg: "var(--warning-soft)", color: "var(--warning)", label: "협상 중" },
  signing: { bg: "var(--success-soft)", color: "var(--teal)", label: "서명 대기" },
  signed: { bg: "var(--success-soft)", color: "var(--success)", label: "체결 완료" },
};

export function ReceivedRequestsPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const selected = params.get("status") as RequestTab | null;
  const tab: RequestTab = selected && TABS.includes(selected) ? selected : "all";
  const rows = tab === "all" ? receivedRequests : receivedRequests.filter((r) => r.status === tab);
  const counts = TABS.reduce<Record<string, number>>((acc, current) => {
    acc[current] = current === "all" ? receivedRequests.length : receivedRequests.filter((r) => r.status === current).length;
    return acc;
  }, {});

  const openRequest = (request: ReceivedRequest) => {
    if (request.revisions.length > 0) {
      navigate(`/seller/received/${request.id}`);
      return;
    }
    if (request.status === "signing") navigate("/seller/signing");
    else if (request.status === "signed") navigate("/seller/contracts");
    else navigate(`/seller/received/${request.id}`);
  };

  return (
    <div>
      <PageHeader title={t("recv.title")} description={t("recv.subtitle")} />

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((tb) => {
          const active = tab === tb;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => (tb === "all" ? setParams({}) : setParams({ status: tb }))}
              className="flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 transition-colors"
              style={{
                fontSize: "13px",
                borderColor: active ? "var(--navy)" : "var(--border)",
                background: active ? "var(--navy)" : "var(--card)",
                color: active ? "#fff" : "var(--foreground)",
              }}
            >
              {statusLabel[tb]}
              <span
                className="rounded-full px-1.5"
                style={{
                  fontSize: "11px",
                  background: active ? "rgba(255,255,255,0.25)" : "var(--muted)",
                  color: active ? "#fff" : "var(--muted-foreground)",
                }}
              >
                {counts[tb] ?? 0}
              </span>
            </button>
          );
        })}
      </div>

      {rows.length === 0 && (
        <div className="rounded-xl border border-border bg-card p-10 text-center text-muted-foreground lg:hidden">{t("recv.empty")}</div>
      )}
      {rows.length > 0 && (
        <div className="space-y-3 lg:hidden">
          {rows.map((r) => (
            <div key={r.id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="line-clamp-2 text-base" style={{ color: "var(--navy)" }}>{r.contractTitle}</h3>
                  <p className="mt-1 truncate text-sm text-muted-foreground">{r.buyer}</p>
                </div>
                <Badge className="shrink-0 gap-1 whitespace-nowrap border-transparent" style={{ background: statusTone[r.status].bg, color: statusTone[r.status].color }}>
                  <FilePenLine className="size-3" />
                  {statusTone[r.status].label}
                </Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 border-y border-border py-3 text-sm">
                <div><div className="text-xs text-muted-foreground">{t("recv.col.count")}</div><div className="mt-1">{r.revisions.length > 0 ? `${r.revisions.length}${t("recv.countUnit")}` : "조건 그대로"}</div></div>
                <div className="text-right"><div className="text-xs text-muted-foreground">{t("recv.col.date")}</div><div className="mt-1 whitespace-nowrap">{r.createdAt}</div></div>
              </div>
              <Button className="mt-3 w-full gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => openRequest(r)}>
                상세 보기
                <ArrowRight className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
      <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
        {rows.length === 0 ? (
          <div className="p-16 text-center text-muted-foreground">{t("recv.empty")}</div>
        ) : (
          <Table className="table-fixed">
            <colgroup>
              <col className="w-[18%]" />
              <col className="w-[30%]" />
              <col className="w-[14%]" />
              <col className="w-[10%]" />
              <col className="w-[14%]" />
              <col className="w-[14%]" />
            </colgroup>
            <TableHeader className="bg-muted/20">
              <TableRow>
                <TableHead className="h-12 whitespace-nowrap px-3">{t("recv.col.buyer")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3">{t("recv.col.contract")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.col.type")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.col.count")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.col.date")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.review")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id} className="h-16">
                  <TableCell className="whitespace-nowrap px-3 py-3" style={{ fontWeight: 600 }}>{r.buyer}</TableCell>
                  <TableCell className="min-w-0 px-3 py-3">
                    <span className="block truncate">{r.contractTitle}</span>
                  </TableCell>
                  <TableCell className="px-3 py-3 text-center">
                    <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: statusTone[r.status].bg, color: statusTone[r.status].color }}>
                      <FilePenLine className="size-3" />
                      {statusTone[r.status].label}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap px-3 py-3 text-center">
                    {r.revisions.length > 0 ? `${r.revisions.length}${t("recv.countUnit")}` : "조건 그대로"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap px-3 py-3 text-center text-muted-foreground">{r.createdAt}</TableCell>
                  <TableCell className="px-3 py-3 text-center">
                    <Button size="sm" className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => openRequest(r)}>
                      상세 보기
                      <ArrowRight className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
