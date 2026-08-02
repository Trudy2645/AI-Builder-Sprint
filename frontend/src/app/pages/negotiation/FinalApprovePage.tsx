import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Clock, FilePenLine, GitCompareArrows, PenLine } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { useRoleBase } from "../../hooks/useRoleBase";
import { approveContractVersion, friendlyApiError, getContractApprovals, getContractDetail, type ApprovalStatus, type ContractDetail } from "../../lib/api";

function ApprovalRow({ label, approved }: { label: string; approved: boolean }) {
  return <div className="flex items-center justify-between rounded-lg border border-border p-4"><span>{label}</span><span className="flex items-center gap-1.5 text-sm" style={{ color: approved ? "var(--success)" : "var(--warning)" }}>{approved ? <CheckCircle2 className="size-4" /> : <Clock className="size-4" />}{approved ? "승인 완료" : "승인 대기"}</span></div>;
}

export function FinalApprovePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { base, role } = useRoleBase();
  const contractId = params.get("contractId");
  const versionId = params.get("versionId");
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [approval, setApproval] = useState<ApprovalStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!contractId || !versionId) { setLoading(false); return; } void Promise.all([getContractDetail(contractId), getContractApprovals(contractId, versionId)]).then(([nextDetail, nextApproval]) => { setDetail(nextDetail); setApproval(nextApproval); }).catch((error) => toast.error(friendlyApiError(error))).finally(() => setLoading(false)); }, [contractId, versionId]);
  if (!contractId || !versionId) return <PageHeader title="검토할 계약을 선택해 주세요" description="계약 목록 또는 협상 화면에서 최종 검토를 시작해 주세요." />;
  if (loading) return <PageHeader title="최종안을 불러오는 중" description="현재 계약 버전과 승인 상태를 확인하고 있습니다." />;
  if (!detail || !approval) return <PageHeader title="계약을 불러올 수 없습니다" description="잠시 후 다시 시도해 주세요." />;
  const mine = role === "buyer" ? approval.buyer.approved : approval.seller.approved;
  const query = `?contractId=${contractId}&versionId=${versionId}`;
  const approve = async () => { setBusy(true); try { setApproval(await approveContractVersion(contractId, versionId)); toast.success("계약 버전을 승인했습니다."); } catch (error) { toast.error(friendlyApiError(error)); } finally { setBusy(false); } };
  return <div className="mx-auto max-w-[860px]"><PageHeader title="최종 계약 검토" description="양측 승인 상태와 서버의 현재 계약 버전을 확인합니다." /><div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={4} /></div><div className="mb-6 rounded-xl border border-border bg-card p-5"><div className="flex items-center justify-between gap-3"><div><p className="font-semibold" style={{ color: "var(--navy)" }}>{detail.current_version.title}</p><p className="text-sm text-muted-foreground">현재 버전 v{detail.current_version.version_no}</p></div><Button variant="outline" onClick={() => navigate(`${base}/signing/compare${query}`)}><GitCompareArrows className="mr-1 size-4" />버전 비교</Button></div></div><div className="mb-6 rounded-xl border border-border bg-card p-5"><h2 className="mb-4 font-semibold">승인 상태</h2><div className="grid gap-3 md:grid-cols-2"><ApprovalRow label="바이어" approved={approval.buyer.approved} /><ApprovalRow label="셀러" approved={approval.seller.approved} /></div></div><div className="flex flex-wrap justify-end gap-2 rounded-xl border border-border bg-card p-4"><Button variant="outline" onClick={() => navigate(role === "buyer" ? `${base}/explore/${detail.listing_id ?? ""}/revise` : `${base}/received`)}><FilePenLine className="mr-1 size-4" />수정 요청</Button>{!mine && <Button disabled={busy} style={{ background: "var(--navy)" }} onClick={() => void approve()}><CheckCircle2 className="mr-1 size-4" />승인</Button>}<Button disabled={!approval.all_approved} style={{ background: approval.all_approved ? "var(--teal)" : "var(--muted)" }} onClick={() => navigate(`${base}/signing/sign${query}`)}><PenLine className="mr-1 size-4" />전자서명<ArrowRight className="ml-1 size-4" /></Button></div></div>;
}
