import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, FileText } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import {
  approveContractVersion,
  friendlyApiError,
  getContractApprovals,
  getContractDetail,
  getSellerRevisionRequests,
  type ApprovalStatus,
  type ContractDetail,
} from "../../lib/api";

function formatDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10).replace(/-/g, ".") : "정보 없음";
}

function formatAmount(amount: number | null, currency: string | null): string {
  if (amount === null || amount === undefined) return "계약 조건에서 확인";
  return currency === "KRW"
    ? `${amount.toLocaleString("ko-KR")}원`
    : `${amount.toLocaleString("ko-KR")} ${currency ?? ""}`.trim();
}

function stepFor(status: string, sellerApproved = false): number {
  if (status === "seller_review" && sellerApproved) return 4;
  if (status === "seller_review") return 2;
  if (status === "revision_requested") return 3;
  if (status === "signing") return 5;
  if (status === "signed") return 6;
  return 3;
}

/** Resolves a contract-id entry point to the appropriate seller request screen. */
export function SellerReceivedRequestPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [approval, setApproval] = useState<ApprovalStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) {
      setError("계약 식별자가 없습니다.");
      return;
    }

    let active = true;

    const open = async () => {
      try {
        const detail = await getContractDetail(id);
        if (!active) return;
        setContract(detail);
        if (detail.status === "seller_review") {
          setApproval(await getContractApprovals(detail.id, detail.current_version.id).catch(() => null));
        }
        setLoading(false);

        try {
          const revisions = await getSellerRevisionRequests();
          const revision = revisions.find((item) => item.contract_id === id);
          if (active && revision) {
            navigate(`/seller/received/${revision.id}`, { replace: true });
          }
        } catch {
          // 계약 상세는 수정 요청 목록 API가 실패해도 계속 확인할 수 있다.
        }
      } catch (reason) {
        if (active) {
          setError(friendlyApiError(reason));
          setLoading(false);
        }
      }
    };

    void open();
    return () => {
      active = false;
    };
  }, [id, navigate]);

  if (loading) {
    return <PageHeader title="계약 요청을 여는 중" description="계약 상세 내용을 불러오고 있습니다." />;
  }

  if (error || !contract) {
    return <PageHeader title="계약을 불러올 수 없습니다" description={error} />;
  }

  const buyerName = contract.parties.find((party) => party.role === "buyer")?.name ?? "바이어";
  const period = `${formatDate(contract.terms.start_date)} ~ ${formatDate(contract.terms.end_date)}`;
  const sellerAlreadyApproved = Boolean(approval?.seller.approved);

  const approve = async () => {
    setSubmitting(true);
    try {
      const result = await approveContractVersion(contract.id, contract.current_version.id);
      toast.success(result.all_approved ? "양측 승인이 완료되었습니다." : "계약 요청을 승인했습니다. 바이어 승인을 기다립니다.");
      navigate(`/seller/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`);
    } catch (reason) {
      toast.error(friendlyApiError(reason));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[960px]">
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 gap-1.5 whitespace-nowrap"
        onClick={() => navigate("/seller/received")}
      >
        <ArrowLeft className="size-4" />
        받은 요청
      </Button>

      <PageHeader
        title={sellerAlreadyApproved ? "최종안 검토" : "계약 요청 검토"}
        description={`요청 바이어: ${buyerName} · ${contract.listing_title}`}
      />

      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={stepFor(contract.status, sellerAlreadyApproved)} />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
        <div>
          <div className="text-xs text-muted-foreground">요청일</div>
          <div className="mt-1 font-semibold">{formatDate(contract.created_at)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">계약 기간</div>
          <div className="mt-1 font-semibold">{period}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">예상 계약 금액</div>
          <div className="mt-1 font-semibold">{formatAmount(contract.amount_minor, contract.currency)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">현재 버전</div>
          <div className="mt-1 font-semibold" style={{ color: "var(--ocean)" }}>
            v{contract.current_version.version_no}
          </div>
        </div>
      </div>

      <div className="mb-4 flex items-start gap-3 rounded-xl border border-border bg-card p-4">
        <FileText className="mt-0.5 size-5 shrink-0" style={{ color: "var(--ocean)" }} />
        <div>
          <div className="font-semibold" style={{ color: "var(--navy)" }}>
            현재 계약서
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {sellerAlreadyApproved ? "셀러가 승인한 최종안을 확인하고 바이어의 최종 승인을 기다리는 중입니다." : "수정 조항별 요청이 아직 생성되지 않은 계약입니다. 현재 계약 조건을 먼저 확인해 주세요."}
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {contract.current_version.clauses.map((clause) => (
          <section key={clause.id} className="rounded-xl border border-border bg-card p-5">
            <h2 className="flex items-center gap-2 text-base" style={{ color: "var(--navy)" }}>
              <span style={{ color: "var(--ocean)" }}>제{clause.clause_order}조</span>
              {clause.title}
            </h2>
            <p className="mt-3 text-sm leading-7">{clause.body}</p>
          </section>
        ))}
      </div>

      <div className="mt-6 flex justify-end rounded-xl border border-border bg-card p-4">
        {contract.status === "seller_review" && sellerAlreadyApproved ? (
          <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`)}>
            최종안 확인
            <ArrowRight className="ml-1 size-4" />
          </Button>
        ) : contract.status === "seller_review" ? (
          <Button disabled={submitting} style={{ background: "var(--navy)" }} onClick={() => void approve()}>
            <CheckCircle2 className="mr-1 size-4" />
            요청 승인
            <ArrowRight className="ml-1 size-4" />
          </Button>
        ) : contract.status === "signing" ? (
          <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`)}>
            최종 검토
            <ArrowRight className="ml-1 size-4" />
          </Button>
        ) : (
          <Button variant="outline" onClick={() => navigate("/seller/received")}>
            받은 요청으로 돌아가기
          </Button>
        )}
      </div>
    </div>
  );
}
