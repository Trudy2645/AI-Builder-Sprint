import { useMemo } from "react";
import { ArrowRight, CheckCircle2, Clock3, GitBranch, MessagesSquare, XCircle } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { friendlyApiError, getContractDetail } from "../../lib/api";
import { useRequests, type SentRequest } from "../../store/RequestsContext";

type WorkflowStage = "seller_counter" | "seller_rejection" | "final_approval" | "buyer_cancelled";
type Tab = "all" | WorkflowStage;

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "all", label: "전체" },
  { key: "seller_counter", label: "셀러 대안 도착" },
  { key: "seller_rejection", label: "셀러 수정 거절" },
  { key: "final_approval", label: "최종 승인 진행" },
  { key: "buyer_cancelled", label: "바이어 거절로 종료" },
];

const STAGE_TONE: Record<WorkflowStage, { bg: string; color: string; icon: typeof GitBranch }> = {
  seller_counter: { bg: "var(--info-soft)", color: "var(--ocean)", icon: GitBranch },
  seller_rejection: { bg: "var(--warning-soft)", color: "var(--warning)", icon: XCircle },
  final_approval: { bg: "var(--success-soft)", color: "var(--success)", icon: CheckCircle2 },
  buyer_cancelled: { bg: "var(--muted)", color: "var(--muted-foreground)", icon: XCircle },
};

function workflowStage(request: SentRequest): WorkflowStage | null {
  switch (request.revisionStatus) {
    case "countered":
    case "partially_accepted":
      return "seller_counter";
    case "rejected":
      return request.revisionResponseMessage ? "buyer_cancelled" : "seller_rejection";
    case "accepted":
      return request.sellerApproved ? null : "final_approval";
    case "cancelled":
      return "buyer_cancelled";
    default:
      return null;
  }
}

function badgeLabel(request: SentRequest, stage: WorkflowStage): string {
  if (stage === "final_approval") {
    return request.finalApprovalRequested ? "셀러 최종 승인 대기" : "바이어 최종 검토";
  }
  return TABS.find((tab) => tab.key === stage)?.label ?? "협상 관리";
}

export function NegotiatingPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { requests, loading } = useRequests();
  const selected = params.get("status") as Tab | null;
  const tab: Tab = selected && TABS.some((item) => item.key === selected) ? selected : "all";

  const rows = useMemo(() => requests
    .map((request) => ({ request, stage: workflowStage(request) }))
    .filter((row): row is { request: SentRequest; stage: WorkflowStage } => row.stage !== null), [requests]);
  const visibleRows = tab === "all" ? rows : rows.filter((row) => row.stage === tab);
  const counts = useMemo(() => TABS.reduce<Record<string, number>>((result, item) => {
    result[item.key] = item.key === "all" ? rows.length : rows.filter((row) => row.stage === item.key).length;
    return result;
  }, {}), [rows]);

  const open = async (request: SentRequest, stage: WorkflowStage) => {
    if ((stage === "seller_counter" || stage === "seller_rejection") && request.revisionRequestId) {
      navigate(`/buyer/sent/revision/${request.revisionRequestId}`);
      return;
    }

    if (stage === "final_approval") {
      try {
        const detail = await getContractDetail(request.contractId);
        navigate(`/buyer/signing?contractId=${detail.id}&versionId=${detail.current_version.id}`);
      } catch (error) {
        toast.error(friendlyApiError(error));
      }
      return;
    }

    navigate(`/buyer/sent/contract/${request.contractId}`);
  };

  return (
    <div className="mx-auto max-w-[1000px]">
      <PageHeader title="협상 관리" description="셀러가 보낸 대안·거절 응답과 최종 승인 상태를 확인합니다." />

      <div className="mb-5 flex flex-wrap gap-2">
        {TABS.map((item) => {
          const active = tab === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => (item.key === "all" ? setParams({}) : setParams({ status: item.key }))}
              className="flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 transition-colors"
              style={{ borderColor: active ? "var(--navy)" : "var(--border)", background: active ? "var(--navy)" : "var(--card)", color: active ? "#fff" : "var(--foreground)", fontSize: "13px" }}
            >
              {item.label}
              <span className="rounded-full px-1.5" style={{ fontSize: "11px", background: active ? "rgba(255,255,255,0.25)" : "var(--muted)", color: active ? "#fff" : "var(--muted-foreground)" }}>
                {counts[item.key] ?? 0}
              </span>
            </button>
          );
        })}
      </div>

      {loading ? (
        <Card className="border-dashed p-16 text-center text-muted-foreground">계약 요청을 불러오는 중입니다…</Card>
      ) : visibleRows.length === 0 ? (
        <Card className="flex flex-col items-center justify-center gap-3 border-dashed p-10 text-center sm:p-16">
          <MessagesSquare className="size-7" style={{ color: "var(--ocean)" }} />
          <p className="text-muted-foreground">해당 상태의 계약이 없습니다.</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {visibleRows.map(({ request, stage }) => {
            const tone = STAGE_TONE[stage];
            const Icon = tone.icon;
            return (
              <Card key={request.id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="min-w-0">
                    <Badge className="gap-1 border-transparent" style={{ background: tone.bg, color: tone.color }}>
                      <Icon className="size-3.5" />
                      {badgeLabel(request, stage)}
                    </Badge>
                    <h2 className="mt-3 truncate text-lg font-semibold" style={{ color: "var(--navy)" }}>{request.title}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{request.seller} · {request.createdAt}</p>
                  </div>
                  <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => void open(request, stage)}>
                    계약 진행상황 보기
                    <ArrowRight className="size-4" />
                  </Button>
                </div>
                {stage === "seller_counter" && <p className="mt-4 flex items-center gap-1.5 text-sm text-muted-foreground"><Clock3 className="size-4" />셀러가 보낸 대안에 대해 수락·거절·추가 수정을 선택할 수 있습니다.</p>}
                {stage === "seller_rejection" && <p className="mt-4 flex items-center gap-1.5 text-sm text-muted-foreground"><Clock3 className="size-4" />셀러가 수정 요청을 거절했습니다. 수락하거나 계약을 종료할 수 있습니다.</p>}
                {stage === "final_approval" && <p className="mt-4 flex items-center gap-1.5 text-sm text-muted-foreground"><CheckCircle2 className="size-4" />최종 계약 내용을 확인하고 바이어 최종 승인을 진행합니다.</p>}
                {stage === "buyer_cancelled" && <p className="mt-4 flex items-center gap-1.5 text-sm text-muted-foreground"><XCircle className="size-4" />바이어가 협상을 거절하여 계약이 종료되었습니다.</p>}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
