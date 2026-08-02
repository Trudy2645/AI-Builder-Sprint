import { useEffect, useState } from "react";
import { ArrowLeft, Save, Send, Plus } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { RevisionCard, type RevisionDraft } from "../../components/requests/RevisionCard";
import { useApp } from "../../context/AppContext";
import { getContract, type Contract } from "../../data/contracts";
import { createPublicContractRequest, createRevisionRequest, friendlyApiError, getPublicListingAsContract, sendRevisionRequest } from "../../lib/api";
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
  const [searchParams] = useSearchParams();
  const initialFrom = searchParams.get("from") ?? "";
  const initialTo = searchParams.get("to") ?? "";
  const demoContract = getContract(id);
  const [serverContract, setServerContract] = useState<Contract | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  useEffect(() => {
    if (demoContract || !id) return;
    void getPublicListingAsContract(id).then(setServerContract).catch((error: unknown) => setLoadError(friendlyApiError(error)));
  }, [demoContract, id]);
  const contract = demoContract ?? serverContract;
  const { addRequest } = useRequests();
  const [startDate, setStartDate] = useState(initialFrom || (contract?.start !== "미정" ? contract?.start ?? "" : ""));
  const [endDate, setEndDate] = useState(initialTo || (contract?.end !== "미정" ? contract?.end ?? "" : ""));

  useEffect(() => {
    if (!contract) return;
    if (!initialFrom && contract.start !== "미정") setStartDate(contract.start);
    if (!initialTo && contract.end !== "미정") setEndDate(contract.end);
  }, [contract, initialFrom, initialTo]);

  // Pre-seed with one card targeting the first risky clause if any.
  const [drafts, setDrafts] = useState<RevisionDraft[]>(() => {
    const first = newDraft();
    const risky = contract?.clauses.find((c) => c.risk);
    if (risky) first.clauseNo = risky.no;
    return [first];
  });

  if (!contract) {
    return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{loadError ?? "계약 조건을 불러오는 중입니다…"}</div>;
  }

  const update = (d: RevisionDraft) => setDrafts((prev) => prev.map((x) => (x.id === d.id ? d : x)));
  const remove = (rid: string) => setDrafts((prev) => (prev.length > 1 ? prev.filter((x) => x.id !== rid) : prev));
  const add = () => setDrafts((prev) => [...prev, newDraft()]);
  const quantityUnit = contract?.quantityUnit ?? (contract?.category === "accommodation" ? "room" : contract?.category === "vehicle_rental" ? "vehicle" : "person");

  const send = async () => {
    const valid = drafts.filter((d) => d.clauseNo && d.requested.trim());
    if (valid.length === 0) {
      toast.error(t("rev.needOne"));
      return;
    }
    if (!startDate || !endDate || endDate <= startDate) { toast.error("이용 시작일과 종료일을 올바르게 입력해 주세요."); return; }
    const nights = Math.round((Date.parse(`${endDate}T00:00:00`) - Date.parse(`${startDate}T00:00:00`)) / 86_400_000);
    if (nights <= 0) { toast.error("이용 기간은 하루 이상이어야 합니다."); return; }
    try {
      const created = await createPublicContractRequest(contract.id, {
        people: 1, quantity: 1, quantity_unit: quantityUnit, nights,
        start_date: startDate, end_date: endDate, currency: "KRW", initial_request_kind: "revision",
        request_message: valid.map((d) => `${d.clauseNo}: ${d.requested}${d.reason ? ` (사유: ${d.reason})` : ""}`).join("\n"),
      });
      const revision = await createRevisionRequest(created.contract_id, {
        base_version_no: created.version_no,
        message: valid.map((d) => d.reason).filter(Boolean).join("\n") || "바이어가 계약 조항 수정을 요청했습니다.",
        items: valid.map((d) => {
          const clause = contract.clauses.find((c) => c.no === d.clauseNo);
          return {
            request_type: d.changeType === "delete" ? "delete" : d.changeType === "add" ? "add" : "modify",
            clause_id: d.changeType === "add" ? undefined : clause?.id,
            reason: d.reason.trim() || "계약 조건 수정을 요청합니다.",
            requested_text: d.changeType === "delete" ? undefined : d.requested.trim(),
          };
        }),
      });
      await sendRevisionRequest(revision.revision_request_id);
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
      navigate(`/buyer/contracts/${created.contract_id}/status`);
    } catch (error) { toast.error(friendlyApiError(error)); }
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
      <div className="mb-4 grid gap-4 rounded-xl border border-border bg-card p-4 sm:grid-cols-2"><div><label className="text-sm">이용 시작일 *</label><Input type="date" min={contract.start !== "미정" ? contract.start : undefined} max={contract.end !== "미정" ? contract.end : undefined} value={startDate} onChange={(e) => setStartDate(e.target.value)} /><span className="text-xs text-muted-foreground">공고 가능 기간 안에서 선택하세요.</span></div><div><label className="text-sm">이용 종료일 *</label><Input type="date" min={contract.start !== "미정" ? contract.start : undefined} max={contract.end !== "미정" ? contract.end : undefined} value={endDate} onChange={(e) => setEndDate(e.target.value)} /><span className="text-xs text-muted-foreground">공고 종료일과 같을 필요는 없습니다.</span></div></div>

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
