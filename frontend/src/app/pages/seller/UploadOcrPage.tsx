import { useState } from "react";
import { ArrowLeft, ArrowRight, UploadCloud, FileText, Loader2, Save, Globe, RefreshCw, Sparkles } from "lucide-react";
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

const STEPS = ["wz.upload", "wz.ocr", "wz.confirm", "wz.risk", "wz.publish"];

// OCR로 추출했다고 가정하는 데모 데이터 (위험 조항이 포함되도록 구성).
const OCR_PREFILL: Partial<ListingDraft> = {
  productName: "2026 오션뷰 루프탑 바비큐 패키지",
  category: "package",
  district: "해운대구",
  start: "2026-06-01",
  end: "2026-09-30",
  quantity: "1일 최대 60명",
  unitPrice: "52000",
  priceUnit: "1인당",
  minQty: "20",
  maxQty: "60",
  cancellation: "이용 3일 전까지 무료 취소",
  noShow: "패키지 요금 전액 청구",
  settlement: "매월 말 마감 후 익익월(60일) 15일 지급",
  liability: "",
  termination: "30일 전 서면 통지로 해지 가능",
  special: "최소 보장 물량 20명 미달 시 위약금 발생",
  headline: "해운대 오션뷰 루프탑에서 즐기는 바비큐 패키지를 단체 물량으로 확보하세요.",
};

export function UploadOcrPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { addListing } = useListings();

  const [step, setStep] = useState(0);
  const [fileName, setFileName] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [draft, setDraft] = useState<ListingDraft>(() => createEmptyDraft("upload"));
  const [applied, setApplied] = useState<Record<string, boolean>>({});

  const patch = (p: Partial<ListingDraft>) => setDraft((d) => ({ ...d, ...p }));

  const runOcr = () => {
    setAnalyzing(true);
    setAnalyzed(false);
    setTimeout(() => {
      setDraft((d) => ({ ...d, ...OCR_PREFILL }));
      setAnalyzing(false);
      setAnalyzed(true);
      toast.success(t("ocr.analyzeDone"));
    }, 1400);
  };

  const applyRisk = (field: keyof ListingDraft, value: string, id: string) => {
    patch({ [field]: value } as Partial<ListingDraft>);
    setApplied((a) => ({ ...a, [id]: true }));
  };

  const goNext = () => {
    if (step === 0 && !fileName) {
      toast.error(t("wz.needFile"));
      return;
    }
    if (step === 1) {
      if (!analyzed) {
        runOcr();
        return;
      }
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const publish = (asDraft: boolean) => {
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
    const risks = analyzeDraft(draft).length;
    addListing(draftToListing(draft, asDraft ? "draft" : "public", risks));
    toast.success(t(asDraft ? "pub.draftSaved" : "pub.published"));
    navigate("/seller/listings");
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
                onChange={(e) => setFileName(e.target.files?.[0]?.name ?? "계약서_2026.pdf")}
              />
              <span className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md px-4 py-2 text-white" style={{ background: "var(--navy)", fontSize: "14px" }}>
                <UploadCloud className="size-4" />
                {t("ocr.choose")}
              </span>
            </label>
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
                <Button variant="outline" size="sm" className="gap-1.5 whitespace-nowrap" onClick={runOcr}>
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
                <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--ocean)" }} onClick={runOcr}>
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
            <RiskReviewStep draft={draft} applied={applied} onApply={applyRisk} />
          </div>
        )}

        {/* Step 4: 공개 설정 */}
        {step === 4 && (
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
          <Button className="w-full gap-1.5 whitespace-nowrap sm:w-auto" style={{ background: "var(--navy)" }} onClick={goNext} disabled={analyzing}>
            {t("wz.next")}
            <ArrowRight className="size-4" />
          </Button>
        ) : (
          <div className="grid w-full grid-cols-1 gap-2 sm:flex sm:w-auto sm:flex-wrap">
            <Button variant="outline" className="gap-1.5 whitespace-nowrap" onClick={() => publish(true)}>
              <Save className="size-4" />
              {t("pub.saveDraft")}
            </Button>
            <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => publish(false)}>
              <Globe className="size-4" />
              {t("pub.publish")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
