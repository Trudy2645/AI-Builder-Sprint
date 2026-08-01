import { useEffect } from "react";
import { CheckCircle2, Clock, GitCompareArrows, ArrowRight, FilePenLine, GitBranch, PenLine } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useApp } from "../../context/AppContext";
import { useRoleBase } from "../../hooks/useRoleBase";
import { useNegotiation } from "../../store/NegotiationContext";
import { finalContractInfo, NEGOTIATION_CONTRACT_ID } from "../../data/negotiation";

function ApprovalRow({
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

export function FinalApprovePage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { role, base } = useRoleBase();
  const { buyerApproved, sellerApproved, bothApproved, approve } = useNegotiation();

  const myApproved = role === "buyer" ? buyerApproved : sellerApproved;

  // 데모에서는 현재 역할이 확인할 차례이며, 상대방은 먼저 승인한 상태로 준비한다.
  useEffect(() => {
    if (role === "buyer" && !sellerApproved) approve("seller");
    if (role === "seller" && !buyerApproved) approve("buyer");
  }, [role, buyerApproved, sellerApproved]);

  const requestMore = () => {
    if (role === "buyer") navigate(`${base}/explore/${NEGOTIATION_CONTRACT_ID}/revise`);
    else navigate(`${base}/received/rcv-summer`);
  };

  return (
    <div className="mx-auto max-w-[860px]">
      <PageHeader title={t("fa.title")} description={t("fa.subtitle")} />

      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <ContractStepper current={4} />
      </div>

      {/* Final document card */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <VersionBadge version="v4" />
            <div className="min-w-0">
              <div className="break-words" style={{ fontWeight: 700, color: "var(--navy)" }}>2026 부산 여름 객실 공급 계약</div>
              <div className="text-muted-foreground" style={{ fontSize: "13px" }}>
                {finalContractInfo.buyer} · {finalContractInfo.seller}
              </div>
            </div>
          </div>
          <Button
            variant="outline"
            className="w-full gap-1.5 whitespace-nowrap sm:w-auto"
            style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}
            onClick={() => navigate(`${base}/signing/compare`)}
          >
            <GitCompareArrows className="size-4" />
            {t("fa.viewCompare")}
          </Button>
        </div>
      </div>

      {/* Approval status */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <h2 className="mb-4 break-words" style={{ color: "var(--navy)", fontSize: "16px", fontWeight: 700 }}>
          {t("fa.approvalStatus")}
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <ApprovalRow label={t("fa.buyer")} name={finalContractInfo.buyer} approved={buyerApproved} approvedText={t("fa.approved")} waitingText={t("fa.waiting")} />
          <ApprovalRow label={t("fa.seller")} name={finalContractInfo.seller} approved={sellerApproved} approvedText={t("fa.approved")} waitingText={t("fa.waiting")} />
        </div>

        {bothApproved && (
          <div className="mt-4 flex items-start gap-2 break-words rounded-lg p-3" style={{ background: "var(--success-soft)", color: "var(--success)", fontSize: "13px", fontWeight: 600 }}>
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            {t("fa.bothApproved")}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end">
        <Button variant="ghost" className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ color: "var(--ocean)" }} onClick={requestMore}>
          {role === "buyer" ? <FilePenLine className="size-4" /> : <GitBranch className="size-4" />}
          {role === "buyer" ? t("fa.requestMore") : t("fa.reCounter")}
        </Button>

        {!myApproved && (
          <Button
            className="w-full gap-1.5 whitespace-nowrap sm:w-auto"
            style={{ background: "var(--navy)" }}
            onClick={() => {
              approve(role);
              toast.success(t("fa.approvedToast"));
            }}
          >
            <CheckCircle2 className="size-4" />
            {role === "buyer" ? t("fa.approveAsBuyer") : t("fa.approveAsSeller")}
          </Button>
        )}

        <Button
          className="w-full gap-1.5 whitespace-nowrap sm:w-auto"
          style={{ background: bothApproved ? "var(--teal)" : "var(--muted)", color: bothApproved ? "#fff" : "var(--muted-foreground)" }}
          disabled={!bothApproved}
          onClick={() => navigate(`${base}/signing/sign`)}
        >
          <PenLine className="size-4" />
          {t("fa.goSign")}
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
