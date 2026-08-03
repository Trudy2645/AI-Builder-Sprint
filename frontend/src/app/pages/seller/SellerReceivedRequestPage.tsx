import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Clock3, FileText, XCircle } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import {
  friendlyApiError,
  getContractApprovals,
  getContractDetail,
  getSellerRevisionRequests,
  type ApprovalStatus,
  type ContractDetail,
  type SellerRevisionRequestListItem,
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

function stepFor(status: string, sellerApproved = false, buyerApproved = false, revisionStatus?: SellerRevisionRequestListItem["status"], finalApprovalRequested = false): number {
  if (revisionStatus === "countered" || revisionStatus === "partially_accepted" || revisionStatus === "rejected") return 3;
  if (revisionStatus === "cancelled") return 3;
  if (revisionStatus === "accepted" || finalApprovalRequested || buyerApproved || (status === "seller_review" && sellerApproved)) return 4;
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
  const [revision, setRevision] = useState<SellerRevisionRequestListItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          const latestRevision = revisions
            .filter((item) => item.contract_id === id)
            .sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0] ?? null;
          if (active) setRevision(latestRevision);
          if (active && latestRevision?.status === "sent") {
            navigate(`/seller/negotiating/revision/${latestRevision.id}`, { replace: true });
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
  const buyerAlreadyApproved = Boolean(approval?.buyer.approved);
  const sellerAlreadyApproved = Boolean(approval?.seller.approved);
  const sellerCounterWaiting = revision?.status === "countered" || revision?.status === "partially_accepted";
  const sellerRejectionWaiting = revision?.status === "rejected" && !revision.response_message;
  const buyerCancelled = revision?.status === "cancelled" || contract.status === "cancelled";
  const asIsRequest = contract.initial_request_kind === "as_is";
  const finalApprovalRequested = Boolean(approval?.final_approval_requested || contract.final_approval_requested);
  const waitingForBuyerFinalReview = contract.status === "seller_review" && !buyerAlreadyApproved && !sellerAlreadyApproved && !sellerCounterWaiting && !sellerRejectionWaiting && !buyerCancelled;
  const sellerApprovalReady = contract.status === "seller_review" && buyerAlreadyApproved && !sellerAlreadyApproved && !sellerCounterWaiting && !sellerRejectionWaiting && !buyerCancelled;
  const currentContractMessage = sellerCounterWaiting
    ? "셀러가 대안 조건을 제시했습니다. 바이어가 수락하거나 추가 수정을 보내면 협상이 이어집니다."
    : sellerRejectionWaiting
      ? "셀러가 수정 요청을 거절했습니다. 바이어의 거절 수락 또는 계약 종료 응답을 기다리는 중입니다."
        : buyerCancelled
          ? "바이어가 협상을 거절하여 계약이 종료되었습니다."
          : waitingForBuyerFinalReview
            ? asIsRequest
              ? "바이어가 조건 그대로 진행을 요청했습니다. 계약 내용은 변경되지 않았습니다. 바이어가 최종 검토 후 최종 승인하면 셀러 승인 요청이 도착합니다."
              : "바이어가 셀러 응답을 확인하고 최종 계약 내용을 검토하는 중입니다. 바이어 최종 승인 후 셀러 승인을 진행할 수 있습니다."
            : sellerAlreadyApproved
              ? buyerAlreadyApproved
                ? "셀러 최종 승인이 완료되었습니다. 모두싸인 요청을 준비할 수 있습니다."
                : "셀러 최종 승인이 완료되었습니다. 바이어의 최종 승인을 기다리는 중입니다."
              : sellerApprovalReady
                ? "바이어 최종 승인이 도착했습니다. 최종 계약 내용을 확인한 뒤 셀러 최종 승인을 진행해 주세요."
                : finalApprovalRequested
                  ? "바이어의 최종 승인을 기다리는 중입니다. 바이어가 승인하면 셀러 승인 버튼이 활성화됩니다."
                  : "현재 계약 조건을 확인하고 바이어 최종 승인을 기다리는 중입니다.";

  return (
    <div className="mx-auto max-w-[960px]">
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 gap-1.5 whitespace-nowrap"
        onClick={() => navigate("/seller/negotiating")}
      >
        <ArrowLeft className="size-4" />
        협상 관리
      </Button>

      <PageHeader
        title={sellerCounterWaiting ? "계약 진행상황" : sellerRejectionWaiting ? "수정 거절 응답 대기" : sellerAlreadyApproved ? "최종안 검토" : buyerCancelled ? "바이어 거절로 종료" : "계약 요청 검토"}
        description={sellerCounterWaiting ? `${contract.listing_title} · 셀러가 보낸 대안 조건에 대한 바이어 응답을 기다리고 있습니다.` : `요청 바이어: ${buyerName} · ${contract.listing_title}`}
      />

      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={stepFor(contract.status, sellerAlreadyApproved, buyerAlreadyApproved, revision?.status, finalApprovalRequested)} />
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
            {currentContractMessage}
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
        {buyerCancelled ? (
          <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground"><XCircle className="size-4" />바이어 거절로 종료된 계약입니다.</div>
        ) : sellerRejectionWaiting ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Clock3 className="size-4" />바이어의 응답을 기다리는 중입니다.</div>
        ) : sellerCounterWaiting ? (
          <Button variant="outline" onClick={() => navigate("/seller/negotiating")}>협상 관리로 돌아가기</Button>
        ) : contract.status === "seller_review" && sellerAlreadyApproved ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><CheckCircle2 className="size-4" style={{ color: "var(--success)" }} />바이어 최종 승인 대기 중입니다.</div>
        ) : sellerApprovalReady ? (
          <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`)}>
            최종 검토
            <ArrowRight className="ml-1 size-4" />
          </Button>
        ) : waitingForBuyerFinalReview ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Clock3 className="size-4" />바이어 최종 승인 대기 중입니다.</div>
        ) : contract.status === "seller_review" ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Clock3 className="size-4" />바이어 최종 승인을 기다리는 중입니다.</div>
        ) : contract.status === "signing" ? (
          <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`)}>
            최종 검토
            <ArrowRight className="ml-1 size-4" />
          </Button>
        ) : (
          <Button variant="outline" onClick={() => navigate("/seller/negotiating")}>
            협상 관리로 돌아가기
          </Button>
        )}
      </div>
    </div>
  );
}
