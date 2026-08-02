import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, Eye, GitBranch, Send, X } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { ReviewClauseCard, emptyDecision, type Decision, type ReceivedRevision } from "../../components/received/ReviewClauseCard";
import { useApp } from "../../context/AppContext";
import { decideRevisionRequest, friendlyApiError, getContractDetail, getRevisionRequest, patchRevisionItem, type ContractDetail, type RevisionRequestResponse } from "../../lib/api";

export function RevisionReviewPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const [revision, setRevision] = useState<RevisionRequestResponse | null>(null);
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    let active = true;
    void getRevisionRequest(id)
      .then(async (nextRevision) => {
        const nextContract = await getContractDetail(nextRevision.contract_id);
        if (!active) return;
        setRevision(nextRevision);
        setContract(nextContract);
        setDecisions(Object.fromEntries(nextRevision.items.map((item) => [item.id, emptyDecision()])));
      })
      .catch((error) => toast.error(friendlyApiError(error)))
      .finally(() => setLoading(false));
    return () => { active = false; };
  }, [id]);

  const rows = useMemo<ReceivedRevision[]>(() => {
    if (!revision || !contract) return [];
    return revision.items.map((item) => {
      const clause = contract.current_version.clauses.find((candidate) => candidate.id === item.clause_id);
      return {
        id: item.id,
        clauseNo: clause ? `제${clause.clause_order}조` : `항목 ${item.item_order}`,
        clauseTitle: clause?.title ?? "추가 조항",
        original: clause?.body ?? "기존 조항 없음",
        requested: item.requested_text ?? "삭제 요청",
        reason: item.reason,
        aiImpact: "서버의 현재 계약 버전과 수정 요청을 기준으로 검토해 주세요.",
        aiRecommend: item.requested_text ?? "",
      };
    });
  }, [revision, contract]);

  if (loading) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">수정 요청을 불러오는 중입니다…</div>;
  if (!revision || !contract) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">수정 요청을 찾을 수 없습니다.</div>;

  const decidedCount = Object.values(decisions).filter((decision) => decision.kind).length;
  const allDecided = rows.length > 0 && decidedCount === rows.length;
  const counts = Object.values(decisions).reduce((result, decision) => { if (decision.kind) result[decision.kind] += 1; return result; }, { accept: 0, reject: 0, counter: 0 });
  const send = async () => {
    if (!allDecided) { toast.error(t("rvw.needAll")); return; }
    if (Object.values(decisions).some((decision) => decision.kind === "counter" && !decision.counterText.trim())) { toast.error(t("rvw.needCounterText")); return; }
    setSubmitting(true);
    try {
      let latest = revision;
      for (const item of revision.items) {
        const decision = decisions[item.id];
        latest = await patchRevisionItem(revision.id, item.id, {
          decision: decision.kind === "accept" ? "accepted" : decision.kind === "reject" ? "rejected" : "countered",
          seller_reason: [decision.counterReason, decision.message].filter(Boolean).join("\n") || undefined,
          counter_text: decision.kind === "counter" ? decision.counterText : undefined,
        });
      }
      await decideRevisionRequest(latest.id, { seller_message: "셀러가 수정 요청 항목을 검토했습니다." });
      toast.success(t("rvw.sent"));
      navigate("/seller/negotiating");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  return <div className="mx-auto max-w-[960px]"><Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate("/seller/received")}><ArrowLeft className="size-4" />{t("recv.title")}</Button><PageHeader title={t("rvw.title")} description={`${t("rvw.from")}: ${contract.parties.find((party) => party.role === "buyer")?.name ?? "바이어"} · ${contract.listing_title}`} /><div className="mb-6 rounded-xl border border-border bg-card p-5"><ContractStepper current={3} /></div><div className="mb-4 flex items-center gap-3 rounded-xl border border-border bg-card p-4"><span className="font-semibold">진행률 {decidedCount}/{rows.length}</span><div className="h-2 flex-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-[var(--ocean)]" style={{ width: `${rows.length ? decidedCount / rows.length * 100 : 0}%` }} /></div><Badge className="border-transparent bg-[var(--success-soft)] text-[var(--success)]"><Check className="mr-1 size-3" />{counts.accept}</Badge><Badge className="border-transparent bg-[var(--coral-soft)] text-[var(--coral)]"><X className="mr-1 size-3" />{counts.reject}</Badge><Badge className="border-transparent bg-[var(--info-soft)] text-[var(--ocean)]"><GitBranch className="mr-1 size-3" />{counts.counter}</Badge></div><div className="flex flex-col gap-4">{rows.map((row, index) => <ReviewClauseCard key={row.id} index={index} revision={row} decision={decisions[row.id]} onChange={(decision) => setDecisions((previous) => ({ ...previous, [row.id]: decision }))} />)}</div><div className="mt-6 flex justify-end gap-2 rounded-xl border border-border bg-card p-4"><Button variant="outline" onClick={() => setPreviewOpen(!previewOpen)}><Eye className="mr-1 size-4" />미리보기</Button><Button disabled={submitting || !allDecided} style={{ background: "var(--navy)" }} onClick={() => void send()}><Send className="mr-1 size-4" />{t("rvw.send")}</Button></div>{previewOpen && <div className="mt-4 rounded-xl border border-[var(--ocean)] bg-[var(--info-soft)] p-5"><h2 className="font-semibold">셀러 응답 미리보기</h2>{rows.map((row) => <div key={row.id} className="mt-3 rounded-lg bg-card p-3 text-sm"><div className="font-semibold">{row.clauseNo} · {row.clauseTitle}</div><p className="mt-1">{decisions[row.id]?.kind === "counter" ? decisions[row.id].counterText : decisions[row.id]?.kind === "accept" ? row.requested : row.original}</p></div>)}</div>}</div>;
}
