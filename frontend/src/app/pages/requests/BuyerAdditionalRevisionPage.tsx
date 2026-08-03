import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Plus, Send } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { RevisionCard, type RevisionDraft } from "../../components/requests/RevisionCard";
import { useApp } from "../../context/AppContext";
import { createRevisionRequest, friendlyApiError, getContractDetail, sendRevisionRequest, type ContractDetail } from "../../lib/api";
import type { Contract } from "../../lib/catalog";

let draftSequence = 0;

function newDraft(clauseId = ""): RevisionDraft {
  draftSequence += 1;
  return { id: `additional-revision-${draftSequence}`, clauseNo: clauseId, changeType: "edit", requested: "", reason: "", attachment: "" };
}

function toContract(detail: ContractDetail): Contract {
  const seller = detail.parties.find((party) => party.role === "seller")?.name ?? "셀러";
  return {
    id: detail.id,
    seller,
    title: detail.listing_title,
    category: "accommodation",
    district: "",
    start: detail.terms.start_date,
    end: detail.terms.end_date,
    unitPrice: detail.terms.amount_minor ?? 0,
    priceUnit: detail.terms.quantity_unit,
    quantityUnit: detail.terms.quantity_unit,
    quantityLabel: `${detail.terms.quantity} ${detail.terms.quantity_unit}`,
    capacity: Number.MAX_SAFE_INTEGER,
    available: true,
    popularity: 0,
    createdOrder: 0,
    recommendScore: 0,
    image: "",
    aiSummary: [],
    details: {
      period: `${detail.terms.start_date} ~ ${detail.terms.end_date}`,
      supplyQuantity: `${detail.terms.quantity} ${detail.terms.quantity_unit}`,
      unitPrice: `${detail.terms.amount_minor ?? 0}`,
      cancellation: "",
      noShow: "",
      settlement: "",
    },
    clauses: detail.current_version.clauses.map((clause) => ({
      id: clause.id,
      no: String(clause.clause_order),
      title: clause.title,
      text: clause.body,
    })),
  };
}

export function BuyerAdditionalRevisionPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [drafts, setDrafts] = useState<RevisionDraft[]>([newDraft()]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    void getContractDetail(id)
      .then((next) => {
        setDetail(next);
        setDrafts([newDraft(next.current_version.clauses[0]?.id ?? "")]);
      })
      .catch((error) => toast.error(friendlyApiError(error)))
      .finally(() => setLoading(false));
  }, [id]);

  const contract = useMemo(() => detail ? toContract(detail) : null, [detail]);

  const create = async () => {
    if (!detail) return;
    const valid = drafts.filter((draft) => draft.reason.trim() && (
      draft.changeType === "add"
        ? Boolean(draft.requested.trim())
        : Boolean(draft.clauseNo) && (draft.changeType === "delete" || Boolean(draft.requested.trim()))
    ));
    if (!valid.length) {
      toast.error(t("rev.needOne"));
      return;
    }
    setSubmitting(true);
    try {
      const created = await createRevisionRequest(detail.id, {
        base_version_no: detail.current_version.version_no,
        message: "바이어가 셀러 응답을 확인한 뒤 추가 수정을 제안했습니다.",
        items: valid.map((draft) => ({
          request_type: draft.changeType === "add" ? "add" : draft.changeType === "delete" ? "delete" : "modify",
          clause_id: draft.changeType === "add" ? undefined : draft.clauseNo,
          reason: draft.reason.trim(),
          requested_text: draft.changeType === "delete" ? undefined : draft.requested.trim(),
          document_ids: [],
        })),
      });
      await sendRevisionRequest(created.revision_request_id);
      toast.success("추가 수정 요청을 보냈습니다.");
      navigate(`/buyer/sent/revision/${created.revision_request_id}`);
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <PageHeader title="추가 수정 요청을 준비하는 중" description="현재 계약 버전을 불러오고 있습니다." />;
  if (!detail || !contract) return <PageHeader title="계약을 불러올 수 없습니다" description="잠시 후 다시 시도해 주세요." />;

  return (
    <div className="mx-auto max-w-[760px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate(`/buyer/sent/revision/${id}`)}>
        <ArrowLeft className="size-4" />
        수정 요청 상세
      </Button>
      <PageHeader title="추가 수정 요청" description="셀러 응답을 확인한 뒤 조정이 필요한 조건을 다시 제안하세요." />
      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={3} />
      </div>
      <div className="mb-4 rounded-xl border border-border bg-card p-4">
        <div className="text-xs text-muted-foreground">현재 계약</div>
        <div className="font-semibold" style={{ color: "var(--navy)" }}>{detail.listing_title}</div>
        <div className="mt-1 text-sm text-muted-foreground">기준 버전 v{detail.current_version.version_no}</div>
      </div>
      <div className="flex flex-col gap-4">
        {drafts.map((draft, index) => (
          <RevisionCard key={draft.id} index={index} contract={contract} draft={draft} onChange={(next) => setDrafts((items) => items.map((item) => item.id === next.id ? next : item))} onRemove={() => setDrafts((items) => items.length > 1 ? items.filter((item) => item.id !== draft.id) : items)} />
        ))}
      </div>
      <Button variant="outline" className="mt-4 w-full gap-1.5 border-dashed" onClick={() => setDrafts((items) => [...items, newDraft(contract.clauses[0]?.id ?? "")])}>
        <Plus className="size-4" />
        수정 항목 추가
      </Button>
      <div className="mt-6 flex justify-end rounded-xl border border-border bg-card p-4">
        <Button disabled={submitting} style={{ background: "var(--navy)" }} onClick={() => void create()}>
          <Send className="mr-1 size-4" />
          추가 수정 요청 보내기
        </Button>
      </div>
    </div>
  );
}
