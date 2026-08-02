import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, X, GitBranch, Eye, Save, Send, XCircle } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ContractStepper } from "../../components/contract/ContractStepper";
import {
  ReviewClauseCard,
  emptyDecision,
  type Decision,
} from "../../components/received/ReviewClauseCard";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { useApp } from "../../context/AppContext";
import { getReceivedRequest, type ReceivedRequest } from "../../data/receivedRequests";
import { useRequests } from "../../store/RequestsContext";
import { decideRevisionItem, decideRevisionRequest, friendlyApiError, getRevisionRequest } from "../../lib/api";

export function RevisionReviewPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const { updateRequestStatus } = useRequests();
  const [serverRequest, setServerRequest] = useState<ReceivedRequest | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const demoRequest = getReceivedRequest(id);
  useEffect(() => {
    if (demoRequest || !id) return;
    void getRevisionRequest(id).then((item) => setServerRequest({
      id: item.id, buyer: "바이어", contractId: item.contract_id, contractTitle: "계약 수정 요청",
      status: "negotiating", createdAt: new Date().toISOString().slice(0, 10).replaceAll("-", "."),
      period: "계약 조건에서 확인", estimatedAmount: "계약 조건에서 확인", currentVersion: `v${item.base_version_no}`,
      revisions: item.items.map((revision) => ({ id: revision.id, clauseNo: revision.clause_id ?? "조항", clauseTitle: revision.request_type, original: "현재 계약 조항", requested: revision.requested_text ?? "조항 추가/삭제 요청", reason: revision.reason, aiImpact: "", aiRecommend: "" })),
    })).catch((error: unknown) => setLoadError(friendlyApiError(error)));
  }, [demoRequest, id]);
  const request = demoRequest ?? serverRequest;

  const [decisions, setDecisions] = useState<Record<string, Decision>>(() => {
    const init: Record<string, Decision> = {};
    request?.revisions.forEach((r) => (init[r.id] = emptyDecision()));
    return init;
  });
  useEffect(() => {
    if (!request) return;
    setDecisions((previous) => {
      const next: Record<string, Decision> = {};
      for (const revision of request.revisions) next[revision.id] = previous[revision.id] ?? emptyDecision();
      return next;
    });
  }, [request]);
  const [previewOpen, setPreviewOpen] = useState(false);

  const total = request?.revisions.length ?? 0;
  const decidedCount = useMemo(
    () => Object.values(decisions).filter((d) => d.kind).length,
    [decisions],
  );
  const allDecided = total > 0 && decidedCount === total;

  const counts = useMemo(() => {
    const c = { accept: 0, reject: 0, counter: 0 };
    for (const d of Object.values(decisions)) {
      if (d.kind) c[d.kind] += 1;
    }
    return c;
  }, [decisions]);

  if (!request) {
    return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{loadError ?? t("recv.empty")}</div>;
  }

  const update = (rid: string, d: Decision) => setDecisions((prev) => ({ ...prev, [rid]: d }));

  const openPreview = () => {
    // 대안 제시는 제안 문구가 있어야 미리보기/전송 가능
    const missingCounter = request.revisions.some((r) => {
      const d = decisions[r.id];
      return d?.kind === "counter" && !d.counterText.trim();
    });
    if (missingCounter) {
      toast.error(t("rvw.needCounterText"));
      return;
    }
    setPreviewOpen(true);
  };

  const send = async () => {
    if (!allDecided) {
      toast.error(t("rvw.needAll"));
      return;
    }
    const missingCounter = request.revisions.some((r) => {
      const d = decisions[r.id];
      return d?.kind === "counter" && !d.counterText.trim();
    });
    if (missingCounter) {
      toast.error(t("rvw.needCounterText"));
      return;
    }
    setPreviewOpen(false);
    if (id && !demoRequest) {
      try {
        for (const item of request.revisions) {
          const decision = decisions[item.id];
          if (decision?.kind) await decideRevisionItem(id, item.id, { decision: decision.kind === "accept" ? "accepted" : decision.kind === "reject" ? "rejected" : "countered", seller_reason: decision.kind === "reject" ? "기존 조건 유지" : undefined, counter_text: decision.kind === "counter" ? decision.counterText : undefined });
        }
        await decideRevisionRequest(id, "셀러가 요청 조항을 검토했습니다.");
        toast.success(t("rvw.sent"));
        navigate("/seller/received");
        return;
      } catch (error) { toast.error(friendlyApiError(error)); return; }
    }
    // 조항별 검토 결과(수락/거절/대안)를 셀러 응답 문구와 함께 요청 상태에 반영해
    // 협상 중 화면에서 바이어 원안 vs 셀러 제안안을 그대로 이어 볼 수 있게 한다.
    const revisedRevisions = request.revisions.map((r) => {
      const d = decisions[r.id] ?? emptyDecision();
      return {
        id: r.id,
        clauseNo: r.clauseNo,
        clauseTitle: r.clauseTitle,
        original: r.original,
        changeType: "문구 수정",
        requested: r.requested,
        reason: r.reason,
        sellerDecision: d.kind,
        sellerResponse: responseText(r.id, r.original, r.requested),
      };
    });
    updateRequestStatus("req-hotel-main", "negotiating", {
      currentVersion: "v3",
      latestResponse: "셀러가 요청 조항을 검토하고 응답안을 보냈습니다.",
      revisions: revisedRevisions,
    });
    toast.success(t("rvw.sent"));
    navigate("/seller/negotiating");
  };

  // 셀러 응답 문구: 수락=바이어 요청, 대안=셀러 제안, 거절=기존 유지
  const responseText = (rid: string, original: string, requested: string) => {
    const d = decisions[rid] ?? emptyDecision();
    if (d.kind === "accept") return requested;
    if (d.kind === "counter") return d.counterText || t("rvw.pending");
    if (d.kind === "reject") return original;
    return t("rvw.pending");
  };

  return (
    <div className="mx-auto max-w-[960px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate("/seller/received")}>
        <ArrowLeft className="size-4" />
        {t("recv.title")}
      </Button>

      <PageHeader title={t("rvw.title")} description={`${t("rvw.from")}: ${request.buyer} · ${request.contractTitle}`} />

      {/* Process stepper — step 3 협상 */}
      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={3} />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-4">
        <div><div className="text-xs text-muted-foreground">요청일</div><div className="mt-1 font-semibold">{request.createdAt}</div></div>
        <div><div className="text-xs text-muted-foreground">계약 기간</div><div className="mt-1 font-semibold">{request.period}</div></div>
        <div><div className="text-xs text-muted-foreground">예상 계약 금액</div><div className="mt-1 font-semibold">{request.estimatedAmount}</div></div>
        <div><div className="text-xs text-muted-foreground">현재 버전</div><div className="mt-1 font-semibold" style={{ color: "var(--ocean)" }}>{request.currentVersion}</div></div>
      </div>

      {/* Progress */}
      <div className="mb-4 flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-3">
        <span className="whitespace-nowrap" style={{ fontWeight: 600, color: "var(--navy)" }}>
          {t("rvw.progress")} {decidedCount}{t("rvw.progressOf").replace("{total}", String(total))}
        </span>
        <div className="h-2 flex-1 overflow-hidden rounded-full" style={{ background: "var(--muted)" }}>
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${(decidedCount / total) * 100}%`, background: allDecided ? "var(--success)" : "var(--ocean)" }}
          />
        </div>
        <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ fontSize: "13px" }}>
          <Badge className="gap-1 border-transparent" style={{ background: "var(--success-soft)", color: "var(--success)" }}><Check className="size-3" />{counts.accept}</Badge>
          <Badge className="gap-1 border-transparent" style={{ background: "var(--coral-soft)", color: "var(--coral)" }}><X className="size-3" />{counts.reject}</Badge>
          <Badge className="gap-1 border-transparent" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}><GitBranch className="size-3" />{counts.counter}</Badge>
        </div>
      </div>

      {/* Clause cards */}
      <div className="flex flex-col gap-4">
        {request.revisions.map((r, i) => (
          <ReviewClauseCard key={r.id} index={i} revision={r} decision={decisions[r.id]} onChange={(d) => update(r.id, d)} />
        ))}
      </div>

      {/* Bottom actions */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card p-4">
        <Button
          variant="ghost"
          className="gap-1.5 whitespace-nowrap"
          style={{ color: "var(--coral)" }}
          onClick={() => {
            if (!window.confirm("이 계약 협상을 종료하시겠습니까? 종료 후에는 같은 요청에서 협상을 계속할 수 없습니다.")) return;
            updateRequestStatus("req-hotel-main", "closed", {
              latestResponse: "셀러가 협상을 종료했습니다.",
            });
            toast.success(t("rvw.ended"));
            navigate("/seller/received");
          }}
        >
          <XCircle className="size-4" />
          {t("rvw.endNegotiation")}
        </Button>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="gap-1.5 whitespace-nowrap" onClick={() => toast.success(t("rvw.draftSaved"))}>
            <Save className="size-4" />
            {t("rvw.saveDraft")}
          </Button>
          <Button variant="outline" className="gap-1.5 whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }} onClick={openPreview}>
            <Eye className="size-4" />
            {t("rvw.preview")}
          </Button>
          <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} disabled={!allDecided} onClick={send}>
            <Send className="size-4" />
            {t("rvw.send")}
          </Button>
        </div>
      </div>

      {/* Preview dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-h-[90vh] w-[calc(100vw-2rem)] max-w-[860px] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t("rvw.previewTitle")}</DialogTitle>
            <DialogDescription>{t("rvw.previewDesc")}</DialogDescription>
          </DialogHeader>

          {/* Summary counts */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-lg p-3 text-center" style={{ background: "var(--success-soft)" }}>
              <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--success)" }}>{counts.accept}</div>
              <div className="whitespace-nowrap" style={{ fontSize: "12px", color: "var(--success)" }}>{t("rvw.sumAccepted")}</div>
            </div>
            <div className="rounded-lg p-3 text-center" style={{ background: "var(--coral-soft)" }}>
              <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--coral)" }}>{counts.reject}</div>
              <div className="whitespace-nowrap" style={{ fontSize: "12px", color: "var(--coral)" }}>{t("rvw.sumRejected")}</div>
            </div>
            <div className="rounded-lg p-3 text-center" style={{ background: "var(--info-soft)" }}>
              <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--ocean)" }}>{counts.counter}</div>
              <div className="whitespace-nowrap" style={{ fontSize: "12px", color: "var(--ocean)" }}>{t("rvw.sumCountered")}</div>
            </div>
          </div>

          {/* Comparison table */}
          <div className="max-h-[50vh] overflow-auto rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="whitespace-nowrap">{t("rvw.cmp.clause")}</TableHead>
                  <TableHead className="whitespace-nowrap">{t("rvw.cmp.original")}</TableHead>
                  <TableHead className="whitespace-nowrap">{t("rvw.cmp.requested")}</TableHead>
                  <TableHead className="whitespace-nowrap">{t("rvw.cmp.response")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {request.revisions.map((r) => {
                  const d = decisions[r.id] ?? emptyDecision();
                  const kindColor =
                    d.kind === "accept" ? "var(--success)" : d.kind === "reject" ? "var(--coral)" : "var(--ocean)";
                  const kindLabel =
                    d.kind === "accept" ? t("rvw.accepted") : d.kind === "reject" ? t("rvw.rejected") : d.kind === "counter" ? t("rvw.countered") : t("rvw.pending");
                  return (
                    <TableRow key={r.id}>
                      <TableCell className="align-top whitespace-nowrap">
                        <div style={{ fontWeight: 600, color: "var(--ocean)" }}>{r.clauseNo}</div>
                        <Badge className="mt-1 whitespace-nowrap border-transparent" style={{ background: `color-mix(in srgb, ${kindColor} 12%, #fff)`, color: kindColor }}>{kindLabel}</Badge>
                      </TableCell>
                      <TableCell className="align-top" style={{ fontSize: "12px", lineHeight: 1.6, minWidth: 180 }}>{r.original}</TableCell>
                      <TableCell className="align-top" style={{ fontSize: "12px", lineHeight: 1.6, minWidth: 180 }}>{r.requested}</TableCell>
                      <TableCell className="align-top" style={{ fontSize: "12px", lineHeight: 1.6, minWidth: 180, color: kindColor, fontWeight: 500 }}>
                        {responseText(r.id, r.original, r.requested)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <DialogFooter>
            <Button variant="outline" className="whitespace-nowrap" onClick={() => setPreviewOpen(false)}>{t("rvw.cmp.close")}</Button>
            <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} disabled={!allDecided} onClick={send}>
              <Send className="size-4" />
              {t("rvw.send")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
