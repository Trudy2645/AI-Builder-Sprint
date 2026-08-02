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
import { friendlyApiError, uploadAndProcessSourceContract, type ContractProcessingStage } from "../../lib/api";

const STEPS = ["wz.upload", "wz.ocr", "wz.confirm", "wz.risk", "wz.publish"];

type ListingCandidate = {
  title?: string;
  category?: ListingDraft["category"];
  terms?: Record<string, unknown>;
};

function stringValue(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function candidateToDraft(candidate: ListingCandidate | null): Partial<ListingDraft> {
  const terms = candidate?.terms ?? {};
  const cancellation = stringValue(terms.cancellation_policy);
  const refund = stringValue(terms.refund_policy);
  return {
    productName: candidate?.title ?? "",
    category: candidate?.category ?? "accommodation",
    start: "",
    end: "",
    unitPrice: stringValue(terms.base_price_amount_minor),
    priceUnit: stringValue(terms.price_unit) || "1인당",
    cancellation,
    // Contracts often state cancellation and refund in one combined clause.
    // Do not show the same extracted paragraph twice in the confirmation form.
    noShow: refund && refund !== cancellation ? refund : "",
    liability: stringValue(terms.liability_policy),
    termination: stringValue(terms.termination_policy),
  };
}

export function UploadOcrPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { addListing } = useListings();

  const [step, setStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(false);
  const [draft, setDraft] = useState<ListingDraft>(() => createEmptyDraft("upload"));
  const [applied, setApplied] = useState<Record<string, boolean>>({});
  const [analysisNotes, setAnalysisNotes] = useState<string[]>([]);
  const [extractedValues, setExtractedValues] = useState<Record<string, unknown> | null>(null);
  const [analysisStage, setAnalysisStage] = useState<ContractProcessingStage>("uploading");

  const patch = (p: Partial<ListingDraft>) => setDraft((d) => ({ ...d, ...p }));

  const runOcr = async () => {
    if (!file) return;
    setAnalyzing(true);
    setAnalyzed(false);
    try {
      const result = await uploadAndProcessSourceContract(file, setAnalysisStage);
      setDraft((d) => ({ ...d, ...candidateToDraft(result.listingCandidate) }));
      setAnalysisNotes([...result.confirmationRequired, ...result.validationWarnings]);
      setExtractedValues(result.extraction);
      setAnalyzed(true);
      toast.success(t("ocr.analyzeDone"));
    } catch (error) {
      toast.error(friendlyApiError(error));
      setAnalyzed(false);
    } finally {
      setAnalyzing(false);
    }
  };

  const loadSampleContract = async () => {
    try {
      const response = await fetch("/samples/accommodation_service_agreement_filled_sample_ko.pdf");
      if (!response.ok) throw new Error("예시 계약서를 불러오지 못했습니다.");
      setFile(new File([await response.blob()], "숙박시설_이용_및_제공_계약서.pdf", { type: "application/pdf" }));
      toast.success("숙박 계약서 예시를 불러왔습니다.");
    } catch (error) {
      toast.error(friendlyApiError(error));
    }
  };

  const applyRisk = (field: keyof ListingDraft, value: string, id: string) => {
    patch({ [field]: value } as Partial<ListingDraft>);
    setApplied((a) => ({ ...a, [id]: true }));
  };

  const goNext = () => {
    if (step === 0 && !file) {
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
      toast.error("공개 전 계약명, 유형, 지역, 가격, 수량, 취소·노쇼·정산 조건을 모두 확인해주세요.");
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
            {file && (
              <div className="flex items-center gap-2 rounded-lg border border-border px-4 py-2" style={{ fontSize: "14px" }}>
                <FileText className="size-4" style={{ color: "var(--ocean)" }} />
                {file.name}
              </div>
            )}
            <label htmlFor="ocr-file">
              <input
                id="ocr-file"
                type="file"
                className="hidden"
                accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <span className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md px-4 py-2 text-white" style={{ background: "var(--navy)", fontSize: "14px" }}>
                <UploadCloud className="size-4" />
                {t("ocr.choose")}
              </span>
            </label>
            <Button type="button" variant="outline" size="sm" onClick={loadSampleContract}>
              숙박 계약서 예시 불러오기
            </Button>
          </div>
        )}

        {/* Step 1: OCR 분석 */}
        {step === 1 && (
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            {analyzing ? (
              <>
                <Loader2 className="size-10 animate-spin" style={{ color: "var(--ocean)" }} />
                <p style={{ color: "var(--navy)", fontWeight: 600 }}>{stageLabel(analysisStage)}</p>
                <div className="w-full max-w-md">
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full transition-all duration-500" style={{ width: `${stageProgress(analysisStage)}%`, background: "var(--ocean)" }} />
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-muted-foreground"><span>업로드</span><span>OCR</span><span>추출</span><span>매칭</span><span>완료</span></div>
                </div>
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
                <p className="text-muted-foreground" style={{ fontSize: "14px" }}>{file?.name}</p>
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
            {analysisNotes.length > 0 && (
              <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <p className="font-medium">AI 확인 필요 항목</p>
                <ul className="mt-1 list-disc pl-5">
                  {analysisNotes.map((note) => <li key={note}>{note}</li>)}
                </ul>
              </div>
            )}
            {extractedValues && (
              <div className="mb-5 rounded-lg border border-blue-100 bg-blue-50/60 p-4">
                <p className="font-medium" style={{ color: "var(--navy)" }}>AI 원본 추출값</p>
                <p className="mt-1 text-xs text-muted-foreground">아래 값은 OCR·Solar가 문서에서 읽은 결과입니다. 최종 공고에는 수정한 값이 반영됩니다.</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {Object.entries(extractedValues).flatMap(([section, raw]) => {
                    const fields = typeof raw === "object" && raw !== null && "fields" in raw
                      ? (raw as { fields: Record<string, { value?: unknown; confidence?: number | null }> }).fields
                      : {};
                    return Object.entries(fields).map(([field, value]) => (
                      <div key={`${section}.${field}`} className="rounded-md border border-blue-100 bg-white px-3 py-2 text-sm">
                        <div className="text-xs text-muted-foreground">{section}.{field}</div>
                        <div className="mt-1 break-words font-medium">{String(value.value ?? "없음")}</div>
                        {value.confidence != null && <div className="mt-1 text-xs text-muted-foreground">신뢰도 {Math.round(value.confidence * 100)}%</div>}
                      </div>
                    ));
                  })}
                </div>
              </div>
            )}
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

function stageLabel(stage: ContractProcessingStage): string {
  return { uploading: "계약서 업로드 준비 중...", ocr: "문서 OCR 분석 중...", extracting: "계약 조건 추출 중...", matching: "Solar가 공고 필드에 매칭 중...", finalizing: "결과 정리 중..." }[stage];
}

function stageProgress(stage: ContractProcessingStage): number {
  return { uploading: 15, ocr: 35, extracting: 58, matching: 82, finalizing: 95 }[stage];
}
