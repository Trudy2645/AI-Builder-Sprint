import { useMemo, useState } from "react";
import { FilePenLine, FileCheck2 } from "lucide-react";
import { useNavigate } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { StatusBadge } from "../../components/requests/StatusBadge";
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

type Tab = "all" | RequestStatus;
const TABS: Tab[] = ["all", "draft", "reviewing", "final_review", "responded", "negotiating", "signing", "completed", "closed"];
const tabLabel: Record<Tab, string> = {
  all: "tab.all",
  draft: "lstatus.draft",
  reviewing: "rstatus.reviewing",
  final_review: "rstatus.final_review",
  responded: "rstatus.responded",
  negotiating: "rstatus.negotiating",
  signing: "rstatus.signing",
  completed: "rstatus.completed",
  closed: "rstatus.closed",
};

export function SentRequestsPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { requests } = useRequests();
  const [tab, setTab] = useState<Tab>("all");

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: requests.length };
    for (const r of requests) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [requests]);

  const rows = tab === "all" ? requests : requests.filter((r) => r.status === tab);

  const openRequest = (request: SentRequest) => {
    if (request.type === "revision" && request.revisionRequestId) {
      navigate(`/buyer/sent/revision/${request.revisionRequestId}`);
      return;
    }
    navigate(`/buyer/sent/contract/${request.contractId}`);
  };

  return (
    <div>
      <PageHeader title={t("sent.title")} description={t("sent.subtitle")} />

      {/* Tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((tb) => {
          const active = tab === tb;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setTab(tb)}
              className="flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 transition-colors"
              style={{
                fontSize: "13px",
                borderColor: active ? "var(--navy)" : "var(--border)",
                background: active ? "var(--navy)" : "var(--card)",
                color: active ? "#fff" : "var(--foreground)",
              }}
            >
              {t(tabLabel[tb])}
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

      {/* Table */}
      {rows.length === 0 && (
        <div className="rounded-xl border border-border bg-card p-10 text-center text-muted-foreground lg:hidden">{t("sent.empty")}</div>
      )}
      {rows.length > 0 && (
        <div className="space-y-3 lg:hidden">
          {rows.map((r) => (
            <div key={r.id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="line-clamp-2 text-base" style={{ color: "var(--navy)" }}>{r.title}</h3>
                  <p className="mt-1 truncate text-sm text-muted-foreground">{r.seller}</p>
                </div>
                <StatusBadge status={r.status} />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 border-y border-border py-3 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">{t("sent.col.type")}</div>
                  <Badge variant="outline" className="mt-1 gap-1 whitespace-nowrap" style={{ borderColor: r.type === "asis" ? "var(--ocean)" : "var(--teal)", color: r.type === "asis" ? "var(--ocean)" : "var(--teal)" }}>
                    {r.type === "asis" ? <FileCheck2 className="size-3" /> : <FilePenLine className="size-3" />}
                    {t(r.type === "asis" ? "sent.type.asis" : "sent.type.revision")}
                  </Badge>
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted-foreground">{t("sent.col.date")}</div>
                  <div className="mt-1 whitespace-nowrap">{r.createdAt}</div>
                </div>
              </div>
              <Button variant="outline" className="mt-3 w-full whitespace-nowrap" onClick={() => openRequest(r)}>
                {t("sent.view")}
              </Button>
            </div>
          ))}
        </div>
      )}
      <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
        {rows.length === 0 ? (
          <div className="p-16 text-center text-muted-foreground">{t("sent.empty")}</div>
        ) : (
          <Table className="table-fixed">
            <colgroup>
              <col className="w-[33%]" />
              <col className="w-[19%]" />
              <col className="w-[14%]" />
              <col className="w-[13%]" />
              <col className="w-[13%]" />
              <col className="w-[8%]" />
            </colgroup>
            <TableHeader className="bg-muted/20">
              <TableRow>
                <TableHead className="h-12 whitespace-nowrap px-3">{t("sent.col.contract")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3">{t("sent.col.seller")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("sent.col.type")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("sent.col.date")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("sent.col.status")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("sent.view")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id} className="h-16">
                  <TableCell className="min-w-0 px-3 py-3">
                    <span className="block truncate">{r.title}</span>
                  </TableCell>
                  <TableCell className="truncate whitespace-nowrap px-3 py-3">{r.seller}</TableCell>
                  <TableCell className="px-3 py-3 text-center">
                    <Badge variant="outline" className="gap-1 whitespace-nowrap" style={{ borderColor: r.type === "asis" ? "var(--ocean)" : "var(--teal)", color: r.type === "asis" ? "var(--ocean)" : "var(--teal)" }}>
                      {r.type === "asis" ? <FileCheck2 className="size-3" /> : <FilePenLine className="size-3" />}
                      {t(r.type === "asis" ? "sent.type.asis" : "sent.type.revision")}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap px-3 py-3 text-center text-muted-foreground">{r.createdAt}</TableCell>
                  <TableCell className="px-3 py-3 text-center"><StatusBadge status={r.status} /></TableCell>
                  <TableCell className="px-3 py-3 text-center">
                    <Button variant="ghost" size="sm" className="whitespace-nowrap px-2" onClick={() => openRequest(r)}>
                      {t("sent.view")}
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
