import { ArrowLeft, ArrowRight, CheckCircle2, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { PageHeader } from "../../components/PageHeader";
import { friendlyApiError, getContractApprovals, getContractDetail, type ContractDetail } from "../../lib/api";

function formatDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10).replace(/-/g, ".") : "정보 없음";
}

function formatAmount(amount: number | null, currency: string | null): string {
  if (amount === null || amount === undefined) return "계약 조건에서 확인";
  return currency === "KRW"
    ? `${amount.toLocaleString("ko-KR")}원`
    : `${amount.toLocaleString("ko-KR")} ${currency ?? ""}`.trim();
}

function stepFor(status: string, sellerApproved: boolean): 2 | 3 | 4 | 5 | 6 {
  if (status === "seller_review") return sellerApproved ? 4 : 2;
  if (status === "revision_requested") return 3;
  if (status === "signing") return 5;
  if (status === "signed") return 6;
  return 4;
}

function statusLabel(status: string, sellerApproved: boolean): string {
  if (status === "seller_review") return sellerApproved ? "최종 검토 가능" : "셀러 검토 중";
  if (status === "revision_requested") return "협상 중";
  if (status === "signing") return "서명 대기";
  if (status === "signed") return "체결 완료";
  if (status === "cancelled") return "종료";
  return "계약 확인 중";
}

export function BuyerContractDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [sellerApproved, setSellerApproved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError("계약 식별자가 없습니다.");
      setLoading(false);
      return;
    }

    void getContractDetail(id)
      .then(async (detail) => {
        setContract(detail);
        if (detail.status === "seller_review") {
          const approvals = await getContractApprovals(detail.id, detail.current_version.id);
          setSellerApproved(approvals.seller.approved);
        }
      })
      .catch((reason: unknown) => setError(friendlyApiError(reason)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <PageHeader title="계약서를 불러오는 중" description="요청한 계약 내용을 확인하고 있습니다." />;
  if (error || !contract) return <PageHeader title="계약서를 불러올 수 없습니다" description={error ?? "잠시 후 다시 시도해 주세요."} />;

  const period = `${formatDate(contract.terms.start_date)} ~ ${formatDate(contract.terms.end_date)}`;
  const canReview = contract.status === "signing" || (contract.status === "seller_review" && sellerApproved);

  return (
    <div className="mx-auto max-w-[960px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate("/buyer/sent")}>
        <ArrowLeft className="size-4" />
        계약 관리로 돌아가기
      </Button>

      <PageHeader title="계약서 상세" description={`${contract.listing_title} · ${contract.initial_request_kind === "as_is" ? "조건 그대로" : "수정 요청"}`} />

      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={stepFor(contract.status, sellerApproved)} />
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-5">
        <div>
          <Badge className="border-transparent" style={{ background: canReview ? "var(--success-soft)" : "var(--warning-soft)", color: canReview ? "var(--success)" : "var(--warning)" }}>
            {statusLabel(contract.status, sellerApproved)}
          </Badge>
          <h2 className="mt-3 text-xl font-semibold" style={{ color: "var(--navy)" }}>{contract.current_version.title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">현재 버전 v{contract.current_version.version_no}</p>
        </div>
        {canReview && <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`/buyer/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`)}>
          최종 검토
          <ArrowRight className="ml-1 size-4" />
        </Button>}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
        <div><div className="text-xs text-muted-foreground">셀러</div><div className="mt-1 font-semibold">{contract.parties.find((party) => party.role === "seller")?.name ?? "셀러"}</div></div>
        <div><div className="text-xs text-muted-foreground">요청일</div><div className="mt-1 font-semibold">{formatDate(contract.created_at)}</div></div>
        <div><div className="text-xs text-muted-foreground">이용 기간</div><div className="mt-1 font-semibold">{period}</div></div>
        <div><div className="text-xs text-muted-foreground">계약 금액</div><div className="mt-1 font-semibold">{formatAmount(contract.amount_minor, contract.currency)}</div></div>
      </div>

      {!canReview && contract.status !== "signed" && (
        <div className="mb-4 flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          <FileText className="mt-0.5 size-5 shrink-0" style={{ color: "var(--ocean)" }} />
          <p>{contract.status === "seller_review" ? "셀러가 최종 승인하면 이 화면에서 최종 계약 내용을 확인하고 승인할 수 있습니다." : "현재 계약은 아직 최종 검토 단계가 아닙니다. 상태가 변경되면 이 화면에서 최종 검토를 시작할 수 있습니다."}</p>
        </div>
      )}

      <div className="space-y-4">
        {contract.current_version.clauses.map((clause) => (
          <section key={clause.id} className="rounded-xl border border-border bg-card p-5">
            <h3 className="flex items-center gap-2 text-base font-semibold" style={{ color: "var(--navy)" }}>
              <span style={{ color: "var(--ocean)" }}>제{clause.clause_order}조</span>
              {clause.title}
            </h3>
            <p className="mt-3 text-sm leading-7">{clause.body}</p>
          </section>
        ))}
      </div>

      <div className="mt-6 flex justify-end rounded-xl border border-border bg-card p-4">
        {contract.status === "signed" ? (
          <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--success)" }}><CheckCircle2 className="size-4" />체결 완료된 계약입니다.</div>
        ) : canReview ? (
          <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`/buyer/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`)}>최종 검토<ArrowRight className="ml-1 size-4" /></Button>
        ) : (
          <Button variant="outline" onClick={() => navigate("/buyer/sent")}>계약 관리로 돌아가기</Button>
        )}
      </div>
    </div>
  );
}
