import { useState } from "react";
import { ArrowLeft, ArrowRight, Loader2, Sparkles, Save, Globe, FileText } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { WizardStepper } from "../../components/listings/WizardStepper";
import { ProductFields, SupplyFields, TermsFields } from "../../components/listings/ListingFormFields";
import { AIReviewStep, RiskReviewStep, analyzeDraft } from "../../components/listings/RiskReviewStep";
import { PublishSettingsStep } from "../../components/listings/PublishSettingsStep";
import { useApp } from "../../context/AppContext";
import { useListings, createEmptyDraft, draftToListing, type ListingDraft } from "../../store/ListingsContext";
import { formatKRW } from "../../data/contracts";
import { friendlyApiError } from "../../lib/api";
import {
  createSellerListing,
  generateSellerContract,
  reviewSellerContract,
  saveSellerListingTerms,
  updateSellerPresentation,
  publishSellerListing,
  type ContractGeneration,
  type ListingTerms,
  type ReviewFinding,
} from "../../lib/sellerAi";

const STEPS = ["wz.product", "wz.supply", "wz.terms", "wz.generate", "wz.risk", "wz.publish"];

export function WriteContractPage() {
  const { t, isDemoSession, organizationId } = useApp();
  const navigate = useNavigate();
  const { addListing, refreshListings } = useListings();

  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<ListingDraft>(() => createEmptyDraft("write"));
  const [applied, setApplied] = useState<Record<string, boolean>>({});
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [listingId, setListingId] = useState<string | null>(null);
  const [currentVersionNo, setCurrentVersionNo] = useState(1);
  const [generation, setGeneration] = useState<ContractGeneration | null>(null);
  const [aiFindings, setAiFindings] = useState<ReviewFinding[]>([]);
  const [publishing, setPublishing] = useState(false);

  const patch = (p: Partial<ListingDraft>) => setDraft((d) => ({ ...d, ...p }));

  const applyRisk = (field: keyof ListingDraft, value: string, id: string) => {
    patch({ [field]: value } as Partial<ListingDraft>);
    setApplied((a) => ({ ...a, [id]: true }));
  };

  const positiveInt = (value: string) => {
    const parsed = Number.parseInt(value, 10);
    return parsed > 0 ? parsed : null;
  };

  const unitValues = (): Pick<ListingTerms, "price_unit" | "quantity_unit"> => {
    if (draft.priceUnit === "객실당" || draft.priceUnit === "1동당") return { price_unit: "room", quantity_unit: "room" };
    if (draft.priceUnit === "1좌석당") return { price_unit: "seat", quantity_unit: "seat" };
    if (draft.category === "vehicle_rental") return { price_unit: "vehicle", quantity_unit: "vehicle" };
    return { price_unit: "person", quantity_unit: "person" };
  };

  const termsPayload = (): ListingTerms => ({
    service_start_date: draft.start || null,
    service_end_date: draft.end || null,
    supply_quantity: positiveInt(draft.maxQty),
    supply_quantity_description: draft.quantity || null,
    ...unitValues(),
    minimum_quantity: positiveInt(draft.minQty),
    maximum_quantity: positiveInt(draft.maxQty),
    base_price_amount_minor: positiveInt(draft.unitPrice),
    currency: "KRW",
    cancellation_policy: draft.cancellation || null,
    no_show_policy: draft.noShow || null,
    settlement_policy: draft.settlement || null,
    liability_policy: draft.liability || null,
    termination_policy: draft.termination || null,
    special_terms: draft.special || null,
  });

  const requiredGenerationFields = () => [
    draft.productName, draft.category, draft.district, draft.start, draft.end,
    draft.quantity, draft.unitPrice, draft.cancellation, draft.noShow, draft.settlement,
  ];

  const runGenerate = async () => {
    if (requiredGenerationFields().some((value) => !String(value).trim())) {
      toast.error("AI 생성 전 계약명, 유형, 지역, 기간, 가격, 수량, 취소·노쇼·정산 조건을 모두 입력해주세요.");
      return;
    }
    setGenerating(true);
    setGenerated(false);
    try {
      if (isDemoSession) {
        await new Promise((resolve) => window.setTimeout(resolve, 1400));
        setGenerated(true);
        toast.success(t("gen.done"));
        return;
      }
      if (!organizationId) throw new Error("Seller organization is missing from the session.");
      let targetListingId = listingId;
      let versionNo = currentVersionNo;
      if (!targetListingId) {
        const created = await createSellerListing(organizationId, {
          creation_method: "manual",
          title: draft.productName,
          category: draft.category || "accommodation",
          district: draft.district,
          language: "ko-KR",
        });
        targetListingId = created.listing_id;
        setListingId(targetListingId);
        versionNo = created.version_no;
        setCurrentVersionNo(versionNo);
      }
      const saved = await saveSellerListingTerms(organizationId, targetListingId, versionNo, termsPayload());
      setCurrentVersionNo(saved.current_version.version_no);
      const result = await generateSellerContract(organizationId, targetListingId, saved.current_version.version_no);
      setCurrentVersionNo(result.version_no);
      setGeneration(result);
      setGenerated(true);
      toast.success(t("gen.done"));
      try {
        const review = await reviewSellerContract(organizationId, targetListingId, result.listing_version_id);
        setAiFindings(review.findings);
      } catch (error) {
        toast.error(`계약서는 생성됐지만 위험 분석을 불러오지 못했습니다. ${friendlyApiError(error)}`);
      }
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setGenerating(false);
    }
  };

  const goNext = () => {
    if (step === 3 && !generated) {
      runGenerate();
      return;
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const publish = async (asDraft: boolean) => {
    const requiredForPublish = [
      draft.productName,
      draft.category,
      draft.district,
      draft.start,
      draft.end,
      draft.quantity,
      draft.unitPrice,
      draft.cancellation,
      draft.noShow,
      draft.settlement,
    ];
    if (!asDraft && requiredForPublish.some((value) => !String(value).trim())) {
      toast.error("공개 전 계약명, 유형, 지역, 기간, 가격, 수량, 취소·노쇼·정산 조건을 모두 입력해주세요.");
      return;
    }
    setPublishing(true);
    try {
      if (isDemoSession) {
        const risks = analyzeDraft(draft).length;
        addListing(draftToListing(draft, asDraft ? "draft" : "public", risks));
      } else {
        if (!organizationId || !listingId || !generation) {
          toast.error("먼저 AI 계약서를 생성해주세요.");
          return;
        }
        await updateSellerPresentation(organizationId, listingId, draft.headline);
        if (!asDraft) await publishSellerListing(organizationId, listingId);
        await refreshListings();
      }
      toast.success(t(asDraft ? "pub.draftSaved" : "pub.published"));
      navigate("/seller/listings");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setPublishing(false);
    }
  };

  const price = parseInt(draft.unitPrice, 10) || 0;

  return (
    <div className="mx-auto max-w-[960px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate("/seller/listings/new")}>
        <ArrowLeft className="size-4" />
        {t("create.title")}
      </Button>

      <PageHeader title={t("write.title")} />

      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <WizardStepper steps={STEPS} current={step} />
      </div>

      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        {step === 0 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("wz.product")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("write.productDesc")}</p>
            <ProductFields draft={draft} onChange={patch} />
          </div>
        )}

        {step === 1 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("wz.supply")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("write.supplyDesc")}</p>
            <SupplyFields draft={draft} onChange={patch} />
          </div>
        )}

        {step === 2 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("wz.terms")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("write.termsDesc")}</p>
            <TermsFields draft={draft} onChange={patch} />
          </div>
        )}

        {/* Step 3: AI 계약서 생성 */}
        {step === 3 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("gen.title")}</h3>
            {generating ? (
              <div className="flex flex-col items-center gap-4 py-12 text-center">
                <Loader2 className="size-10 animate-spin" style={{ color: "var(--ocean)" }} />
                <p style={{ color: "var(--navy)", fontWeight: 600 }}>{t("gen.running")}</p>
              </div>
            ) : generated ? (
              <div className="mt-4">
                <div className="mb-3 flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--teal)", fontWeight: 600 }}>
                  <FileText className="size-4" />
                  {t("gen.preview")}
                </div>
                <div className="rounded-lg border border-border p-5" style={{ background: "var(--surface)", fontSize: "14px", lineHeight: 1.9 }}>
                  <p style={{ fontWeight: 700, color: "var(--navy)" }}>{draft.productName || t("lf.productName")}</p>
                  {generation ? generation.clauses.map((clause) => (
                    <div key={clause.id} className="mt-2">
                      <p style={{ fontWeight: 600 }}>제{clause.clause_order}조 ({clause.title})</p>
                      <p>{clause.body}</p>
                    </div>
                  )) : (
                    <>
                      <p className="mt-2">제1조 (계약의 목적) 본 계약은 셀러가 바이어에게 {draft.productName || "관광 상품"}을 공급하는 조건을 정함을 목적으로 한다.</p>
                      <p>제2조 (공급 기간·수량) 공급 기간은 {draft.start || "○○"} ~ {draft.end || "○○"}로 하며, {draft.quantity || "협의된 수량"}을 공급한다.</p>
                      <p>제3조 (공급 단가) 공급 단가는 {draft.priceUnit} {formatKRW(price)}으로 한다.</p>
                    </>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4 py-12 text-center">
                <div className="flex size-14 items-center justify-center rounded-2xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
                  <Sparkles className="size-7" />
                </div>
                <p className="text-muted-foreground" style={{ fontSize: "14px" }}>{t("gen.title")}</p>
                <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--ocean)" }} onClick={runGenerate}>
                  <Sparkles className="size-4" />
                  {t("gen.title")}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Step 4: 위험 검토 */}
        {step === 4 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("risk.title")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("risk.desc")}</p>
            {isDemoSession ? (
              <RiskReviewStep draft={draft} applied={applied} onApply={applyRisk} />
            ) : (
              <AIReviewStep findings={aiFindings} />
            )}
          </div>
        )}

        {/* Step 5: 공개 설정 */}
        {step === 5 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("pub.title")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("pub.desc")}</p>
            <PublishSettingsStep draft={draft} onChange={patch} />
          </div>
        )}
      </div>

      {/* Footer nav */}
      <div className="mt-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <Button
          variant="ghost"
          className="w-full gap-1.5 whitespace-nowrap sm:w-auto"
          onClick={() => (step === 0 ? navigate("/seller/listings/new") : setStep((s) => s - 1))}
        >
          <ArrowLeft className="size-4" />
          {step === 0 ? t("wz.cancel") : t("wz.prev")}
        </Button>

        {step < STEPS.length - 1 ? (
          <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: "var(--navy)" }} onClick={goNext} disabled={generating}>
            {t("wz.next")}
            <ArrowRight className="size-4" />
          </Button>
        ) : (
          <div className="grid w-full grid-cols-1 gap-2 sm:flex sm:w-auto sm:flex-wrap">
            <Button variant="outline" className="gap-1.5 whitespace-nowrap" onClick={() => void publish(true)} disabled={publishing}>
              <Save className="size-4" />
              {t("pub.saveDraft")}
            </Button>
            <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => void publish(false)} disabled={publishing}>
              <Globe className="size-4" />
              {t("pub.publish")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
