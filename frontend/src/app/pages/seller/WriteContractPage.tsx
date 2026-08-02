import { useState } from "react";
import { ArrowLeft, ArrowRight, Loader2, Sparkles, Save, Globe, FileText } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { WizardStepper } from "../../components/listings/WizardStepper";
import { ProductFields, SupplyFields, TermsFields } from "../../components/listings/ListingFormFields";
import { RiskReviewStep, analyzeDraft } from "../../components/listings/RiskReviewStep";
import { PublishSettingsStep } from "../../components/listings/PublishSettingsStep";
import { useApp } from "../../context/AppContext";
import { useListings, createEmptyDraft, draftToListing, type ListingDraft } from "../../store/ListingsContext";
import { formatKRW } from "../../lib/catalog";
import { friendlyApiError, hasApiSession, saveSellerListing } from "../../lib/api";

const STEPS = ["wz.product", "wz.supply", "wz.terms", "wz.generate", "wz.risk", "wz.publish"];

export function WriteContractPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { addListing } = useListings();

  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<ListingDraft>(() => createEmptyDraft("write"));
  const [applied, setApplied] = useState<Record<string, boolean>>({});
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const patch = (p: Partial<ListingDraft>) => setDraft((d) => ({ ...d, ...p }));

  const applyRisk = (field: keyof ListingDraft, value: string, id: string) => {
    patch({ [field]: value } as Partial<ListingDraft>);
    setApplied((a) => ({ ...a, [id]: true }));
  };

  const runGenerate = () => {
    setGenerating(true);
    setGenerated(false);
    setTimeout(() => {
      setGenerating(false);
      setGenerated(true);
      toast.success(t("gen.done"));
    }, 1400);
  };

  const isBlank = (value: unknown) => !String(value ?? "").trim();
  const validateCurrentStep = () => {
    if (step === 0) {
      if ([draft.productName, draft.category, draft.district].some(isBlank)) {
        toast.error("다음 단계로 가기 전에 계약명, 상품 유형, 지역을 입력해주세요.");
        return false;
      }
    }
    if (step === 1) {
      if ([draft.availabilityStart, draft.availabilityEnd, draft.quantity, draft.priceUnit, draft.unitPrice].some(isBlank)) {
        toast.error("다음 단계로 가기 전에 공급 기간, 공급 수량, 단가 기준, 단가를 입력해주세요.");
        return false;
      }
      if ((parseInt(draft.unitPrice, 10) || 0) <= 0) {
        toast.error("단가는 0원보다 큰 금액으로 입력해주세요.");
        return false;
      }
    }
    if (step === 2) {
      if ([draft.cancellation, draft.noShow, draft.settlement, draft.liability, draft.termination].some(isBlank)) {
        toast.error("다음 단계로 가기 전에 취소, 노쇼, 정산, 책임, 계약 해지 조건을 입력해주세요.");
        return false;
      }
    }
    return true;
  };

  const goNext = () => {
    if (!validateCurrentStep()) return;
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
      draft.quantity,
      draft.unitPrice,
      draft.cancellation,
      draft.noShow,
      draft.settlement,
    ];
    if (!asDraft && requiredForPublish.some((value) => !String(value).trim())) {
      toast.error("공개 전 계약명, 유형, 지역, 가격, 수량, 취소·노쇼·정산 조건을 모두 입력해주세요.");
      return;
    }
    const risks = analyzeDraft(draft).length;
    const serverDraft = {
      ...draft,
      category: (draft.category || "accommodation") as Exclude<ListingDraft["category"], "">,
      district: draft.district || "부산",
    };
    setPublishing(true);
    try {
      if (!hasApiSession()) throw new Error("API 로그인 정보가 없습니다. 다시 로그인해 주세요.");
      await saveSellerListing(serverDraft, !asDraft && draft.available);
      addListing(draftToListing(serverDraft, asDraft ? "draft" : "public", risks));
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
                  <p className="mt-2">제1조 (계약의 목적) 본 계약은 셀러가 바이어에게 {draft.productName || "관광 상품"}을 공급하는 조건을 정함을 목적으로 한다.</p>
                  <p>제2조 (이용 기간·수량) 이용 기간은 바이어가 계약 요청 시 선택하며, {draft.quantity || "협의된 수량"}을 공급한다.</p>
                  <p>제3조 (공급 단가) 공급 단가는 {draft.priceUnit} {formatKRW(price)}으로 한다.</p>
                  <p>제4조 (취소·환불) {draft.cancellation || "별도 협의"}.</p>
                  <p>제5조 (노쇼) {draft.noShow || "별도 협의"}.</p>
                  <p>제6조 (정산) {draft.settlement || "별도 협의"}.</p>
                  <p>제7조 (책임) {draft.liability || "관계 법령에 따른다"}.</p>
                  <p>제8조 (계약 해지) {draft.termination || "상호 협의로 해지할 수 있다"}.</p>
                  {draft.special && <p>제9조 (특약) {draft.special}.</p>}
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
            <RiskReviewStep draft={draft} applied={applied} onApply={applyRisk} />
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
