import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CalendarDays, FileCheck2, FileText, UsersRound } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/requests/StatusBadge";
import { Button } from "../../components/ui/button";
import { useRequests, type RequestStatus, type SentRequest } from "../../store/RequestsContext";
import { friendlyApiError, getContractDetail, type ContractDetail } from "../../lib/api";

const STATUS_DESCRIPTION: Record<RequestStatus, string> = {
  draft: "계약 요청을 준비하고 있습니다.",
  reviewing: "셀러가 요청한 조건을 검토하고 있습니다.",
  responded: "셀러의 응답을 확인해 주세요.",
  negotiating: "수정 요청에 대한 협상이 진행 중입니다.",
  signing: "양측 확정이 완료되어 모두싸인 서명을 기다리고 있습니다.",
  completed: "양측의 전자서명이 완료된 계약입니다.",
  closed: "취소된 계약 요청입니다.",
};

function money(amount: number | undefined, currency: string | undefined): string {
  if (amount === undefined) return "금액 확인 중";
  return new Intl.NumberFormat("ko-KR", { style: "currency", currency: currency ?? "KRW", maximumFractionDigits: 0 }).format(amount);
}

function ContractRow({ request }: { request: SentRequest }) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className="w-full rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-[var(--ocean)] hover:bg-muted/30 sm:p-5"
      onClick={() => navigate(`/buyer/contracts/${request.contractId}/status`)}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="truncate text-base font-semibold" style={{ color: "var(--navy)" }}>{request.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{request.seller} · 요청일 {request.createdAt}</p>
        </div>
        <StatusBadge status={request.status} />
      </div>
      <div className="mt-4 grid grid-cols-1 gap-2 text-sm text-muted-foreground sm:grid-cols-3 sm:gap-4">
        <span className="flex items-center gap-1.5"><CalendarDays className="size-4" />{request.serviceStartDate ?? "-"} ~ {request.serviceEndDate ?? "-"}</span>
        <span className="flex items-center gap-1.5"><UsersRound className="size-4" />{request.guests ? `${request.guests}명` : "인원 미정"}</span>
        <span className="flex items-center gap-1.5"><FileText className="size-4" />{money(request.total, request.currency)}</span>
      </div>
    </button>
  );
}

export function BuyerContractsPage() {
  const { requests, loading, refreshRequests } = useRequests();
  const [status, setStatus] = useState<"all" | RequestStatus>("all");
  const contracts = useMemo(
    () => status === "all" ? requests : requests.filter((request) => request.status === status),
    [requests, status],
  );

  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader
        title="내 계약"
        description="서버에 저장된 계약 요청, 협상 진행 상황, 전자서명 완료 계약을 확인합니다."
        actions={<Button variant="outline" onClick={() => void refreshRequests().catch((error) => toast.error(friendlyApiError(error)))}>새로고침</Button>}
      />
      <div className="mb-5 flex flex-wrap gap-2">
        {(["all", "reviewing", "negotiating", "signing", "completed", "closed"] as const).map((item) => (
          <Button key={item} variant={status === item ? "default" : "outline"} size="sm" onClick={() => setStatus(item)}>
            {item === "all" ? "전체" : <StatusBadge status={item} />}
          </Button>
        ))}
      </div>
      {loading ? <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">계약을 불러오는 중입니다…</div> : contracts.length === 0 ? (
        <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">표시할 계약이 없습니다.</div>
      ) : <div className="space-y-3">{contracts.map((request) => <ContractRow key={request.id} request={request} />)}</div>}
    </div>
  );
}

export function BuyerContractStatusPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { requests } = useRequests();
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const request = requests.find((item) => item.contractId === id);

  useEffect(() => {
    if (!id) return;
    let active = true;
    void getContractDetail(id)
      .then((result) => { if (active) setDetail(result); })
      .catch((error) => { if (active) toast.error(friendlyApiError(error)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  if (!id) return <PageHeader title="계약을 찾을 수 없습니다" />;
  if (loading) return <PageHeader title="계약을 불러오는 중" description="현재 계약 상태를 확인하고 있습니다." />;
  if (!detail) return <div className="mx-auto max-w-[860px]"><PageHeader title="계약을 불러올 수 없습니다" /><Button onClick={() => navigate("/buyer/contracts")}>내 계약으로</Button></div>;

  const currentStatus = request?.status ?? (detail.status === "signed" ? "completed" : detail.status === "signing" ? "signing" : detail.status === "cancelled" ? "closed" : detail.status === "revision_requested" ? "negotiating" : "reviewing");
  const versionId = detail.current_version.id;
  const action = currentStatus === "signing"
    ? { label: "모두싸인 서명 현황", path: `/buyer/signing/sign?contractId=${id}&versionId=${versionId}` }
    : currentStatus === "completed"
      ? { label: "최종 계약 확인", path: `/buyer/signing/complete?contractId=${id}&versionId=${versionId}` }
      : { label: "협상 및 최종안 확인", path: `/buyer/signing?contractId=${id}&versionId=${versionId}` };

  return (
    <div className="mx-auto max-w-[860px]">
      <Button variant="ghost" className="mb-4" onClick={() => navigate("/buyer/contracts")}><ArrowLeft className="mr-1 size-4" />내 계약</Button>
      <PageHeader title="계약 상태" description={STATUS_DESCRIPTION[currentStatus]} />
      <div className="rounded-xl border border-border bg-card p-5 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><h2 className="text-lg font-semibold" style={{ color: "var(--navy)" }}>{detail.listing_title}</h2><p className="mt-1 text-sm text-muted-foreground">현재 버전 v{detail.current_version.version_no}</p></div><StatusBadge status={currentStatus} /></div>
        <div className="mt-5 grid gap-3 text-sm sm:grid-cols-2"><p><span className="text-muted-foreground">이용 기간 </span>{detail.service_start_date} ~ {detail.service_end_date}</p><p><span className="text-muted-foreground">예상 금액 </span>{money(detail.amount_minor ?? undefined, detail.currency ?? undefined)}</p></div>
        <div className="mt-5 border-t border-border pt-5"><p className="text-sm text-muted-foreground">계약 당사자</p><p className="mt-1">{detail.parties.map((party) => party.name).join(" · ")}</p></div>
        <div className="mt-6 flex justify-end"><Button onClick={() => navigate(action.path)}>{action.label}<ArrowRight className="ml-1 size-4" /></Button></div>
      </div>
      <div className="mt-5 rounded-xl border border-border bg-card p-5"><h2 className="flex items-center gap-2 font-semibold" style={{ color: "var(--navy)" }}><FileCheck2 className="size-4" />현재 계약 조항</h2><div className="mt-4 space-y-3">{detail.current_version.clauses.map((clause) => <div key={clause.id} className="rounded-lg border border-border p-4"><p className="font-medium">제{clause.clause_order}조 {clause.title}</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{clause.body}</p></div>)}</div></div>
    </div>
  );
}
