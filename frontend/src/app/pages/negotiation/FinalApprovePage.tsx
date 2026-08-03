import { useCallback, useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Clock, PenLine } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { useRoleBase } from "../../hooks/useRoleBase";
import {
  approveContractVersion,
  dispatchSignatureRequest,
  friendlyApiError,
  getContractApprovals,
  getContractDetail,
  getBuyerRevisionRequests,
  getMyContracts,
  getSellerReceivedContracts,
  type ApprovalStatus,
  type ContractDetail,
} from "../../lib/api";

function ApiApprovalRow({ label, approved }: { label: string; approved: boolean }) {
  const Icon = approved ? CheckCircle2 : Clock;
  return (
    <div className="flex items-center justify-between rounded-lg border border-border p-4">
      <span>{label}</span>
      <span className="flex items-center gap-1.5 text-sm" style={{ color: approved ? "var(--success)" : "var(--warning)" }}>
        <Icon className="size-4" />
        {approved ? "승인 완료" : "승인 대기"}
      </span>
    </div>
  );
}

export function FinalApprovePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { role, base } = useRoleBase();
  const contractId = params.get("contractId");
  const versionId = params.get("versionId");
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [approval, setApproval] = useState<ApprovalStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [revisionAccepted, setRevisionAccepted] = useState(false);
  const [sendingSignatureRequest, setSendingSignatureRequest] = useState(false);
  const [signatureRequestSent, setSignatureRequestSent] = useState(false);
  const [pendingContracts, setPendingContracts] = useState<Array<{ id: string; title: string; status: string }>>([]);

  const loadApiState = useCallback(async (showLoading: boolean) => {
    if (!contractId || !versionId) return;
    if (showLoading) setLoading(true);
    try {
      const [contract, approvals, revisions] = await Promise.all([
        getContractDetail(contractId),
        getContractApprovals(contractId, versionId),
        getBuyerRevisionRequests().catch(() => []),
      ]);
      setDetail(contract);
      setApproval(approvals);
      const latestRevision = revisions
        .filter((revision) => revision.contract_id === contractId)
        .sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0];
      setRevisionAccepted(latestRevision?.status === "accepted");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [contractId, versionId]);

  useEffect(() => {
    if (!contractId || !versionId) {
      setLoading(false);
      return;
    }
    void loadApiState(true);
  }, [contractId, versionId, loadApiState]);

  useEffect(() => {
    if (!detail || !approval || detail.status !== "seller_review" || approval.all_approved) return;
    const interval = window.setInterval(() => void loadApiState(false), 3000);
    return () => window.clearInterval(interval);
  }, [approval, detail, loadApiState]);

  useEffect(() => {
    if (contractId || versionId) return;
    const load = role === "buyer"
      ? getMyContracts().then((items) => items.map((item) => ({ id: item.id, title: item.listing_title, status: item.status })))
      : getSellerReceivedContracts().then((items) => items.map((item) => ({ id: item.contract_id, title: item.listing_title, status: item.status })));
    void load
      .then((items) => setPendingContracts(items.filter((item) => ["seller_review", "revision_requested", "signing"].includes(item.status))))
      .catch((error) => toast.error(friendlyApiError(error)));
  }, [contractId, versionId, role]);

  const approveApi = async () => {
    if (!contractId || !versionId) return;
    setSubmitting(true);
    try {
      const next = await approveContractVersion(contractId, versionId);
      setApproval(next);
      if (next.all_approved) {
        toast.success("양측 최종 승인이 완료되었습니다. 모두싸인 요청을 보내 서명을 시작해 주세요.");
        return;
      }
      toast.success(role === "buyer" ? "바이어 최종 승인이 완료되었습니다. 셀러에게 승인 요청을 보냈습니다." : "셀러 최종 승인이 완료되었습니다. 모두싸인 요청을 준비할 수 있습니다.");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  const sendSignatureRequest = async () => {
    if (!contractId || !versionId || !approval?.all_approved) return;
    setSendingSignatureRequest(true);
    try {
      const request = await dispatchSignatureRequest(contractId, versionId);
      setSignatureRequestSent(true);
      toast.success("모두싸인 서명 요청을 발송했습니다.");
      navigate(`${base}/signing/sign?contractId=${contractId}&versionId=${versionId}&signatureRequestId=${request.id}`, { replace: true });
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSendingSignatureRequest(false);
    }
  };


  if (contractId || versionId) {
    if (!contractId || !versionId) return <PageHeader title="계약을 선택해 주세요" description="계약 목록 또는 상세 화면에서 최종 검토를 시작해 주세요." />;
    if (loading) return <PageHeader title="최종안을 불러오는 중" description="현재 계약 버전과 승인 상태를 확인하고 있습니다." />;
    if (!detail || !approval) return <PageHeader title="계약을 불러올 수 없습니다" description="잠시 후 다시 시도해 주세요." />;
    const mine = role === "buyer" ? approval.buyer.approved : approval.seller.approved;
    const sellerReviewWaiting = detail.status === "seller_review" && !approval.seller.approved;
    const asIsReview = detail.initial_request_kind === "as_is" && detail.status === "seller_review";
    const finalApprovalStage = asIsReview || revisionAccepted || approval.buyer.approved || approval.seller.approved || approval.all_approved;
    const currentStep = detail.status === "signed" ? 6 : detail.status === "signing" ? 5 : finalApprovalStage ? 4 : 2;
    const canApprove = detail.status === "seller_review" && !mine && (
      (role === "buyer" && finalApprovalStage) ||
      (role === "seller" && approval.buyer.approved)
    );
    const waitingForCounterpartyApproval = !approval.all_approved && (
      role === "buyer" ? approval.buyer.approved : !approval.buyer.approved
    );
    const finalApprovalAndSigningWait = finalApprovalStage && detail.status !== "signing" && detail.status !== "signed";
    return (
      <div className="mx-auto max-w-[860px]">
        <PageHeader
          title={finalApprovalAndSigningWait ? "최종안 승인 및 서명 대기" : sellerReviewWaiting ? (asIsReview ? "최종 계약 정보 확인" : role === "buyer" ? "셀러 검토 중" : "계약 요청 검토") : detail.status === "signing" ? "서명 대기" : "최종안 승인"}
          description={approval.all_approved
            ? "양측 최종 승인이 완료되었습니다. 모두싸인 요청을 보내 서명을 시작하세요."
            : role === "buyer"
              ? approval.buyer.approved
                ? "바이어 승인이 완료되었습니다. 셀러의 최종 승인을 기다리고 있습니다."
                : "최종 계약 내용을 확인한 뒤 바이어 최종 승인을 진행하세요."
              : approval.buyer.approved
                ? "바이어 승인이 완료되었습니다. 셀러 최종 승인을 진행하세요."
                : "바이어의 최종 승인을 기다리고 있습니다."}
        />
        <div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={currentStep} /></div>
        {finalApprovalStage && !approval.all_approved && (
          <div className="mb-6 rounded-xl border border-[var(--ocean)] bg-[var(--info-soft)] p-4 text-sm" style={{ color: "var(--ocean)" }}>
            {role === "buyer"
              ? approval.buyer.approved
                ? "바이어 최종 승인이 완료되어 셀러에게 승인 요청이 전달되었습니다."
                : "계약 내용을 확인한 뒤 아래의 바이어 최종 승인 버튼을 눌러 주세요."
              : approval.buyer.approved
                ? "바이어 최종 승인이 도착했습니다. 아래의 셀러 최종 승인 버튼을 눌러 주세요."
                : "바이어가 최종 승인하면 셀러 최종 승인 버튼이 활성화됩니다."}
          </div>
        )}
        <div className="mb-6 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold" style={{ color: "var(--navy)" }}>{detail.current_version.title}</p>
              <p className="text-sm text-muted-foreground">현재 버전 v{detail.current_version.version_no}</p>
            </div>
          </div>
        </div>
        <div className="mb-6 rounded-xl border border-border bg-card p-5">
          <h2 className="mb-4 font-semibold" style={{ color: "var(--navy)" }}>최종 계약 내용</h2>
          <div className="space-y-3">
            {detail.current_version.clauses.map((clause) => (
              <section key={clause.id} className="rounded-lg border border-border p-4">
                <h3 className="font-semibold"><span className="mr-2" style={{ color: "var(--ocean)" }}>제{clause.clause_order}조</span>{clause.title}</h3>
                <p className="mt-2 text-sm leading-7">{clause.body}</p>
              </section>
            ))}
          </div>
        </div>
        <div className="mb-6 rounded-xl border border-border bg-card p-5">
          <h2 className="mb-4 font-semibold">승인 상태</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <ApiApprovalRow label="바이어" approved={approval.buyer.approved} />
            <ApiApprovalRow label="셀러" approved={approval.seller.approved} />
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 rounded-xl border border-border bg-card p-4">
          {finalApprovalStage && !approval.all_approved && (
            <Button
              disabled={submitting || !canApprove}
              style={{ background: canApprove ? "var(--navy)" : "var(--muted)", color: canApprove ? "#fff" : "var(--muted-foreground)" }}
              onClick={() => void approveApi()}
            >
              <CheckCircle2 className="mr-1 size-4" />
              {role === "buyer" ? (approval.buyer.approved ? "바이어 최종 승인 완료" : "바이어 최종 승인") : (approval.seller.approved ? "셀러 최종 승인 완료" : "셀러 최종 승인")}
              {!approval[role].approved && <ArrowRight className="ml-1 size-4" />}
            </Button>
          )}
          {approval.all_approved && !signatureRequestSent && <Button disabled={sendingSignatureRequest} style={{ background: "var(--teal)" }} onClick={() => void sendSignatureRequest()}>
            <PenLine className="mr-1 size-4" />모두싸인 요청<ArrowRight className="ml-1 size-4" />
          </Button>}
          {detail.status === "seller_review" && waitingForCounterpartyApproval && !approval.all_approved && (
            <span className="inline-flex items-center rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
              {role === "seller" ? "바이어 최종 승인 대기" : "셀러 최종 승인 대기"}
            </span>
          )}
          {detail.status === "signing" && !canApprove && !approval.all_approved && (
            <span className="inline-flex items-center rounded-md bg-[var(--warning-soft)] px-3 py-2 text-sm" style={{ color: "var(--warning)" }}>
              모두싸인 서명 대기 중
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[860px]">
      <PageHeader title="최종안 승인" description="계약을 선택한 뒤 현재 버전과 양측 승인 상태를 확인하세요." />
      <div className="rounded-xl border border-border bg-card p-5">
        {pendingContracts.length === 0 ? <p className="py-8 text-center text-muted-foreground">최종안 확인이 필요한 계약이 없습니다.</p> : (
          <div className="space-y-3">{pendingContracts.map((contract) => (
            <div key={contract.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-4">
              <div><p className="font-semibold" style={{ color: "var(--navy)" }}>{contract.title}</p><p className="mt-1 text-sm text-muted-foreground">{contract.status === "signing" ? "모두싸인 서명 대기" : "최종안 승인 대기"}</p></div>
              <Button onClick={() => void getContractDetail(contract.id).then((detail) => navigate(`${base}/signing?contractId=${contract.id}&versionId=${detail.current_version.id}`)).catch((error) => toast.error(friendlyApiError(error)))}>최종안 확인</Button>
            </div>
          ))}</div>
        )}
      </div>
    </div>
  );

}
