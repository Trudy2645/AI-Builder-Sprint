import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, GitCompareArrows } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useRoleBase } from "../../hooks/useRoleBase";
import { useRequests } from "../../store/RequestsContext";
import { compareContractVersions, friendlyApiError, getContractVersions, type ContractVersionCompare, type ContractVersionListItem } from "../../lib/api";

function version(value: number): "v1" | "v2" | "v3" | "v4" { return `v${Math.min(4, Math.max(1, value))}` as "v1" | "v2" | "v3" | "v4"; }

export function VersionComparePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { base, role } = useRoleBase();
  const { requests } = useRequests();
  const contractId = params.get("contractId") ?? requests[0]?.contractId;
  const [versions, setVersions] = useState<ContractVersionListItem[]>([]);
  const [from, setFrom] = useState(1);
  const [to, setTo] = useState(2);
  const [comparison, setComparison] = useState<ContractVersionCompare | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!contractId) { setLoading(false); return; }
    void getContractVersions(contractId).then((next) => { setVersions(next); if (next.length > 1) { setFrom(next[0].version_no); setTo(next[next.length - 1].version_no); } }).catch((error) => toast.error(friendlyApiError(error))).finally(() => setLoading(false));
  }, [contractId]);
  useEffect(() => { if (contractId && from < to) void compareContractVersions(contractId, from, to).then(setComparison).catch((error) => toast.error(friendlyApiError(error))); }, [contractId, from, to]);
  const current = useMemo(() => versions.find((item) => item.version_no === to), [versions, to]);
  if (loading) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">계약 버전을 불러오는 중입니다…</div>;
  if (!contractId || versions.length < 2) return <PageHeader title="비교할 계약 버전이 없습니다" description="서버에 두 개 이상의 계약 버전이 생성된 뒤 다시 시도해 주세요." />;
  return <div className="mx-auto max-w-[960px]"><Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate(`${base}/signing?contractId=${contractId}&versionId=${current?.id ?? ""}`)}><ArrowLeft className="size-4" />최종 검토</Button><PageHeader title="계약 버전 비교" description="서버가 저장한 계약 버전과 변경 요약을 비교합니다." /><div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={4} /></div><div className="mb-5 flex flex-wrap items-center justify-center gap-3 rounded-xl border border-border bg-card p-5"><select className="rounded-md border px-3 py-2" value={from} onChange={(event) => setFrom(Number(event.target.value))}>{versions.filter((item) => item.version_no < to).map((item) => <option key={item.id} value={item.version_no}>v{item.version_no} · {item.title}</option>)}</select><ArrowRight className="size-5" style={{ color: "var(--ocean)" }} /><select className="rounded-md border px-3 py-2" value={to} onChange={(event) => setTo(Number(event.target.value))}>{versions.filter((item) => item.version_no > from).map((item) => <option key={item.id} value={item.version_no}>v{item.version_no} · {item.title}</option>)}</select></div>{comparison && <><div className="grid gap-3 md:grid-cols-3"><div className="rounded-lg border bg-muted/20 p-3 text-sm">추가 {comparison.clause_summary.added}개</div><div className="rounded-lg border bg-muted/20 p-3 text-sm">삭제 {comparison.clause_summary.deleted}개</div><div className="rounded-lg border bg-muted/20 p-3 text-sm">수정 {comparison.clause_summary.modified}개</div></div><div className="mt-5 space-y-4">{comparison.clause_changes.map((change, index) => <div key={`${change.change_type}-${index}`} className="rounded-xl border border-border bg-card p-5"><div className="flex flex-wrap items-center gap-2"><Badge>{change.change_type}</Badge><span className="font-semibold">{change.after?.title ?? change.before?.title ?? "조항"}</span></div><div className="mt-3 grid gap-3 md:grid-cols-2"><div className="rounded-lg border p-3 text-sm leading-6"><div className="mb-1 text-xs text-muted-foreground">v{comparison.from_version.version_no}</div>{change.before?.body ?? "없음"}</div><div className="rounded-lg border border-[var(--ocean)] bg-[var(--info-soft)] p-3 text-sm leading-6"><div className="mb-1 text-xs text-muted-foreground">v{comparison.to_version.version_no}</div>{change.after?.body ?? "삭제됨"}</div></div></div>)}</div><div className="mt-6 flex justify-end rounded-xl border border-border bg-card p-4"><Button style={{ background: "var(--navy)" }} onClick={() => { toast.success("서버 버전 비교를 확인했습니다."); navigate(`${base}/signing?contractId=${contractId}&versionId=${current?.id ?? ""}`); }}><CheckCircle2 className="mr-1 size-4" />최종 검토로 이동</Button></div></>}</div>;
}
