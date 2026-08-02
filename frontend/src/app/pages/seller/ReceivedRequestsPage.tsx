import { useEffect, useMemo, useState } from "react";
import { ArrowRight, FilePenLine } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { useApp } from "../../context/AppContext";
import { friendlyApiError, getReceivedContracts, getSellerRevisionRequests, type SellerContractListItem, type SellerRevisionRequestListItem } from "../../lib/api";

type RequestTab = "all" | "new" | "negotiating" | "signing" | "signed";
const TABS: RequestTab[] = ["all", "new", "negotiating", "signing", "signed"];
const statusLabel: Record<RequestTab, string> = { all: "전체", new: "새 요청", negotiating: "협상 중", signing: "서명 대기", signed: "체결 완료" };
const statusTone: Record<Exclude<RequestTab, "all">, { bg: string; color: string; label: string }> = {
  new: { bg: "var(--info-soft)", color: "var(--ocean)", label: "새 요청" },
  negotiating: { bg: "var(--warning-soft)", color: "var(--warning)", label: "협상 중" },
  signing: { bg: "var(--success-soft)", color: "var(--teal)", label: "서명 대기" },
  signed: { bg: "var(--success-soft)", color: "var(--success)", label: "체결 완료" },
};

type Row = {
  id: string;
  contractId: string;
  buyer: string;
  title: string;
  status: Exclude<RequestTab, "all">;
  count: number;
  createdAt: string;
  revision: boolean;
};

function contractStatus(status: string): Row["status"] {
  if (status === "revision_requested") return "negotiating";
  if (status === "signing") return "signing";
  if (status === "signed") return "signed";
  return "new";
}

export function ReceivedRequestsPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [contracts, setContracts] = useState<SellerContractListItem[]>([]);
  const [revisions, setRevisions] = useState<SellerRevisionRequestListItem[]>([]);
  const [error, setError] = useState<string>();
  const selected = params.get("status") as RequestTab | null;
  const tab = selected && TABS.includes(selected) ? selected : "all";

  useEffect(() => {
    Promise.all([getReceivedContracts(), getSellerRevisionRequests()])
      .then(([nextContracts, nextRevisions]) => { setContracts(nextContracts); setRevisions(nextRevisions); })
      .catch((reason) => setError(friendlyApiError(reason)));
  }, []);

  const rows = useMemo<Row[]>(() => {
    const revisionByContract = new Map(revisions.map((revision) => [revision.contract_id, revision]));
    return contracts.map((contract) => {
      const revision = revisionByContract.get(contract.contract_id);
      return {
        id: revision?.id ?? contract.contract_id,
        contractId: contract.contract_id,
        buyer: contract.buyer_name,
        title: contract.listing_title,
        status: revision ? "negotiating" : contractStatus(contract.status),
        count: revision?.item_count ?? 0,
        createdAt: (revision?.sent_at ?? contract.requested_at).slice(0, 10).replace(/-/g, "."),
        revision: Boolean(revision),
      };
    });
  }, [contracts, revisions]);
  const filteredRows = tab === "all" ? rows : rows.filter((row) => row.status === tab);
  const counts = TABS.reduce<Record<string, number>>((result, current) => { result[current] = current === "all" ? rows.length : rows.filter((row) => row.status === current).length; return result; }, {});

  const openRow = (row: Row) => row.revision ? navigate(`/seller/received/${row.id}`) : navigate(`/seller/contracts?contractId=${row.contractId}`);

  return <div><PageHeader title={t("recv.title")} description={t("recv.subtitle")} />{error && <div className="mb-4 rounded-lg border border-destructive/30 p-3 text-sm text-destructive">{error}</div>}<div className="mb-4 flex flex-wrap gap-2">{TABS.map((current) => <button key={current} type="button" onClick={() => current === "all" ? setParams({}) : setParams({ status: current })} className="rounded-full border px-3 py-1.5 text-sm" style={{ borderColor: tab === current ? "var(--navy)" : "var(--border)", background: tab === current ? "var(--navy)" : "var(--card)", color: tab === current ? "#fff" : "var(--foreground)" }}>{statusLabel[current]} <span className="ml-1 rounded-full px-1.5 text-xs" style={{ background: tab === current ? "rgba(255,255,255,.25)" : "var(--muted)" }}>{counts[current] ?? 0}</span></button>)}</div><div className="overflow-hidden rounded-xl border border-border bg-card">{filteredRows.length === 0 ? <div className="p-16 text-center text-muted-foreground">{t("recv.empty")}</div> : <Table><TableHeader><TableRow><TableHead>{t("recv.col.buyer")}</TableHead><TableHead>{t("recv.col.contract")}</TableHead><TableHead>{t("recv.col.type")}</TableHead><TableHead>{t("recv.col.count")}</TableHead><TableHead>{t("recv.col.date")}</TableHead><TableHead>{t("recv.review")}</TableHead></TableRow></TableHeader><TableBody>{filteredRows.map((row) => <TableRow key={row.id}><TableCell className="font-semibold">{row.buyer}</TableCell><TableCell>{row.title}</TableCell><TableCell><Badge className="border-transparent" style={{ background: statusTone[row.status].bg, color: statusTone[row.status].color }}><FilePenLine className="mr-1 size-3" />{statusTone[row.status].label}</Badge></TableCell><TableCell>{row.revision ? `${row.count}${t("recv.countUnit")}` : "조건 그대로"}</TableCell><TableCell>{row.createdAt}</TableCell><TableCell><Button size="sm" className="gap-1.5" style={{ background: "var(--navy)" }} onClick={() => openRow(row)}>상세 보기<ArrowRight className="size-4" /></Button></TableCell></TableRow>)}</TableBody></Table>}</div></div>;
}
