import { useEffect, useState } from "react";
import { ArrowRight, Clock3, GitCompareArrows, MessageSquareReply } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { useRequests } from "../../store/RequestsContext";
import { getContractVersions, type ContractVersionListItem } from "../../lib/api";

export function NegotiatingPage() {
  const navigate = useNavigate();
  const { requests, loading } = useRequests();
  const active = requests.find((request) => request.status === "negotiating" || request.status === "reviewing");
  const [versions, setVersions] = useState<ContractVersionListItem[]>([]);
  useEffect(() => { if (active) void getContractVersions(active.contractId).then(setVersions).catch(() => setVersions([])); }, [active]);
  if (loading) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">협상 목록을 불러오는 중입니다…</div>;
  if (!active) return <div className="mx-auto max-w-[720px] rounded-xl border border-dashed p-10 text-center"><Clock3 className="mx-auto mb-3 size-8 text-muted-foreground" /><h1 className="text-xl font-semibold" style={{ color: "var(--navy)" }}>진행 중인 협상이 없습니다</h1><p className="mt-2 text-sm text-muted-foreground">계약 요청이 셀러에게 전달되면 이곳에서 응답을 확인할 수 있습니다.</p><Button className="mt-5" style={{ background: "var(--navy)" }} onClick={() => navigate("/buyer/explore")}>계약 탐색으로</Button></div>;
  const currentVersion = versions.at(-1);
  return <div className="mx-auto max-w-[820px]"><PageHeader title="협상 진행" description="서버에 저장된 계약 요청과 버전 상태를 확인합니다." /><div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={3} /></div><div className="rounded-xl border border-border bg-card p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><Badge className="border-transparent bg-[var(--warning-soft)] text-[var(--warning)]">{active.status === "reviewing" ? "셀러 검토 중" : "협상 중"}</Badge><h2 className="mt-3 text-xl font-semibold" style={{ color: "var(--navy)" }}>{active.title}</h2><p className="mt-1 text-sm text-muted-foreground">{active.seller} · {active.createdAt}</p></div><div className="text-right text-sm text-muted-foreground">현재 버전<br /><span className="font-semibold text-foreground">{currentVersion ? `v${currentVersion.version_no}` : "확인 중"}</span></div></div>{active.message && <div className="mt-5 flex items-start gap-2 rounded-lg border border-[var(--ocean)] bg-[var(--info-soft)] p-3 text-sm"><MessageSquareReply className="mt-0.5 size-4 shrink-0" />{active.message}</div>}<div className="mt-5 flex flex-wrap justify-end gap-2"><Button variant="outline" disabled={!currentVersion} onClick={() => navigate(`/buyer/signing/compare?contractId=${active.contractId}`)}><GitCompareArrows className="mr-1 size-4" />버전 비교</Button><Button disabled={!currentVersion} style={{ background: "var(--navy)" }} onClick={() => { toast.info("셀러 응답과 계약 버전을 확인해 주세요."); navigate(`/buyer/signing?contractId=${active.contractId}&versionId=${currentVersion?.id ?? ""}`); }}>최종 검토<ArrowRight className="ml-1 size-4" /></Button></div></div></div>;
}
