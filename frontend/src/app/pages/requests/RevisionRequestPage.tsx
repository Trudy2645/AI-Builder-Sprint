import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Plus, Save, Send } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { RevisionCard, type RevisionDraft } from "../../components/requests/RevisionCard";
import { useApp } from "../../context/AppContext";
import { createContractRequest, createRevisionRequest, friendlyApiError, getPublicListing, sendRevisionRequest, type PublicListingDetail } from "../../lib/api";
import type { Contract } from "../../lib/catalog";

let draftSequence = 0;
function newDraft(clauseNo = ""): RevisionDraft {
  draftSequence += 1;
  return { id: `revision-${draftSequence}`, clauseNo, changeType: "edit", requested: "", reason: "", attachment: "" };
}

function toContract(listing: PublicListingDetail): Contract {
  return {
    id: listing.id,
    seller: listing.seller.name,
    title: listing.title,
    category: listing.category,
    district: listing.district,
    start: listing.availability.start_date ?? "",
    end: listing.availability.end_date ?? "",
    unitPrice: listing.base_price?.amount_minor ?? 0,
    priceUnit: listing.base_price?.unit ?? "기준 단가",
    quantityLabel: listing.supply_quantity_description ?? "",
    capacity: listing.maximum_people ?? Number.MAX_SAFE_INTEGER,
    available: listing.contract_available,
    popularity: 0,
    createdOrder: 0,
    recommendScore: 0,
    image: listing.hero_image_url ?? "",
    aiSummary: listing.ai_summary?.split(/\r?\n/) ?? [],
    details: {
      period: `${listing.availability.start_date ?? ""} ~ ${listing.availability.end_date ?? ""}`,
      supplyQuantity: listing.supply_quantity_description ?? "",
      unitPrice: `${listing.base_price?.amount_minor ?? 0}`,
      cancellation: listing.cancellation_policy ?? "",
      noShow: listing.no_show_policy ?? "",
      settlement: listing.settlement_policy ?? "",
    },
    clauses: listing.clauses.map((clause) => ({ no: String(clause.id), title: clause.title, text: clause.body })),
  };
}

export function RevisionRequestPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const [listing, setListing] = useState<PublicListingDetail | null>(null);
  const [drafts, setDrafts] = useState<RevisionDraft[]>([newDraft()]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    void getPublicListing(id)
      .then((next) => {
        setListing(next);
        setDrafts([newDraft(next.clauses[0] ? String(next.clauses[0].id) : "")]);
      })
      .catch((error) => toast.error(friendlyApiError(error)))
      .finally(() => setLoading(false));
  }, [id]);

  const contract = useMemo(() => listing ? toContract(listing) : null, [listing]);
  if (loading) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">공고를 불러오는 중입니다…</div>;
  if (!listing || !contract) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">공고를 찾을 수 없습니다.</div>;

  const update = (draft: RevisionDraft) => setDrafts((previous) => previous.map((item) => item.id === draft.id ? draft : item));
  const remove = (draftId: string) => setDrafts((previous) => previous.length > 1 ? previous.filter((item) => item.id !== draftId) : previous);

  const createServerRevision = async (send: boolean) => {
    const valid = drafts.filter((draft) => draft.clauseNo && draft.reason.trim() && (draft.changeType === "delete" || draft.requested.trim()));
    if (!valid.length) {
      toast.error(t("rev.needOne"));
      return;
    }
    if (!listing.availability.start_date || !listing.availability.end_date) {
      toast.error("공고 이용 기간이 없어 요청할 수 없습니다.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await createContractRequest(listing.id, {
        people: listing.minimum_people ?? 1,
        quantity: listing.minimum_quantity ?? 1,
        quantity_unit: listing.quantity_unit ?? "unit",
        nights: Math.max(1, Math.ceil((new Date(listing.availability.end_date).getTime() - new Date(listing.availability.start_date).getTime()) / 86_400_000)),
        start_date: listing.availability.start_date,
        end_date: listing.availability.end_date,
        currency: listing.base_price?.currency ?? "KRW",
        initial_request_kind: "revision",
        request_message: valid.map((item) => item.reason).join("\n"),
      });
      const revision = await createRevisionRequest(created.contract_id, {
        base_version_no: created.version_no,
        message: valid.map((item) => item.reason).join("\n"),
        items: valid.map((item) => {
          const clause = listing.clauses.find((candidate) => String(candidate.id) === item.clauseNo);
          return {
            request_type: item.changeType === "delete" ? "delete" : item.changeType === "add" ? "add" : "modify",
            clause_id: item.changeType === "add" ? undefined : clause?.id,
            reason: item.reason,
            requested_text: item.changeType === "delete" ? undefined : item.requested,
            document_ids: [],
          };
        }),
      });
      if (send) await sendRevisionRequest(revision.revision_request_id);
      toast.success(send ? "수정 요청을 보냈습니다." : "수정 요청 초안을 저장했습니다.");
      navigate("/buyer/sent");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  return <div className="mx-auto max-w-[760px]"><Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate(`/buyer/explore/${listing.id}/document`)}><ArrowLeft className="size-4" />{t("req.exit")}</Button><PageHeader title={t("rev.title")} description={t("rev.intro")} /><div className="mb-6 rounded-xl border border-border bg-card p-5"><ContractStepper current={3} /></div><div className="mb-4 rounded-xl border border-border bg-card p-4"><div className="text-xs text-muted-foreground">{t("asis.contract")}</div><div className="font-semibold" style={{ color: "var(--navy)" }}>{listing.seller.name} · {listing.title}</div></div><div className="flex flex-col gap-4">{drafts.map((draft, index) => <RevisionCard key={draft.id} index={index} contract={contract} draft={draft} onChange={update} onRemove={() => remove(draft.id)} />)}</div><Button variant="outline" className="mt-4 w-full gap-1.5 border-dashed" onClick={() => setDrafts((previous) => [...previous, newDraft()])}><Plus className="size-4" />{t("rev.addCard")}</Button><div className="mt-6 flex justify-end gap-2 rounded-xl border border-border bg-card p-4"><Button variant="outline" disabled={submitting} onClick={() => void createServerRevision(false)}><Save className="mr-1 size-4" />{t("req.saveDraft")}</Button><Button disabled={submitting} style={{ background: "var(--navy)" }} onClick={() => void createServerRevision(true)}><Send className="mr-1 size-4" />{t("rev.send")}</Button></div></div>;
}
