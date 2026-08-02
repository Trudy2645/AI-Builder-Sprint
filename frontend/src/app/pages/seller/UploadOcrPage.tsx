import { useState } from "react";
import { ArrowLeft, ArrowRight, UploadCloud, FileText, Loader2, Save, Globe, RefreshCw, Sparkles } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { WizardStepper } from "../../components/listings/WizardStepper";
import { ProductFields, SupplyFields, TermsFields } from "../../components/listings/ListingFormFields";
import { AIReviewStep } from "../../components/listings/RiskReviewStep";
import { PublishSettingsStep } from "../../components/listings/PublishSettingsStep";
import { useApp } from "../../context/AppContext";
import { useListings, createEmptyDraft, type ListingDraft } from "../../store/ListingsContext";
import { friendlyApiError } from "../../lib/api";
import {
  createSellerListing,
  generateSellerContract,
  publishSellerListing,
  reviewSellerContract,
  saveSellerListingTerms,
  updateSellerPresentation,
  uploadAndProcessDocument,
  type ListingTerms,
  type ReviewFinding,
} from "../../lib/sellerAi";

const STEPS = ["wz.upload", "wz.ocr", "wz.confirm", "wz.risk", "wz.publish"];

export function UploadOcrPage() {
  const { t, organizationId } = useApp();
  const navigate = useNavigate();
  const { refreshListings } = useListings();

  const [step, setStep] = useState(0);
  const [fileName, setFileName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [draft, setDraft] = useState<ListingDraft>(() => createEmptyDraft("upload"));
  const [listingId, setListingId] = useState<string | null>(null);
  const [currentVersionNo, setCurrentVersionNo] = useState(1);
  const [aiFindings, setAiFindings] = useState<ReviewFinding[]>([]);
  const [preparingReview, setPreparingReview] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const patch = (p: Partial<ListingDraft>) => setDraft((d) => ({ ...d, ...p }));

  const runOcr = async () => {
    if (!file) {
      toast.error(t("wz.needFile"));
      return;
    }
    setAnalyzing(true);
    setAnalyzed(false);
    try {
      if (!organizationId) throw new Error("Seller organization is missing from the session.");
      let targetListingId = listingId;
      if (!targetListingId) {
        const created = await createSellerListing(organizationId, {
          creation_method: "upload",
          title: draft.productName,
          category: draft.category || "tour",
          district: draft.district,
          language: "ko-KR",
        });
        targetListingId = created.listing_id;
        setListingId(targetListingId);
        setCurrentVersionNo(created.version_no);
      }
      const result = await uploadAndProcessDocument(organizationId, targetListingId, file);
      const terms = result.listing_candidate?.terms ?? {};
      setDraft((current) => ({
          ...current,
          productName: current.productName,
          category: current.category,
          district: current.district,
          start: String(terms.service_start_date ?? ""),
          end: String(terms.service_end_date ?? ""),
          unitPrice: terms.base_price_amount_minor == null ? "" : String(terms.base_price_amount_minor),
          priceUnit: terms.price_unit === "room" || terms.price_unit === "room_night"
            ? "객실당"
            : terms.price_unit === "seat"
              ? "1좌석당"
              : terms.price_unit === "vehicle"
                ? "차량 1대·1일"
                : "1인당",
          cancellation: String(terms.cancellation_policy ?? ""),
          noShow: String(terms.no_show_policy ?? ""),
          settlement: String(terms.settlement_policy ?? ""),
          liability: String(terms.liability_policy ?? ""),
      }));
      if (result.confirmation_required.length > 0) {
        toast.info(`${result.confirmation_required.length}개 항목은 셀러 확인이 필요합니다.`);
      }
      setAnalyzed(true);
      toast.success(t("ocr.analyzeDone"));
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setAnalyzing(false);
    }
  };

  const positiveInt = (value: string) => {
    const parsed = Number.parseInt(value, 10);
    return parsed > 0 ? parsed : null;
  };

  const termsPayload = (): ListingTerms => {
    const isRoom = draft.priceUnit === "객실당" || draft.priceUnit === "1동당";
    const isSeat = draft.priceUnit === "1좌석당";
    const isVehicle = draft.category === "vehicle_rental" || draft.priceUnit.includes("차량");
    const priceUnit = isRoom ? "room" : isSeat ? "seat" : isVehicle ? "vehicle" : "person";
    const quantityUnit = isRoom ? "room" : isSeat ? "seat" : isVehicle ? "vehicle" : "person";
    return {
      service_start_date: draft.start || null,
      service_end_date: draft.end || null,
      supply_quantity: positiveInt(draft.maxQty),
      supply_quantity_description: draft.quantity || null,
      quantity_unit: quantityUnit,
      minimum_quantity: positiveInt(draft.minQty),
      maximum_quantity: positiveInt(draft.maxQty),
      base_price_amount_minor: positiveInt(draft.unitPrice),
      currency: "KRW",
      price_unit: priceUnit,
      cancellation_policy: draft.cancellation || null,
      no_show_policy: draft.noShow || null,
      settlement_policy: draft.settlement || null,
      liability_policy: draft.liability || null,
      termination_policy: draft.termination || null,
      special_terms: draft.special || null,
    };
  };

  const prepareReview = async () => {
    const required = [draft.productName, draft.category, draft.district, draft.start, draft.end, draft.quantity, draft.unitPrice, draft.cancellation, draft.noShow, draft.settlement];
    if (required.some((value) => !String(value).trim())) {
      toast.error("위험 검토 전 추출된 필수 조건을 모두 확인하고 빈 항목을 입력해주세요.");
      return false;
    }
    if (!organizationId || !listingId) {
      toast.error("업로드된 계약서 정보가 없습니다. 다시 업로드해주세요.");
      return false;
    }
    setPreparingReview(true);
    try {
      const saved = await saveSellerListingTerms(organizationId, listingId, currentVersionNo, termsPayload());
      setCurrentVersionNo(saved.current_version.version_no);
      const generated = await generateSellerContract(organizationId, listingId, saved.current_version.version_no);
      setCurrentVersionNo(generated.version_no);
      const review = await reviewSellerContract(organizationId, listingId, generated.listing_version_id);
      setAiFindings(review.findings);
      return true;
    } catch (error) {
      toast.error(friendlyApiError(error));
      return false;
    } finally {
      setPreparingReview(false);
    }
  };

  const goNext = async () => {
    if (step === 0 && !fileName) {
      toast.error(t("wz.needFile"));
      return;
    }
    if (step === 0 && (!draft.productName.trim() || !draft.category || !draft.district)) {
      toast.error("업로드 전 계약명, 상품 유형, 지역을 입력해주세요.");
      return;
    }
    if (step === 1) {
      if (!analyzed) {
        void runOcr();
        return;
      }
    }
    if (step === 2 && !(await prepareReview())) return;
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
      toast.error("공개 전 계약명, 유형, 지역, 기간, 가격, 수량, 취소·노쇼·정산 조건을 모두 확인해주세요.");
      return;
    }
    setPublishing(true);
    try {
      if (!organizationId || !listingId) throw new Error("Listing is not ready.");
      await updateSellerPresentation(organizationId, listingId, draft.headline);
      if (!asDraft) await publishSellerListing(organizationId, listingId);
      await refreshListings();
      toast.success(t(asDraft ? "pub.draftSaved" : "pub.published"));
      navigate("/seller/listings");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setPublishing(false);
    }
  };

  return (
    <div className="mx-auto max-w-[960px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate("/seller/listings/new")}>
        <ArrowLeft className="size-4" />
        {t("create.title")}
      </Button>

      <PageHeader title={t("ocr.title")} />

      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <WizardStepper steps={STEPS} current={step} />
      </div>

      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        {/* Step 0: 파일 업로드 */}
        {step === 0 && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="flex size-16 items-center justify-center rounded-2xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
              <UploadCloud className="size-8" />
            </div>
            <div>
              <h3 style={{ color: "var(--navy)" }}>{t("ocr.dropTitle")}</h3>
              <p className="mt-1 text-muted-foreground" style={{ fontSize: "14px" }}>{t("ocr.dropDesc")}</p>
            </div>
            {fileName && (
              <div className="flex items-center gap-2 rounded-lg border border-border px-4 py-2" style={{ fontSize: "14px" }}>
                <FileText className="size-4" style={{ color: "var(--ocean)" }} />
                {fileName}
              </div>
            )}
            <label htmlFor="ocr-file">
              <input
                id="ocr-file"
                type="file"
                className="hidden"
                accept=".pdf,.docx,.jpg,.jpeg,.png"
                onChange={(e) => {
                  const selected = e.target.files?.[0] ?? null;
                  setFile(selected);
                  setFileName(selected?.name ?? "");
                  setAnalyzed(false);
                }}
              />
              <span className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md px-4 py-2 text-white" style={{ background: "var(--navy)", fontSize: "14px" }}>
                <UploadCloud className="size-4" />
                {t("ocr.choose")}
              </span>
            </label>
            <div className="mt-4 w-full max-w-[680px] text-left">
              <ProductFields draft={draft} onChange={patch} />
            </div>
          </div>
        )}

        {/* Step 1: OCR 분석 */}
        {step === 1 && (
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            {analyzing ? (
              <>
                <Loader2 className="size-10 animate-spin" style={{ color: "var(--ocean)" }} />
                <p style={{ color: "var(--navy)", fontWeight: 600 }}>{t("ocr.analyzing")}</p>
              </>
            ) : analyzed ? (
              <>
                <div className="flex size-14 items-center justify-center rounded-2xl" style={{ background: "var(--success-soft)", color: "var(--success)" }}>
                  <FileText className="size-7" />
                </div>
                <p style={{ color: "var(--success)", fontWeight: 600 }}>{t("ocr.analyzeDone")}</p>
                <Button variant="outline" size="sm" className="gap-1.5 whitespace-nowrap" onClick={() => void runOcr()}>
                  <RefreshCw className="size-4" />
                  {t("ocr.reanalyze")}
                </Button>
              </>
            ) : (
              <>
                <div className="flex size-14 items-center justify-center rounded-2xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
                  <FileText className="size-7" />
                </div>
                <p className="text-muted-foreground" style={{ fontSize: "14px" }}>{fileName}</p>
                <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--ocean)" }} onClick={() => void runOcr()}>
                  <Sparkles className="size-4" />
                  {t("wz.ocr")}
                </Button>
              </>
            )}
          </div>
        )}

        {/* Step 2: 정보 확인 */}
        {step === 2 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("ocr.confirmTitle")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("ocr.confirmDesc")}</p>
            <div className="flex flex-col gap-6">
              <ProductFields draft={draft} onChange={patch} />
              <SupplyFields draft={draft} onChange={patch} />
              <TermsFields draft={draft} onChange={patch} />
            </div>
          </div>
        )}

        {/* Step 3: 위험 검토 */}
        {step === 3 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("risk.title")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("risk.desc")}</p>
            <AIReviewStep findings={aiFindings} />
          </div>
        )}

        {/* Step 4: 공개 설정 */}
        {step === 4 && (
          <div>
            <h3 style={{ color: "var(--navy)" }}>{t("pub.title")}</h3>
            <p className="mt-1 mb-5 text-muted-foreground" style={{ fontSize: "14px" }}>{t("pub.desc")}</p>
            <PublishSettingsStep draft={draft} riskCount={aiFindings.length} onChange={patch} />
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
          <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: "var(--navy)" }} onClick={() => void goNext()} disabled={analyzing || preparingReview}>
            {preparingReview && <Loader2 className="size-4 animate-spin" />}
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
