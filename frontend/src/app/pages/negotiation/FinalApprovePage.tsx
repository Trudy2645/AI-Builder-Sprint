import { useEffect, useState } from "react";
import { CheckCircle2, Clock, GitCompareArrows, ArrowRight, FilePenLine, GitBranch, PenLine } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { useApp } from "../../context/AppContext";
import { useRoleBase } from "../../hooks/useRoleBase";
import { approveContractVersion, friendlyApiError, getContractApprovals, getContractDetail, type ApprovalStatus, type ContractDetail } from "../../lib/api";

function ApprovalRow({ label, approved }: { label: string; approved: boolean }) {
  const Icon = approved ? CheckCircle2 : Clock;
  return <div className="flex items-center justify-between rounded-lg border border-border p-4"><span>{label}</span><span className="flex items-center gap-1.5 text-sm" style={{ color: approved ? "var(--success)" : "var(--warning)" }}><Icon className="size-4" />{approved ? "승인 완료" : "승인 대기"}</span></div>;
}

export function FinalApprovePage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { role, base } = useRoleBase();
  const contractId = params.get("contractId");
  const versionId = params.get("versionId");
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [approval, setApproval] = useState<ApprovalStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    if (!contractId || !versionId) { setLoading(false); return; }
    try {
      const [contract, approvals] = await Promise.all([getContractDetail(contractId), getContractApprovals(contractId, versionId)]);
      setDetail(contract); setApproval(approvals);
    } catch (error) { toast.error(friendlyApiError(error)); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [contractId, versionId]);

  const approve = async () => {
    if (!contractId || !versionId) return;
    setSubmitting(true);
    try { setApproval(await approveContractVersion(contractId, versionId)); toast.success(t("fa.approvedToast")); }
    catch (error) { toast.error(friendlyApiError(error)); }
    finally { setSubmitting(false); }
  };
  if (!contractId || !versionId) return <PageHeader title="계약을 선택해 주세요" description="계약 목록 또는 상세 화면에서 최종 검토를 시작해 주세요." />;
  if (loading) return <PageHeader title="최종안을 불러오는 중" description="현재 계약 버전과 승인 상태를 확인하고 있습니다." />;
  if (!detail || !approval) return <PageHeader title="계약을 불러올 수 없습니다" description="잠시 후 다시 시도해 주세요." />;
  const mine = role === "buyer" ? approval.buyer.approved : approval.seller.approved;
  const query = `?contractId=${contractId}&versionId=${versionId}`;
  return <div className="mx-auto max-w-[860px]">
    <PageHeader title={t("fa.title")} description={t("fa.subtitle")} />
    <div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={4} /></div>
    <div className="mb-6 rounded-xl border border-border bg-card p-5"><div className="flex items-center justify-between gap-3"><div><p className="font-semibold" style={{ color: "var(--navy)" }}>{detail.current_version.title}</p><p className="text-sm text-muted-foreground">현재 버전 v{detail.current_version.version_no}</p></div><Button variant="outline" onClick={() => navigate(`${base}/signing/compare${query}`)}><GitCompareArrows className="mr-1 size-4" />버전 비교</Button></div></div>
    <div className="mb-6 rounded-xl border border-border bg-card p-5"><h2 className="mb-4 font-semibold">승인 상태</h2><div className="grid gap-3 md:grid-cols-2"><ApprovalRow label="바이어" approved={approval.buyer.approved} /><ApprovalRow label="셀러" approved={approval.seller.approved} /></div></div>
    <div className="flex flex-wrap justify-end gap-2 rounded-xl border border-border bg-card p-4"><Button variant="outline" onClick={() => navigate(role === "buyer" ? `${base}/explore` : `${base}/received`)}>{role === "buyer" ? <FilePenLine className="mr-1 size-4" /> : <GitBranch className="mr-1 size-4" />}수정 요청</Button>{!mine && <Button disabled={submitting} style={{ background: "var(--navy)" }} onClick={() => void approve()}><CheckCircle2 className="mr-1 size-4" />승인</Button>}<Button disabled={!approval.all_approved} style={{ background: approval.all_approved ? "var(--teal)" : "var(--muted)" }} onClick={() => navigate(`${base}/signing/sign${query}`)}><PenLine className="mr-1 size-4" />전자서명 <ArrowRight className="ml-1 size-4" /></Button></div>
  </div>;
}
