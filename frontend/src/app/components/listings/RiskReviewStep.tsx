import { AlertTriangle, Lightbulb, CheckCircle2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { useApp } from "../../context/AppContext";
import type { ListingDraft } from "../../store/ListingsContext";
import type { ReviewFinding } from "../../lib/sellerAi";

type DraftField = keyof ListingDraft;

interface Finding {
  id: string;
  field: DraftField;
  fieldLabelKey: string;
  original: string;
  reason: string;
  recommendation: string;
}

/**
 * 입력한 계약 조건을 heuristics로 검토해 확인이 필요한 조항을 도출한다. (데모 로직)
 */
export function analyzeDraft(draft: ListingDraft): Finding[] {
  const findings: Finding[] = [];

  if (!draft.cancellation.trim() || /협의|추후|별도/.test(draft.cancellation)) {
    findings.push({
      id: "f-cancellation",
      field: "cancellation",
      fieldLabelKey: "lf.cancellation",
      original: draft.cancellation || "-",
      reason:
        "무료 취소 기한과 취소 수수료가 명확하지 않으면 셀러가 체크인 직전까지 공실 위험을 부담할 수 있습니다.",
      recommendation:
        "체크인 7일 전까지 무료 취소하며, 이후 취소 시 객실 1박 공급 요금의 50%를 부과한다.",
    });
  }

  if (!draft.noShow.trim() || /협의|추후|별도/.test(draft.noShow)) {
    findings.push({
      id: "f-noshow",
      field: "noShow",
      fieldLabelKey: "lf.noShow",
      original: draft.noShow || "-",
      reason:
        "노쇼 정산 기준이 없으면 객실을 확보해 둔 셀러가 손실을 보전받기 어렵고 분쟁이 발생할 수 있습니다.",
      recommendation:
        "노쇼 발생 시 해당 객실의 1박 공급 요금 100%를 부과하며, 불가항력 사유는 상호 협의한다.",
    });
  }

  if (!draft.settlement.trim() || /추후|협의|별도/.test(draft.settlement)) {
    findings.push({
      id: "f-settlement-missing",
      field: "settlement",
      fieldLabelKey: "lf.settlement",
      original: draft.settlement || "-",
      reason:
        "정산 마감일, 지급일 또는 지급 주체가 모호하면 셀러의 대금 회수가 지연될 수 있습니다.",
      recommendation:
        "매월 말 이용 내역을 마감하고, 바이어는 다음 달 15일까지 확인된 공급 대금을 셀러에게 지급한다.",
    });
  } else if (/익익월|60일|60 ?days/i.test(draft.settlement)) {
    findings.push({
      id: "f-settlement",
      field: "settlement",
      fieldLabelKey: "lf.settlement",
      original: draft.settlement,
      reason:
        "60일 이후 지급은 셀러의 대금 회수와 현금 흐름에 불리할 수 있습니다. 지급일과 지급 주체를 더 앞당겨 명시해 보세요.",
      recommendation: "매월 말 이용 내역을 마감하고, 바이어는 다음 달 15일까지 셀러에게 공급 대금을 지급한다.",
    });
  }

  if (/모든 사고|일체의 책임|전적으로 책임/.test(draft.liability)) {
    findings.push({
      id: "f-liability-excessive",
      field: "liability",
      fieldLabelKey: "lf.liability",
      original: draft.liability,
      reason:
        "셀러가 원인과 관계없이 모든 사고 책임을 부담하는 문구는 책임 범위가 과도해 분쟁으로 이어질 수 있습니다.",
      recommendation:
        "각 당사자는 자신의 귀책 사유로 발생한 손해를 부담하며, 셀러의 배상 범위는 영업배상책임보험 한도와 관련 법령에 따른다.",
    });
  } else if (!draft.liability.trim()) {
    findings.push({
      id: "f-liability",
      field: "liability",
      fieldLabelKey: "lf.liability",
      original: "-",
      reason:
        "책임·배상 조건이 비어 있어 사고 발생 시 셀러가 부담할 범위와 보험 적용 여부가 불명확합니다.",
      recommendation:
        "안전사고 배상 책임은 셀러가 영업배상책임보험 한도 내에서 부담하며, 보험 가입 사실을 계약서에 명시한다.",
    });
  }

  return findings;
}

interface RiskReviewStepProps {
  draft: ListingDraft;
  applied: Record<string, boolean>;
  onApply: (field: DraftField, value: string, findingId: string) => void;
}

export function RiskReviewStep({ draft, applied, onApply }: RiskReviewStepProps) {
  const { t } = useApp();
  const findings = analyzeDraft(draft);

  if (findings.length === 0) {
    return (
      <div>
        <div className="flex flex-col items-center gap-3 rounded-xl border p-10 text-center" style={{ borderColor: "var(--success)", background: "var(--success-soft)" }}>
          <ShieldCheck className="size-8" style={{ color: "var(--success)" }} />
          <p style={{ color: "var(--success)", fontWeight: 600 }}>{t("risk.none")}</p>
        </div>
        <p className="mt-4 text-center text-xs text-muted-foreground">AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이나 계약의 법적 효력을 보장하지 않습니다.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--coral)", fontWeight: 600 }}>
        <AlertTriangle className="size-4" />
        {t("risk.found")} {findings.length}{t("card.riskUnit")}
      </div>

      <div className="flex flex-col gap-4">
        {findings.map((f) => {
          const isApplied = applied[f.id];
          return (
            <div key={f.id} className="rounded-xl border p-5" style={{ borderColor: "var(--coral)", background: "var(--coral-soft)" }}>
              <div className="flex items-center gap-2 whitespace-nowrap" style={{ color: "var(--coral)", fontWeight: 700 }}>
                <AlertTriangle className="size-4" />
                {t(f.fieldLabelKey)}
              </div>

              <div className="mt-3">
                <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>{t("risk.reason")}</div>
                <p className="mt-1 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{f.reason}</p>
              </div>

              <div className="mt-3 rounded-lg p-3" style={{ background: "#fff" }}>
                <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--teal)", fontSize: "12px", fontWeight: 600 }}>
                  <Lightbulb className="size-4" />
                  {t("risk.recommend")}
                </div>
                <p className="mt-1 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{f.recommendation}</p>
                <div className="mt-3">
                  {isApplied ? (
                    <span className="inline-flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--success)", fontSize: "13px", fontWeight: 600 }}>
                      <CheckCircle2 className="size-4" />
                      {t("risk.applied")}
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5 whitespace-nowrap"
                      style={{ borderColor: "var(--teal)", color: "var(--teal)" }}
                      onClick={() => {
                        onApply(f.field, f.recommendation, f.id);
                        toast.success(t("risk.applyToast"));
                      }}
                    >
                      <Lightbulb className="size-4" />
                      {t("risk.apply")}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-5 text-center text-xs text-muted-foreground">AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이나 계약의 법적 효력을 보장하지 않습니다.</p>
    </div>
  );
}

export function AIReviewStep({ findings }: { findings: ReviewFinding[] }) {
  const { t } = useApp();
  if (findings.length === 0) {
    return (
      <div>
        <div className="flex flex-col items-center gap-3 rounded-xl border p-10 text-center" style={{ borderColor: "var(--success)", background: "var(--success-soft)" }}>
          <ShieldCheck className="size-8" style={{ color: "var(--success)" }} />
          <p style={{ color: "var(--success)", fontWeight: 600 }}>{t("risk.none")}</p>
        </div>
        <p className="mt-4 text-center text-xs text-muted-foreground">AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이나 계약의 법적 효력을 보장하지 않습니다.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-1.5" style={{ color: "var(--coral)", fontWeight: 600 }}>
        <AlertTriangle className="size-4" />
        {t("risk.found")} {findings.length}{t("card.riskUnit")}
      </div>
      <div className="flex flex-col gap-4">
        {findings.map((finding) => (
          <div key={finding.id} className="rounded-xl border p-5" style={{ borderColor: "var(--coral)", background: "var(--coral-soft)" }}>
            <div className="flex flex-wrap items-center gap-2" style={{ color: "var(--coral)", fontWeight: 700 }}>
              <AlertTriangle className="size-4" />
              {finding.title}
              <span className="rounded-full bg-white px-2 py-0.5 text-xs uppercase">{finding.severity}</span>
            </div>
            <p className="mt-3 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{finding.explanation}</p>
            {finding.suggested_text && (
              <div className="mt-3 rounded-lg bg-white p-3">
                <div className="flex items-center gap-1.5" style={{ color: "var(--teal)", fontSize: "12px", fontWeight: 600 }}>
                  <Lightbulb className="size-4" />
                  {t("risk.recommend")}
                </div>
                <p className="mt-1 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{finding.suggested_text}</p>
              </div>
            )}
            <p className="mt-3 text-xs text-muted-foreground">{finding.disclaimer}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
