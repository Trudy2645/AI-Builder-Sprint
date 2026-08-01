import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  FilePenLine,
  GitCompareArrows,
  MessageSquareReply,
  Sparkles,
} from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { StatusBadge } from "../../components/requests/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Separator } from "../../components/ui/separator";
import { formatKRW } from "../../data/contracts";
import {
  NEGOTIATION_CONTRACT_ID,
  finalContractInfo,
  getVersionDiff,
  versionMetas,
} from "../../data/negotiation";
import { useRequests, type SentRequest } from "../../store/RequestsContext";
import { useNegotiation } from "../../store/NegotiationContext";

const TIMELINE = [
  {
    version: "v1" as const,
    title: "셀러 공개 원본",
    description: "공개 공고 조건으로 계약 요청을 시작했습니다.",
  },
  {
    version: "v2" as const,
    title: "바이어 수정 요청",
    description: "취소, 노쇼, 정산 조건을 명확히 해달라고 요청했습니다.",
  },
  {
    version: "v3" as const,
    title: "셀러 응답안",
    description: "셀러가 무료 취소 기한과 수수료를 대안으로 제시했습니다.",
  },
  {
    version: "v4" as const,
    title: "최종 합의안",
    description: "양측이 전자서명으로 넘길 수 있는 최종안을 만들었습니다.",
  },
];

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-3">
      <div className="text-xs font-semibold text-muted-foreground">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold" style={{ color: "var(--navy)" }}>
        {value}
      </div>
    </div>
  );
}

function RequestPreview({ request }: { request: SentRequest }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={request.status} />
            <Badge variant="outline" className="whitespace-nowrap">
              {request.currentVersion ?? "v3"}
            </Badge>
          </div>
          <h2 className="mt-3 break-words text-lg font-semibold" style={{ color: "var(--navy)" }}>
            {request.title}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {request.seller} · 요청일 {request.createdAt}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <MetricCard label="요청 유형" value={request.type === "asis" ? "조건 그대로" : "수정 요청"} />
        <MetricCard label="수정 조항" value={`${request.revisions?.length ?? 0}개`} />
        <MetricCard label="예상 금액" value={request.total ? formatKRW(request.total) : formatKRW(finalContractInfo.estimatedTotal)} />
      </div>

      {request.latestResponse && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border p-3" style={{ borderColor: "var(--ocean)", background: "var(--info-soft)" }}>
          <MessageSquareReply className="mt-0.5 size-4 shrink-0" style={{ color: "var(--ocean)" }} />
          <p className="text-sm leading-6" style={{ color: "var(--navy)" }}>
            {request.latestResponse}
          </p>
        </div>
      )}
    </div>
  );
}

export function NegotiatingPage() {
  const navigate = useNavigate();
  const { requests, updateRequestStatus } = useRequests();
  const { approve } = useNegotiation();
  const activeRequest = useMemo(
    () =>
      requests.find((request) => request.id === "req-summer-main") ??
      requests.find((request) => request.status === "responded" || request.status === "negotiating") ??
      requests[0],
    [requests],
  );
  const finalDiff = getVersionDiff("v4");

  const goFinalReview = () => {
    if (activeRequest) {
      updateRequestStatus(activeRequest.id, "signing", {
        currentVersion: "v4",
        latestResponse: "최종 합의안(v4)을 승인하고 전자서명 단계로 이동했습니다.",
      });
    }
    approve("seller");
    toast.success("최종 합의안을 확인했습니다.");
    navigate("/buyer/signing");
  };

  if (!activeRequest) {
    return (
      <div className="mx-auto max-w-[720px] rounded-xl border border-dashed border-border bg-card p-10 text-center sm:p-14">
        <Clock3 className="mx-auto mb-3 size-8" style={{ color: "var(--muted-foreground)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--navy)" }}>
          진행 중인 협상이 없습니다
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">공고를 탐색하고 수정 요청을 보내면 이곳에서 응답을 확인할 수 있습니다.</p>
        <Button className="mt-5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate("/buyer/explore")}>
          계약 탐색으로
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1040px]">
      <PageHeader
        title="협상 중"
        description="셀러 응답을 확인하고 최종 합의안으로 전자서명을 진행하세요."
        actions={
          <Button variant="outline" className="gap-1.5 whitespace-nowrap" onClick={() => navigate("/buyer/sent")}>
            보낸 요청
          </Button>
        }
      />

      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <ContractStepper current={3} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-5">
          <RequestPreview request={activeRequest} />

          <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold" style={{ color: "var(--navy)" }}>
                  버전 진행 타임라인
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">원본부터 최종 합의안까지 변경 흐름을 한 화면에서 확인합니다.</p>
              </div>
              <Button
                variant="outline"
                className="gap-1.5 whitespace-nowrap"
                style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}
                onClick={() => navigate("/buyer/signing/compare")}
              >
                <GitCompareArrows className="size-4" />
                버전 비교
              </Button>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-4">
              {TIMELINE.map((item, index) => {
                const meta = versionMetas[item.version];
                const isFinal = item.version === "v4";
                return (
                  <div
                    key={item.version}
                    className="rounded-lg border p-4"
                    style={{
                      borderColor: isFinal ? "var(--teal)" : "var(--border)",
                      background: isFinal ? "var(--success-soft)" : "var(--card)",
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <VersionBadge version={item.version} />
                      <span className="text-xs font-semibold text-muted-foreground">{index + 1}/4</span>
                    </div>
                    <div className="mt-3 text-sm font-semibold" style={{ color: "var(--navy)" }}>
                      {item.title}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.description}</p>
                    <div className="mt-3 text-xs text-muted-foreground">{meta.authorName} · {meta.date}</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
            <div className="flex items-center gap-2 font-semibold" style={{ color: "var(--ocean)" }}>
              <Sparkles className="size-4" />
              AI 변경 요약
            </div>
            <ul className="mt-3 space-y-2">
              {finalDiff?.aiSummary.map((line, index) => (
                <li key={line} className="flex gap-2 text-sm leading-6">
                  <span className="font-bold" style={{ color: "var(--ocean)" }}>{index + 1}</span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>

            <Separator className="my-4" />

            <div className="grid gap-3 md:grid-cols-3">
              {finalDiff?.changes.map((change) => (
                <div key={change.clauseNo} className="rounded-lg border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold" style={{ color: "var(--ocean)" }}>
                      {change.clauseNo}
                    </span>
                    <span className="text-sm font-semibold">{change.title}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{change.note}</p>
                  <div className="mt-3 rounded-md p-2 text-xs leading-5" style={{ background: "var(--info-soft)" }}>
                    {change.newText}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-4 xl:sticky xl:top-6">
            <div className="flex items-center gap-2 font-semibold" style={{ color: "var(--navy)" }}>
              <CheckCircle2 className="size-4" style={{ color: "var(--teal)" }} />
              다음 액션
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              셀러 응답안이 최종 합의안으로 정리되었습니다. 바이어가 최종안을 승인하면 모두싸인 전자서명 단계로 넘어갑니다.
            </p>

            <div className="mt-4 space-y-2">
              <Button className="w-full gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={goFinalReview}>
                최종안 승인으로 이동
                <ArrowRight className="size-4" />
              </Button>
              <Button
                variant="outline"
                className="w-full gap-1.5 whitespace-nowrap"
                style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}
                onClick={() => navigate(`/buyer/explore/${NEGOTIATION_CONTRACT_ID}/revise`)}
              >
                <FilePenLine className="size-4" />
                추가 수정 요청
              </Button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
