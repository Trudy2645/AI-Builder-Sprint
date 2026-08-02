import { useEffect, useState } from "react";
import { ArrowLeft, Save, Send, Plus } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { RevisionCard, type RevisionDraft } from "../../components/requests/RevisionCard";
import { useApp } from "../../context/AppContext";
import type { Contract } from "../../data/contracts";
import { friendlyApiError, getPublicContractPreview, getPublicListingDetail } from "../../lib/api";
import { useRequests } from "../../store/RequestsContext";

let counter = 0;
const newDraft = (): RevisionDraft => ({
  id: `d-${Date.now()}-${counter++}`,
  clauseNo: "",
  changeType: "edit",
  requested: "",
  reason: "",
  attachment: "",
});

const changeTypeLabel: Record<string, string> = {
  edit: "opt.ct.edit",
  delete: "opt.ct.delete",
  add: "opt.ct.add",
};

export function RevisionRequestPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const { addRequest } = useRequests();
  const [contract, setContract] = useState<Contract>();
  const [loadError, setLoadError] = useState("");

  const [drafts, setDrafts] = useState<RevisionDraft[]>(() => [newDraft()]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    Promise.all([getPublicListingDetail(id), getPublicContractPreview(id)])
      .then(([listing, preview]) => {
        if (!active) return;
        const findings = new Map(
          preview.findings.filter((finding) => finding.clause_id).map((finding) => [finding.clause_id, finding]),
        );
        const clauses = preview.clauses.map((clause, index) => {
          const finding = findings.get(clause.id);
          return {
            no: clause.clause_key || `제${index + 1}조`,
            title: clause.title,
            text: clause.body,
            risk: finding
              ? { reason: finding.explanation, recommendation: finding.suggested_text || finding.explanation }
              : undefined,
          };
        });
        setContract({
          id: listing.id,
          seller: listing.seller.name,
          title: listing.title,
          category: listing.category,
          district: listing.district,
          start: listing.availability.start_date || "",
          end: listing.availability.end_date || "",
          unitPrice: listing.base_price?.amount_minor || 0,
          priceUnit: listing.base_price?.unit || "",
          quantityLabel: listing.supply_quantity_description || "",
          capacity: listing.maximum_people || listing.maximum_quantity || 0,
          available: listing.contract_available,
          popularity: 0,
          createdOrder: 0,
          recommendScore: 0,
          image: listing.hero_image_url || "",
          details: {
            period: `${listing.availability.start_date || ""} ~ ${listing.availability.end_date || ""}`,
            supplyQuantity: listing.supply_quantity_description || "",
            unitPrice: listing.base_price ? `${listing.base_price.amount_minor} ${listing.base_price.currency}` : "",
            cancellation: listing.cancellation_policy || "",
            noShow: listing.no_show_policy || "",
            settlement: listing.settlement_policy || "",
          },
          clauses,
          attentionRequiredCount: preview.findings.length,
        });
        const firstRisk = clauses.find((clause) => clause.risk);
        if (firstRisk) {
          setDrafts((current) => current.map((draft, index) => index === 0 && !draft.clauseNo ? { ...draft, clauseNo: firstRisk.no } : draft));
        }
      })
      .catch((reason: unknown) => active && setLoadError(friendlyApiError(reason)));
    return () => {
      active = false;
    };
  }, [id]);

  if (!contract) {
    return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{loadError || "계약서와 AI 분석 결과를 불러오는 중입니다."}</div>;
  }

  const update = (d: RevisionDraft) => setDrafts((prev) => prev.map((x) => (x.id === d.id ? d : x)));
  const remove = (rid: string) => setDrafts((prev) => (prev.length > 1 ? prev.filter((x) => x.id !== rid) : prev));
  const add = () => setDrafts((prev) => [...prev, newDraft()]);

  const send = () => {
    const valid = drafts.filter((d) => d.clauseNo && d.requested.trim());
    if (valid.length === 0) {
      toast.error(t("rev.needOne"));
      return;
    }
    addRequest({
      contractId: contract.id,
      seller: contract.seller,
      title: contract.title,
      type: "revision",
      status: "reviewing",
      revisions: valid.map((d) => {
        const clause = contract.clauses.find((c) => c.no === d.clauseNo)!;
        return {
          id: d.id,
          clauseNo: d.clauseNo,
          clauseTitle: clause.title,
          original: clause.text,
          changeType: t(changeTypeLabel[d.changeType] ?? "opt.ct.edit"),
          requested: d.requested,
          reason: d.reason,
          attachment: d.attachment || undefined,
        };
      }),
    });
    toast.success(t("rev.sent"));
    navigate("/buyer/sent");
  };

  const saveDraft = () => {
    addRequest({
      contractId: contract.id,
      seller: contract.seller,
      title: contract.title,
      type: "revision",
      status: "draft",
      currentVersion: "v1",
      revisions: drafts
        .filter((d) => d.clauseNo)
        .map((d) => {
          const clause = contract.clauses.find((c) => c.no === d.clauseNo)!;
          return {
            id: d.id,
            clauseNo: d.clauseNo,
            clauseTitle: clause.title,
            original: clause.text,
            changeType: t(changeTypeLabel[d.changeType] ?? "opt.ct.edit"),
            requested: d.requested,
            reason: d.reason,
            attachment: d.attachment || undefined,
          };
        }),
    });
    toast.success(t("req.draftSaved"));
    navigate("/buyer/sent");
  };

  return (
    <div className="mx-auto max-w-[760px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate(`/buyer/explore/${contract.id}/document`)}>
        <ArrowLeft className="size-4" />
        {t("req.exit")}
      </Button>

      <PageHeader title={t("rev.title")} description={t("rev.intro")} />

      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={3} />
      </div>

      <div className="mb-4 rounded-xl border border-border bg-card p-4">
        <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "13px" }}>{t("asis.contract")}</div>
        <div style={{ color: "var(--navy)", fontWeight: 600 }}>{contract.seller} · {contract.title}</div>
      </div>

      <div className="flex flex-col gap-4">
        {drafts.map((d, i) => (
          <RevisionCard key={d.id} index={i} contract={contract} draft={d} onChange={update} onRemove={() => remove(d.id)} />
        ))}
      </div>

      <Button variant="outline" className="mt-4 w-full gap-1.5 whitespace-nowrap border-dashed" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }} onClick={add}>
        <Plus className="size-4" />
        {t("rev.addCard")}
      </Button>

      {/* Actions */}
      <div className="mt-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end [&_button]:w-full sm:[&_button]:w-auto">
        <Button variant="ghost" className="gap-1.5 whitespace-nowrap" onClick={() => navigate(`/buyer/explore/${contract.id}/document`)}>
          <ArrowLeft className="size-4" />
          {t("req.exit")}
        </Button>
        <Button variant="outline" className="gap-1.5 whitespace-nowrap" onClick={saveDraft}>
          <Save className="size-4" />
          {t("req.saveDraft")}
        </Button>
        <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={send}>
          <Send className="size-4" />
          {t("rev.send")}
        </Button>
      </div>
    </div>
  );
}
