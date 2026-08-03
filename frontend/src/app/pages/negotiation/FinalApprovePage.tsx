import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Clock, FilePenLine, GitBranch, PenLine } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { useApp } from "../../context/AppContext";
import { useRoleBase } from "../../hooks/useRoleBase";
import { useNegotiation } from "../../store/NegotiationContext";
import { finalContractInfo, NEGOTIATION_CONTRACT_ID } from "../../data/negotiation";
import {
  approveContractVersion,
  friendlyApiError,
  getContractApprovals,
  getContractDetail,
  type ApprovalStatus,
  type ContractDetail,
} from "../../lib/api";

function DemoApprovalRow({
  label,
  name,
  approved,
  approvedText,
  waitingText,
}: {
  label: string;
  name: string;
  approved: boolean;
  approvedText: string;
  waitingText: string;
}) {
  const color = approved ? "var(--success)" : "var(--warning)";
  const bg = approved ? "var(--success-soft)" : "var(--warning-soft)";
  const Icon = approved ? CheckCircle2 : Clock;
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>{label}</div>
        <div className="truncate" style={{ fontWeight: 600 }}>{name}</div>
      </div>
      <span className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1" style={{ background: bg, color, fontSize: "13px", fontWeight: 600 }}>
        <Icon className="size-4" />
        {approved ? approvedText : waitingText}
      </span>
    </div>
  );
}

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
  const { buyerApproved, sellerApproved, bothApproved, approve: approveDemo } = useNegotiation();

  useEffect(() => {
    if (contractId || versionId) return;
    if (role === "buyer" && !sellerApproved) approveDemo("seller");
    if (role === "seller" && !buyerApproved) approveDemo("buyer");
  }, [role, buyerApproved, sellerApproved, approveDemo, contractId, versionId]);

  useEffect(() => {
    if (!contractId || !versionId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    void Promise.all([getContractDetail(contractId), getContractApprovals(contractId, versionId)])
      .then(([contract, approvals]) => {
        setDetail(contract);
        setApproval(approvals);
      })
      .catch((error) => toast.error(friendlyApiError(error)))
      .finally(() => setLoading(false));
  }, [contractId, versionId]);

  const approveApi = async () => {
    if (!contractId || !versionId) return;
    setSubmitting(true);
    try {
      setApproval(await approveContractVersion(contractId, versionId));
      toast.success(t("fa.approvedToast"));
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  if (contractId || versionId) {
    if (!contractId || !versionId) return <PageHeader title="계약을 선택해 주세요" description="계약 목록 또는 상세 화면에서 최종 검토를 시작해 주세요." />;
    if (loading) return <PageHeader title="최종안을 불러오는 중" description="현재 계약 버전과 승인 상태를 확인하고 있습니다." />;
    if (!detail || !approval) return <PageHeader title="계약을 불러올 수 없습니다" description="잠시 후 다시 시도해 주세요." />;
    const mine = role === "buyer" ? approval.buyer.approved : approval.seller.approved;
    const query = `?contractId=${contractId}&versionId=${versionId}`;
    return (
      <div>
        <PageHeader title={t("fa.title")} description={t("fa.subtitle")} />
        <div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={4} /></div>
        <div className="mb-6 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold" style={{ color: "var(--navy)" }}>{detail.current_version.title}</p>
            </div>
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
          <Button variant="outline" onClick={() => navigate(role === "buyer" ? `${base}/explore` : `${base}/received`)}>
            {role === "buyer" ? <FilePenLine className="mr-1 size-4" /> : <GitBranch className="mr-1 size-4" />}수정 요청
          </Button>
          {!mine && <Button disabled={submitting} style={{ background: "var(--navy)" }} onClick={() => void approveApi()}><CheckCircle2 className="mr-1 size-4" />승인</Button>}
          <Button disabled={!approval.all_approved} style={{ background: approval.all_approved ? "var(--teal)" : "var(--muted)" }} onClick={() => navigate(`${base}/signing/sign${query}`)}>
            <PenLine className="mr-1 size-4" />전자서명 <ArrowRight className="ml-1 size-4" />
          </Button>
        </div>
      </div>
    );
  }

  const myApproved = role === "buyer" ? buyerApproved : sellerApproved;
  const requestMore = () => {
    if (role === "buyer") navigate(`${base}/explore/${NEGOTIATION_CONTRACT_ID}/revise`);
    else navigate(`${base}/received/rcv-coastline`);
  };

  return (
    <div>
      <PageHeader title={t("fa.title")} description={t("fa.subtitle")} />

      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <ContractStepper current={4} />
      </div>

      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <div className="min-w-0">
              <div className="break-words" style={{ fontWeight: 700, color: "var(--navy)" }}>2026 해운대 단체 객실 공급 계약</div>
              <div className="text-muted-foreground" style={{ fontSize: "13px" }}>
                {finalContractInfo.buyer} · {finalContractInfo.seller}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <h2 className="mb-4 break-words" style={{ color: "var(--navy)", fontSize: "16px", fontWeight: 700 }}>{t("fa.approvalStatus")}</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <DemoApprovalRow label={t("fa.buyer")} name={finalContractInfo.buyer} approved={buyerApproved} approvedText={t("fa.approved")} waitingText={t("fa.waiting")} />
          <DemoApprovalRow label={t("fa.seller")} name={finalContractInfo.seller} approved={sellerApproved} approvedText={t("fa.approved")} waitingText={t("fa.waiting")} />
        </div>

        {bothApproved && (
          <div className="mt-4 flex items-start gap-2 break-words rounded-lg p-3" style={{ background: "var(--success-soft)", color: "var(--success)", fontSize: "13px", fontWeight: 600 }}>
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            {t("fa.bothApproved")}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end">
        <Button variant="ghost" className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ color: "var(--ocean)" }} onClick={requestMore}>
          {role === "buyer" ? <FilePenLine className="size-4" /> : <GitBranch className="size-4" />}
          {role === "buyer" ? t("fa.requestMore") : t("fa.reCounter")}
        </Button>

        {!myApproved && (
          <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: "var(--navy)" }} onClick={() => { approveDemo(role); toast.success(t("fa.approvedToast")); }}>
            <CheckCircle2 className="size-4" />
            {role === "buyer" ? t("fa.approveAsBuyer") : t("fa.approveAsSeller")}
          </Button>
        )}

        <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: bothApproved ? "var(--teal)" : "var(--muted)", color: bothApproved ? "#fff" : "var(--muted-foreground)" }} disabled={!bothApproved} onClick={() => navigate(`${base}/signing/sign`)}>
          <PenLine className="size-4" />
          {t("fa.goSign")}
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
