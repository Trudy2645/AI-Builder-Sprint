import { ArrowLeft, CheckCircle2, Clock3, MessageSquareReply } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { PageHeader } from "../../components/PageHeader";
import { friendlyApiError, getContractDetail, getRevisionRequest, respondRevisionRequest, type ContractDetail, type RevisionRequestResponse } from "../../lib/api";

function statusLabel(status: RevisionRequestResponse["status"]): string {
  if (status === "sent") return "셀러 검토 중";
  if (status === "countered" || status === "partially_accepted") return "응답 도착";
  if (status === "accepted") return "수정 요청 반영 완료";
  if (status === "rejected") return "수정 요청 거절";
  return "수정 요청";
}

function requestTypeLabel(type: RevisionRequestResponse["items"][number]["request_type"]): string {
  if (type === "modify") return "문구 수정";
  if (type === "delete") return "조항 삭제";
  return "조항 추가";
}

export function BuyerRevisionRequestPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [revision, setRevision] = useState<RevisionRequestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) {
      setError("수정 요청 식별자가 없습니다.");
      setLoading(false);
      return;
    }

    const load = async () => {
      const request = await getRevisionRequest(id);
      const detail = await getContractDetail(request.contract_id);
      setRevision(request);
      setContract(detail);
    };

    void load()
      .catch((reason: unknown) => setError(friendlyApiError(reason)))
      .finally(() => setLoading(false));
  }, [id]);

  const clauses = useMemo(() => new Map((contract?.current_version.clauses ?? []).map((clause) => [clause.id, clause])), [contract]);

  if (loading) return <PageHeader title="수정 요청을 불러오는 중" description="요청한 수정 조항을 확인하고 있습니다." />;
  if (error || !contract || !revision) return <PageHeader title="수정 요청을 불러올 수 없습니다" description={error ?? "잠시 후 다시 시도해 주세요."} />;

  const responseArrived = revision.status === "countered" || revision.status === "partially_accepted" || revision.status === "accepted" || revision.status === "rejected";
  const buyerCanRespond = revision.status === "countered" || revision.status === "partially_accepted";

  const respond = async (decision: "accepted" | "rejected") => {
    setSubmitting(true);
    try {
      await respondRevisionRequest(revision.id, {
        decision,
        message: decision === "accepted" ? "셀러 응답을 수락합니다." : "셀러 응답을 수락하지 않고 추가 검토를 요청합니다.",
      });
      const nextRevision = await getRevisionRequest(revision.id);
      setRevision(nextRevision);
      if (decision === "accepted") {
        const nextContract = await getContractDetail(contract.id);
        toast.success("셀러 응답을 수락했습니다. 최종안을 확인해 주세요.");
        navigate(`/buyer/signing?contractId=${contract.id}&versionId=${nextContract.current_version.id}`);
      } else {
        toast.success("셀러 응답을 종료했습니다. 추가 수정 요청을 보낼 수 있습니다.");
      }
    } catch (reason) {
      toast.error(friendlyApiError(reason));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[960px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate("/buyer/sent")}>
        <ArrowLeft className="size-4" />
        계약 관리로 돌아가기
      </Button>
      <PageHeader title="수정 요청 상세" description={`${contract.listing_title} · 셀러에게 보낸 수정 조항을 확인하세요.`} />

      <div className="mb-6 rounded-xl border border-border bg-card p-5"><ContractStepper current={3} /></div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-5">
        <div>
          <Badge className="border-transparent" style={{ background: responseArrived ? "var(--info-soft)" : "var(--warning-soft)", color: responseArrived ? "var(--ocean)" : "var(--warning)" }}>
            {statusLabel(revision.status)}
          </Badge>
          <h2 className="mt-3 text-xl font-semibold" style={{ color: "var(--navy)" }}>{contract.current_version.title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">기준 버전 v{revision.base_version_no} · 요청 조항 {revision.items.length}개</p>
        </div>
        {revision.status === "accepted" && (contract.status === "seller_review" || contract.status === "signing") && <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`/buyer/signing?contractId=${contract.id}&versionId=${contract.current_version.id}`)}>{contract.status === "signing" ? "서명 대기" : "최종안 검토"}</Button>}
      </div>

      {revision.message && <div className="mb-4 rounded-xl border border-border bg-card p-4"><div className="text-sm font-semibold" style={{ color: "var(--navy)" }}>요청 메시지</div><p className="mt-2 text-sm leading-6">{revision.message}</p></div>}

      <div className="space-y-4">
        {revision.items.map((item, index) => {
          const clause = item.clause_id ? clauses.get(item.clause_id) : undefined;
          return (
            <section key={item.id} className="rounded-xl border border-border bg-card p-5">
              <div className="flex flex-wrap items-center gap-2"><span className="flex size-7 items-center justify-center rounded-full bg-[var(--navy)] text-sm font-semibold text-white">{index + 1}</span><span className="font-semibold" style={{ color: "var(--navy)" }}>{clause ? `제${clause.clause_order}조 ${clause.title}` : "새 요청 조항"}</span><Badge variant="outline">{requestTypeLabel(item.request_type)}</Badge></div>
              {clause && <div className="mt-4 rounded-lg border bg-muted/20 p-3 text-sm leading-6"><div className="mb-1 text-xs font-semibold text-muted-foreground">기존 계약 문구</div>{clause.body}</div>}
              <div className="mt-3 rounded-lg border border-[var(--ocean)] bg-[var(--info-soft)] p-3 text-sm leading-6"><div className="mb-1 text-xs font-semibold" style={{ color: "var(--ocean)" }}>바이어 요청 문구</div>{item.requested_text ?? "해당 조항을 삭제해 주세요."}</div>
              <div className="mt-3 rounded-lg border p-3 text-sm leading-6"><div className="mb-1 text-xs font-semibold text-muted-foreground">수정 사유</div>{item.reason}</div>
              {item.decision === "countered" && item.counter_text && <div className="mt-3 flex items-start gap-2 rounded-lg border border-[var(--ocean)] bg-[var(--info-soft)] p-3 text-sm leading-6"><MessageSquareReply className="mt-0.5 size-4 shrink-0" style={{ color: "var(--ocean)" }} /><div><div className="mb-1 text-xs font-semibold" style={{ color: "var(--ocean)" }}>셀러 대안 문구</div>{item.counter_text}</div></div>}
            </section>
          );
        })}
      </div>

      <div className="mt-6 rounded-xl border border-border bg-card p-4">
        {buyerCanRespond ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--ocean)" }}><CheckCircle2 className="size-4" />셀러 응답을 확인하고 선택하세요.</div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" disabled={submitting} onClick={() => navigate(`/buyer/sent/contract/${contract.id}/revise`)}>추가 수정 제안</Button>
              <Button variant="outline" disabled={submitting} onClick={() => void respond("rejected")}>응답 거절</Button>
              <Button disabled={submitting} style={{ background: "var(--navy)" }} onClick={() => void respond("accepted")}>응답 수락</Button>
            </div>
          </div>
        ) : revision.status === "rejected" ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--warning)" }}><CheckCircle2 className="size-4" />수정 요청이 종료되었습니다. 원래 조건으로 진행하거나 다시 제안할 수 있습니다.</div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" onClick={() => navigate(`/buyer/sent/contract/${contract.id}/revise`)}>추가 수정 요청</Button>
              <Button onClick={() => navigate(`/buyer/sent/contract/${contract.id}`)}>원래 조건으로 진행</Button>
            </div>
          </div>
        ) : responseArrived ? (
          <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--ocean)" }}><CheckCircle2 className="size-4" />셀러 응답이 도착했습니다.</div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Clock3 className="size-4" />셀러 검토를 기다리는 중입니다.</div>
        )}
      </div>
    </div>
  );
}
