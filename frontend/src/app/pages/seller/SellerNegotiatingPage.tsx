import { useMemo, useState } from "react";
import {
  MessagesSquare,
  ChevronDown,
  ChevronUp,
  Building2,
  CalendarClock,
  Send,
  CheckCircle2,
  XCircle,
  Check,
  X,
  GitBranch,
  Clock,
  Sparkles,
} from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { useRequests, type SentRequest } from "../../store/RequestsContext";
import { useNegotiation } from "../../store/NegotiationContext";
import { getContract, formatKRW } from "../../data/contracts";

const BUYER_NAME = "GlobalTrip Japan";
const NEGOTIATING_STATUSES: SentRequest["status"][] = ["reviewing", "responded", "negotiating"];

interface CompareRow {
  label: string;
  buyer: string;
  seller: string;
  tone: "accept" | "reject" | "counter" | "same" | "pending";
}

const toneMeta: Record<CompareRow["tone"], { text: string; color: string; bg: string; icon: typeof Check }> = {
  accept: { text: "요청 수락", color: "var(--success)", bg: "var(--success-soft)", icon: Check },
  reject: { text: "기존 유지", color: "var(--coral)", bg: "var(--coral-soft)", icon: X },
  counter: { text: "셀러 대안 제시", color: "var(--ocean)", bg: "var(--info-soft)", icon: GitBranch },
  same: { text: "변경 없음", color: "var(--muted-foreground)", bg: "var(--muted)", icon: Check },
  pending: { text: "검토 중", color: "var(--warning)", bg: "var(--warning-soft)", icon: Clock },
};

function buildComparison(request: SentRequest): CompareRow[] {
  const contract = getContract(request.contractId);
  const findRevision = (keyword: string) => request.revisions?.find((r) => r.clauseTitle.includes(keyword));

  const cancelRev = findRevision("취소");
  const settleRev = findRevision("정산");

  const decisionTone = (kind?: "accept" | "reject" | "counter"): CompareRow["tone"] =>
    kind === "accept" ? "accept" : kind === "reject" ? "reject" : kind === "counter" ? "counter" : "pending";

  const quantityLabel =
    [request.rooms ? `${request.rooms}실` : "", request.guests ? `${request.guests}명` : ""]
      .filter(Boolean)
      .join(" · ") || "-";

  return [
    {
      label: "이용 기간",
      buyer: contract?.details.period ?? "-",
      seller: contract?.details.period ?? "-",
      tone: "same",
    },
    {
      label: "인원 / 객실 수",
      buyer: quantityLabel,
      seller: quantityLabel,
      tone: "same",
    },
    {
      label: "단가",
      buyer: contract ? `${contract.priceUnit} ${formatKRW(contract.unitPrice)}` : "-",
      seller: contract ? `${contract.priceUnit} ${formatKRW(contract.unitPrice)}` : "-",
      tone: "same",
    },
    {
      label: "총액",
      buyer: request.total ? formatKRW(request.total) : "-",
      seller: request.total ? formatKRW(request.total) : "-",
      tone: "same",
    },
    {
      label: "취소 규정",
      buyer: cancelRev?.requested ?? contract?.details.cancellation ?? "-",
      seller: cancelRev?.sellerResponse ?? (cancelRev ? "검토 중" : contract?.details.cancellation ?? "-"),
      tone: cancelRev ? decisionTone(cancelRev.sellerDecision) : "same",
    },
    {
      label: "정산 조건",
      buyer: settleRev?.requested ?? contract?.details.settlement ?? "-",
      seller: settleRev?.sellerResponse ?? (settleRev ? "검토 중" : contract?.details.settlement ?? "-"),
      tone: settleRev ? decisionTone(settleRev.sellerDecision) : "same",
    },
  ];
}

interface TimelineItem {
  label: string;
  date: string;
  who: "buyer" | "seller";
  note: string;
}

function buildTimeline(request: SentRequest, signedAt?: string): TimelineItem[] {
  const items: TimelineItem[] = [
    {
      label: "셀러 공고 공개",
      date: "-",
      who: "seller",
      note: `${request.title} 공고를 등록·공개했습니다.`,
    },
    {
      label: "바이어 수정 요청",
      date: request.createdAt,
      who: "buyer",
      note: `${request.revisions?.length ?? 0}개 조항에 대해 수정을 요청했습니다.`,
    },
  ];

  if (request.status !== "reviewing" && request.latestResponse) {
    items.push({
      label: "셀러 응답 제출",
      date: "진행 중",
      who: "seller",
      note: request.latestResponse,
    });
  }

  if (request.status === "signing" || request.status === "completed") {
    items.push({
      label: "최종 합의 완료",
      date: "진행 중",
      who: "seller",
      note: "양측이 최종안에 합의해 전자서명 절차로 넘어갔습니다.",
    });
  }

  if (request.status === "completed" && signedAt) {
    items.push({
      label: "전자서명 체결 완료",
      date: signedAt,
      who: "seller",
      note: "전자서명이 완료되어 계약이 체결되었습니다.",
    });
  }

  return items;
}

function RequestCard({ request }: { request: SentRequest }) {
  const navigate = useNavigate();
  const { updateRequestStatus } = useRequests();
  const { approve, signedAt } = useNegotiation();
  const [open, setOpen] = useState(false);
  const isMain = request.id === "req-summer-main";

  const rows = useMemo(() => buildComparison(request), [request]);
  const timeline = useMemo(() => buildTimeline(request, signedAt), [request, signedAt]);

  const sendProposal = () => {
    if (request.status === "reviewing") {
      toast.error("먼저 조항별 검토를 완료한 뒤 제안을 보낼 수 있습니다.");
      navigate(`/seller/received/${isMain ? "rcv-summer" : request.id}`);
      return;
    }
    updateRequestStatus(request.id, "negotiating", {
      latestResponse: "셀러가 제안 내용을 바이어에게 다시 전달했습니다.",
    });
    toast.success("바이어에게 제안을 보냈습니다.");
  };

  const requestFinalAgreement = () => {
    updateRequestStatus(request.id, "signing", {
      latestResponse: "양측이 최종 조건에 합의해 서명 대기 상태로 전환되었습니다.",
    });
    if (isMain) {
      approve("seller");
      toast.success("최종 합의를 요청했습니다. 서명 대기 화면으로 이동합니다.");
      navigate("/seller/signing");
    } else {
      toast.success("최종 합의를 요청했습니다. 서명 대기 상태로 전환되었습니다.");
    }
  };

  const endNegotiation = () => {
    if (!window.confirm("이 협상을 종료하시겠습니까? 종료 후에는 계속 진행할 수 없습니다.")) return;
    updateRequestStatus(request.id, "closed", {
      latestResponse: "셀러가 협상을 종료했습니다.",
    });
    toast.success("협상을 종료했습니다.");
    setOpen(false);
  };

  const statusLabel =
    request.status === "reviewing" ? "검토 대기" : request.status === "responded" ? "셀러 응답 도착" : "협상 중";
  const statusColor =
    request.status === "reviewing" ? "var(--warning)" : request.status === "responded" ? "var(--ocean)" : "var(--teal)";
  const statusBg =
    request.status === "reviewing" ? "var(--warning-soft)" : request.status === "responded" ? "var(--info-soft)" : "var(--success-soft)";

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge className="border-transparent whitespace-nowrap" style={{ background: statusBg, color: statusColor }}>
              {statusLabel}
            </Badge>
          </div>
          <h2 className="break-words" style={{ color: "var(--navy)" }}>{request.title}</h2>
          <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
            <Building2 className="size-3.5 shrink-0" />
            {BUYER_NAME}
            <span>·</span>
            <CalendarClock className="size-3.5 shrink-0" />
            최신 수정일 {request.latestResponse ? "진행 중" : request.createdAt}
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-muted-foreground">예상 계약 금액</div>
          <div className="mt-1 text-lg font-bold" style={{ color: "var(--navy)" }}>{formatKRW(request.total || 0)}</div>
        </div>
      </div>

      <Button
        variant="ghost"
        size="sm"
        className="mt-3 gap-1.5 whitespace-nowrap"
        style={{ color: "var(--ocean)" }}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        {open ? "상세 닫기" : "상세 보기"}
      </Button>

      {open && (
        <div className="mt-4 flex flex-col gap-6 border-t border-border pt-5">
          {/* Condition comparison */}
          <div>
            <h3 className="mb-3 text-sm font-semibold" style={{ color: "var(--navy)" }}>조건 비교 · 바이어 원안 vs 셀러 제안안</h3>
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="grid grid-cols-[1fr_1.4fr_1.4fr] gap-0 bg-muted/40 px-3 py-2 text-xs font-semibold text-muted-foreground">
                <div>항목</div>
                <div>바이어 원안(요청)</div>
                <div>셀러 제안안</div>
              </div>
              {rows.map((row) => {
                const meta = toneMeta[row.tone];
                const Icon = meta.icon;
                return (
                  <div key={row.label} className="grid grid-cols-[1fr_1.4fr_1.4fr] items-start gap-0 border-t border-border px-3 py-3 text-sm">
                    <div className="font-semibold">{row.label}</div>
                    <div className="pr-2 text-muted-foreground" style={{ fontSize: "13px", lineHeight: 1.6 }}>{row.buyer}</div>
                    <div>
                      <p style={{ fontSize: "13px", lineHeight: 1.6 }}>{row.seller}</p>
                      {row.tone !== "same" && (
                        <span
                          className="mt-1 inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5"
                          style={{ background: meta.bg, color: meta.color, fontSize: "11px", fontWeight: 600 }}
                        >
                          <Icon className="size-3" />
                          {meta.text}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Timeline */}
          <div>
            <h3 className="mb-3 text-sm font-semibold" style={{ color: "var(--navy)" }}>협상 이력 타임라인</h3>
            <ol className="flex flex-col gap-3">
              {timeline.map((item, i) => (
                <li key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <span
                      className="flex size-6 shrink-0 items-center justify-center rounded-full"
                      style={{
                        background: item.who === "buyer" ? "var(--info-soft)" : "var(--success-soft)",
                        color: item.who === "buyer" ? "var(--ocean)" : "var(--success)",
                      }}
                    >
                      {item.who === "buyer" ? <MessagesSquare className="size-3.5" /> : <Sparkles className="size-3.5" />}
                    </span>
                    {i !== timeline.length - 1 && <div className="mt-1 h-full w-px flex-1 bg-border" />}
                  </div>
                  <div className="min-w-0 pb-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold">{item.label}</span>
                      <span className="whitespace-nowrap text-xs text-muted-foreground">{item.date}</span>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground" style={{ lineHeight: 1.6 }}>{item.note}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2 border-t border-border pt-4 sm:flex-row sm:flex-wrap sm:justify-end">
            <Button variant="ghost" className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ color: "var(--coral)" }} onClick={endNegotiation}>
              <XCircle className="size-4" />
              협상 종료
            </Button>
            <Button variant="outline" className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }} onClick={sendProposal}>
              <Send className="size-4" />
              바이어에게 제안 보내기
            </Button>
            <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: "var(--navy)" }} onClick={requestFinalAgreement}>
              <CheckCircle2 className="size-4" />
              최종 합의 요청
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

export function SellerNegotiatingPage() {
  const { requests } = useRequests();

  const negotiating = useMemo(
    () => requests.filter((r) => NEGOTIATING_STATUSES.includes(r.status)),
    [requests],
  );

  return (
    <div>
      <PageHeader
        title="협상 중인 계약"
        description="바이어의 조항별 수정 요청과 셀러 응답을 비교하고 최종 합의를 진행하세요."
      />

      {negotiating.length === 0 ? (
        <Card className="flex flex-col items-center justify-center gap-3 border-dashed p-10 text-center sm:p-16">
          <MessagesSquare className="size-7" style={{ color: "var(--ocean)" }} />
          <p className="text-muted-foreground">현재 협상 중인 계약이 없습니다.</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {negotiating.map((r) => (
            <RequestCard key={r.id} request={r} />
          ))}
        </div>
      )}
    </div>
  );
}
