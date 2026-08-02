import { useMemo, useState } from "react";
import {
  FileCheck2,
  Download,
  FileText,
  History,
  Building2,
  CalendarRange,
  Hash,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../../components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { Separator } from "../../components/ui/separator";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useRequests, type SentRequest, type RequestStatus } from "../../store/RequestsContext";
import { useNegotiation } from "../../store/NegotiationContext";
import { getContract, formatKRW } from "../../data/contracts";

const BUYER_NAME = "GlobalTrip Japan";

type Tab = "all" | "signing" | "completed" | "closed";
const TABS: { key: Tab; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "signing", label: "서명 대기" },
  { key: "completed", label: "체결 완료" },
  { key: "closed", label: "종료" },
];
const CONTRACT_STATUSES: RequestStatus[] = ["signing", "completed", "closed"];

function hashId(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 9000;
  return String(1000 + h);
}

function contractNoFor(request: SentRequest, mainContractNo?: string): string {
  if (request.id === "req-summer-main" && mainContractNo) return mainContractNo;
  return `BL-2026-${hashId(request.id)}`;
}

function periodFor(request: SentRequest): string {
  return getContract(request.contractId)?.details.period ?? "-";
}

const statusMeta: Record<Tab, { label: string; color: string; bg: string }> = {
  all: { label: "전체", color: "var(--muted-foreground)", bg: "var(--muted)" },
  signing: { label: "서명 대기", color: "var(--warning)", bg: "var(--warning-soft)" },
  completed: { label: "체결 완료", color: "var(--success)", bg: "var(--success-soft)" },
  closed: { label: "종료", color: "var(--muted-foreground)", bg: "var(--muted)" },
};

function StatusPill({ status }: { status: RequestStatus }) {
  const key: Tab = status === "signing" ? "signing" : status === "completed" ? "completed" : "closed";
  const meta = statusMeta[key];
  return (
    <Badge className="border-transparent whitespace-nowrap" style={{ background: meta.bg, color: meta.color }}>
      {meta.label}
    </Badge>
  );
}

export function SellerContractsPage() {
  const { requests } = useRequests();
  const { bothSigned, contractNo, signedAt } = useNegotiation();
  const [tab, setTab] = useState<Tab>("all");
  const [docTarget, setDocTarget] = useState<SentRequest | null>(null);
  const [auditTarget, setAuditTarget] = useState<SentRequest | null>(null);

  // 최종 전자서명이 완료되면 CompletionPage에서 상태를 "completed"로 갱신하지만,
  // 화면 전환 타이밍 안전망으로 여기서도 한 번 더 반영한다.
  const contracts = useMemo(() => {
    let list = requests.filter((r) => CONTRACT_STATUSES.includes(r.status));
    const main = requests.find((r) => r.id === "req-summer-main");
    if (bothSigned && main && main.status !== "completed" && !list.some((r) => r.id === "req-summer-main")) {
      list = [{ ...main, status: "completed" as const }, ...list];
    }
    return list;
  }, [requests, bothSigned]);

  const counts = useMemo(() => {
    const c: Record<Tab, number> = { all: contracts.length, signing: 0, completed: 0, closed: 0 };
    for (const r of contracts) {
      if (r.status === "signing") c.signing += 1;
      else if (r.status === "completed") c.completed += 1;
      else if (r.status === "closed") c.closed += 1;
    }
    return c;
  }, [contracts]);

  const rows = tab === "all" ? contracts : contracts.filter((r) => r.status === tab);

  const downloadContract = (request: SentRequest) => {
    const contract = getContract(request.contractId);
    const no = contractNoFor(request, contractNo);
    const content = [
      "BUSAN LINK 전자계약서 (데모)",
      "",
      `계약명: ${request.title}`,
      `계약번호: ${no}`,
      `바이어: ${BUYER_NAME}`,
      `셀러: 해운대 오션스테이`,
      `계약기간: ${periodFor(request)}`,
      `최종버전: ${request.currentVersion ?? "v4"}`,
      `상태: ${statusMeta[request.status === "signing" ? "signing" : request.status === "completed" ? "completed" : "closed"].label}`,
      "",
      "핵심 조건",
      contract ? `- ${contract.details.supplyQuantity}` : "- 공급 조건 정보 없음",
      contract ? `- 단가: ${contract.priceUnit} ${formatKRW(contract.unitPrice)}` : "",
      contract ? `- 취소 규정: ${contract.details.cancellation}` : "",
      contract ? `- 정산 조건: ${contract.details.settlement}` : "",
      "",
      request.id === "req-summer-main" && signedAt
        ? `전자서명 완료 시각: ${signedAt}`
        : "전자서명 완료 (데모 데이터)",
    ]
      .filter(Boolean)
      .join("\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${no}-계약서.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("계약서 파일을 다운로드했습니다. (데모 텍스트 파일)");
  };

  return (
    <div>
      <PageHeader title="체결 계약" description="서명 대기·체결 완료·종료된 계약을 상태별로 확인하고 계약서를 관리하세요." />

      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card className="p-4 sm:p-5">
          <div className="text-xs text-muted-foreground">서명 대기</div>
          <div className="mt-2 text-2xl font-bold" style={{ color: "var(--warning)" }}>{counts.signing}건</div>
        </Card>
        <Card className="p-4 sm:p-5">
          <div className="text-xs text-muted-foreground">체결 완료</div>
          <div className="mt-2 text-2xl font-bold" style={{ color: "var(--success)" }}>{counts.completed}건</div>
        </Card>
        <Card className="p-4 sm:p-5">
          <div className="text-xs text-muted-foreground">종료</div>
          <div className="mt-2 text-2xl font-bold" style={{ color: "var(--muted-foreground)" }}>{counts.closed}건</div>
        </Card>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList className="mb-4 flex-wrap">
          {TABS.map((t) => (
            <TabsTrigger key={t.key} value={t.key} className="gap-1.5 whitespace-nowrap">
              {t.label}
              <span
                className="rounded-full px-1.5"
                style={{ fontSize: "11px", background: "var(--muted)", color: "var(--muted-foreground)" }}
              >
                {counts[t.key]}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value={tab}>
          {rows.length === 0 ? (
            <Card className="flex flex-col items-center justify-center gap-3 border-dashed p-10 text-center sm:p-16">
              <FileCheck2 className="size-7" style={{ color: "var(--ocean)" }} />
              <p className="text-muted-foreground">해당 상태의 계약이 없습니다.</p>
            </Card>
          ) : (
            <>
              {/* Mobile cards */}
              <div className="flex flex-col gap-3 lg:hidden">
                {rows.map((r) => (
                  <Card key={r.id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold" style={{ color: "var(--ocean)" }}>{contractNoFor(r, contractNo)}</div>
                        <h3 className="mt-1 line-clamp-2 text-base" style={{ color: "var(--navy)" }}>{r.title}</h3>
                        <p className="mt-1 truncate text-sm text-muted-foreground">{BUYER_NAME}</p>
                      </div>
                      <StatusPill status={r.status} />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 border-y border-border py-3 text-sm">
                      <div><div className="text-xs text-muted-foreground">계약 기간</div><div className="mt-1">{periodFor(r)}</div></div>
                      <div className="text-right"><div className="text-xs text-muted-foreground">최종 수정일</div><div className="mt-1">{r.createdAt}</div></div>
                    </div>
                    {r.status === "completed" && (
                      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                        <Button size="sm" variant="outline" className="gap-1.5 whitespace-nowrap" onClick={() => setDocTarget(r)}>
                          <FileText className="size-4" />계약서 보기
                        </Button>
                        <Button size="sm" variant="outline" className="gap-1.5 whitespace-nowrap" onClick={() => setAuditTarget(r)}>
                          <History className="size-4" />서명 이력
                        </Button>
                        <Button size="sm" className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => downloadContract(r)}>
                          <Download className="size-4" />다운로드
                        </Button>
                      </div>
                    )}
                  </Card>
                ))}
              </div>

              {/* Desktop table */}
              <Card className="hidden overflow-x-auto lg:block">
                <div className="grid min-w-[920px] grid-cols-[1fr_1.8fr_1.1fr_1.2fr_.9fr_.9fr_1.6fr] gap-4 border-b bg-muted/40 px-5 py-3 text-xs font-semibold text-muted-foreground">
                  <div>계약번호</div><div>계약명</div><div>바이어</div><div>계약 기간</div><div>상태</div><div>최종 수정일</div><div>작업</div>
                </div>
                {rows.map((r) => (
                  <div key={r.id} className="grid min-w-[920px] grid-cols-[1fr_1.8fr_1.1fr_1.2fr_.9fr_.9fr_1.6fr] items-center gap-4 border-b px-5 py-4 last:border-b-0">
                    <div className="truncate font-mono text-xs" style={{ color: "var(--ocean)" }}>{contractNoFor(r, contractNo)}</div>
                    <div className="truncate font-semibold">{r.title}</div>
                    <div className="truncate text-sm">{BUYER_NAME}</div>
                    <div className="text-xs text-muted-foreground">{periodFor(r)}</div>
                    <div><StatusPill status={r.status} /></div>
                    <div className="text-xs text-muted-foreground">{r.createdAt}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {r.status === "completed" ? (
                        <>
                          <Button size="sm" variant="outline" className="gap-1 whitespace-nowrap" onClick={() => setDocTarget(r)}>
                            <FileText className="size-3.5" />계약서
                          </Button>
                          <Button size="sm" variant="outline" className="gap-1 whitespace-nowrap" onClick={() => setAuditTarget(r)}>
                            <History className="size-3.5" />서명이력
                          </Button>
                          <Button size="sm" className="gap-1 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => downloadContract(r)}>
                            <Download className="size-3.5" />다운로드
                          </Button>
                        </>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </div>
                  </div>
                ))}
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>

      {/* 계약서 보기 */}
      <Dialog open={!!docTarget} onOpenChange={(v) => !v && setDocTarget(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>{docTarget?.title}</DialogTitle>
            <DialogDescription>계약서 핵심 조건 (데모 미리보기)</DialogDescription>
          </DialogHeader>
          {docTarget && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Hash className="size-4" style={{ color: "var(--ocean)" }} />
                <span className="font-mono text-sm">{contractNoFor(docTarget, contractNo)}</span>
                <VersionBadge version={docTarget.currentVersion || "v4"} />
              </div>
              <Separator />
              <div className="flex items-center gap-2 text-sm">
                <Building2 className="size-4 shrink-0" style={{ color: "var(--ocean)" }} />
                {BUYER_NAME} · 해운대 오션스테이
              </div>
              <div className="flex items-center gap-2 text-sm">
                <CalendarRange className="size-4 shrink-0" style={{ color: "var(--ocean)" }} />
                {periodFor(docTarget)}
              </div>
              {getContract(docTarget.contractId) && (
                <div className="rounded-lg p-3 text-sm" style={{ background: "var(--surface)" }}>
                  <div className="mb-1 font-semibold" style={{ color: "var(--navy)" }}>주요 조항</div>
                  <ul className="flex flex-col gap-1 text-muted-foreground">
                    <li>· 공급 수량: {getContract(docTarget.contractId)!.details.supplyQuantity}</li>
                    <li>· 단가: {getContract(docTarget.contractId)!.details.unitPrice}</li>
                    <li>· 취소 규정: {getContract(docTarget.contractId)!.details.cancellation}</li>
                    <li>· 정산 조건: {getContract(docTarget.contractId)!.details.settlement}</li>
                  </ul>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDocTarget(null)}>닫기</Button>
            {docTarget && (
              <Button style={{ background: "var(--navy)" }} className="gap-1.5" onClick={() => downloadContract(docTarget)}>
                <Download className="size-4" />다운로드
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 서명 이력 보기 */}
      <Dialog open={!!auditTarget} onOpenChange={(v) => !v && setAuditTarget(null)}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>서명 이력</DialogTitle>
            <DialogDescription>{auditTarget?.title}</DialogDescription>
          </DialogHeader>
          {auditTarget && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between rounded-lg border border-border p-3">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <CheckCircle2 className="size-4" style={{ color: "var(--success)" }} />
                  바이어 서명 완료
                </div>
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  {auditTarget.id === "req-summer-main" && signedAt ? signedAt : `${auditTarget.createdAt} 14:32`}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border p-3">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <CheckCircle2 className="size-4" style={{ color: "var(--success)" }} />
                  셀러 서명 완료
                </div>
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  {auditTarget.id === "req-summer-main" && signedAt ? signedAt : `${auditTarget.createdAt} 15:10`}
                </span>
              </div>
              <div className="flex items-start gap-2 rounded-lg p-3 text-xs text-muted-foreground" style={{ background: "var(--surface)" }}>
                <Clock className="mt-0.5 size-3.5 shrink-0" />
                본 이력은 데모용 목업 데이터이며, 실제 서비스에서는 전자서명 서비스의 감사 추적(audit trail) API 결과를 표시합니다.
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAuditTarget(null)}>닫기</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
