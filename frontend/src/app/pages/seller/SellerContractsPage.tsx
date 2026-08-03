import { useMemo, useState } from "react";
import { Download, FileCheck2, FileText } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { useRequests, type RequestStatus, type SentRequest } from "../../store/RequestsContext";
import { friendlyApiError, getContractDetail } from "../../lib/api";

type Tab = "all" | "signing" | "completed" | "closed";
const TABS: Array<{ key: Tab; label: string }> = [{ key: "all", label: "전체" }, { key: "signing", label: "서명 대기" }, { key: "completed", label: "체결 완료" }, { key: "closed", label: "종료" }];
const label: Record<Tab, string> = { all: "전체", signing: "서명 대기", completed: "체결 완료", closed: "종료" };

function statusFor(request: SentRequest): Tab { return request.status === "signing" ? "signing" : request.status === "completed" ? "completed" : "closed"; }
function contractNo(id: string): string { return `BL-${id.slice(0, 8).toUpperCase()}`; }

export function SellerContractsPage() {
  const { requests } = useRequests();
  const [tab, setTab] = useState<Tab>("all");
  const contracts = useMemo(() => requests.filter((request) => ["signing", "completed", "closed"].includes(request.status)), [requests]);
  const rows = tab === "all" ? contracts : contracts.filter((request) => statusFor(request) === tab);
  const download = async (request: SentRequest) => {
    try {
      const detail = await getContractDetail(request.contractId);
      const content = [detail.current_version.title, `계약번호: ${contractNo(request.id)}`, `바이어: ${detail.parties.find((party) => party.role === "buyer")?.name ?? ""}`, `셀러: ${detail.parties.find((party) => party.role === "seller")?.name ?? ""}`, "", detail.current_version.body].join("\n");
      const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${contractNo(request.id)}-계약서.txt`; anchor.click(); URL.revokeObjectURL(url);
    } catch (error) { toast.error(friendlyApiError(error)); }
  };
  return <div><PageHeader title="체결 계약" description="서버에 저장된 서명 대기·체결 완료·종료 계약을 확인합니다." /><div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3"><Card className="p-4"><div className="text-xs text-muted-foreground">서명 대기</div><div className="mt-2 text-2xl font-bold text-[var(--warning)]">{contracts.filter((r) => statusFor(r) === "signing").length}건</div></Card><Card className="p-4"><div className="text-xs text-muted-foreground">체결 완료</div><div className="mt-2 text-2xl font-bold text-[var(--success)]">{contracts.filter((r) => statusFor(r) === "completed").length}건</div></Card><Card className="p-4"><div className="text-xs text-muted-foreground">종료</div><div className="mt-2 text-2xl font-bold text-muted-foreground">{contracts.filter((r) => statusFor(r) === "closed").length}건</div></Card></div><div className="mb-4 flex flex-wrap gap-2">{TABS.map((item) => <Button key={item.key} variant={tab === item.key ? "default" : "outline"} onClick={() => setTab(item.key)}>{item.label} <span className="ml-1 text-xs">{item.key === "all" ? contracts.length : contracts.filter((r) => statusFor(r) === item.key).length}</span></Button>)}</div><div className="overflow-hidden rounded-xl border border-border bg-card">{rows.length === 0 ? <div className="p-16 text-center text-muted-foreground"><FileCheck2 className="mx-auto mb-3 size-7" />해당 상태의 계약이 없습니다.</div> : rows.map((request) => <div key={request.id} className="flex flex-col gap-3 border-b p-5 last:border-b-0 md:flex-row md:items-center md:justify-between"><div><div className="font-mono text-xs text-[var(--ocean)]">{contractNo(request.id)}</div><h2 className="mt-1 font-semibold" style={{ color: "var(--navy)" }}>{request.title}</h2><p className="mt-1 text-sm text-muted-foreground">{request.buyer ?? "바이어"} · {request.serviceStartDate ?? ""} ~ {request.serviceEndDate ?? ""}</p></div><div className="flex flex-wrap items-center gap-2"><Badge className="border-transparent" style={{ background: statusFor(request) === "completed" ? "var(--success-soft)" : "var(--warning-soft)", color: statusFor(request) === "completed" ? "var(--success)" : "var(--warning)" }}>{label[statusFor(request)]}</Badge><Button size="sm" variant="outline" onClick={() => void download(request)}><Download className="mr-1 size-4" />다운로드</Button><Button size="sm" variant="outline" onClick={() => toast.info("계약 상세 API에서 현재 버전을 확인할 수 있습니다.")}><FileText className="mr-1 size-4" />상세</Button></div></div>)}</div></div>;
}
