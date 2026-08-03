import { useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Lightbulb, Loader2, Pencil, RefreshCw, Save, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
import { useApp } from "../../context/AppContext";
import type { ContractReviewFinding } from "../../lib/api";
import type { ListingDraft } from "../../store/ListingsContext";

type DraftField = keyof ListingDraft;

interface LocalFinding {
  id: string;
  field: DraftField;
  fieldLabelKey: string;
  original: string;
  reason: string;
  recommendation: string;
}

type ReviewFinding = ContractReviewFinding | LocalFinding;

const CATEGORY_FIELD_MAP: Record<string, DraftField> = {
  cancellation: "cancellation",
  cancellation_refund: "cancellation",
  refund: "cancellation",
  no_show: "noShow",
  settlement: "settlement",
  payment: "settlement",
  liability: "liability",
  termination: "termination",
  special_terms: "special",
};

/**
 * 수기 작성 화면을 위한 기존 로컬 보조 규칙입니다.
 * 업로드/OCR 화면은 이 함수를 사용하지 않고 백엔드 계약 검토 결과를 사용합니다.
 */
export function analyzeDraft(draft: ListingDraft): LocalFinding[] {
  const findings: LocalFinding[] = [];

  if (!draft.cancellation.trim() || /협의|추후|별도/.test(draft.cancellation)) {
    findings.push({
      id: "f-cancellation",
      field: "cancellation",
      fieldLabelKey: "lf.cancellation",
      original: draft.cancellation || "-",
      reason: "무료 취소 기한과 취소 수수료가 명확하지 않으면 셀러가 체크인 직전까지 공실 위험을 부담할 수 있습니다.",
      recommendation: "체크인 7일 전까지 무료 취소하며, 이후 취소 시 객실 1박 공급 요금의 50%를 부과한다.",
    });
  }

  if (!draft.noShow.trim() || /협의|추후|별도/.test(draft.noShow)) {
    findings.push({
      id: "f-noshow",
      field: "noShow",
      fieldLabelKey: "lf.noShow",
      original: draft.noShow || "-",
      reason: "노쇼 정산 기준이 없으면 객실을 확보해 둔 셀러가 손실을 보전받기 어렵고 분쟁이 발생할 수 있습니다.",
      recommendation: "노쇼 발생 시 해당 객실의 1박 공급 요금 100%를 부과하며, 불가항력 사유는 상호 협의한다.",
    });
  }

  if (!draft.settlement.trim() || /추후|협의|별도/.test(draft.settlement)) {
    findings.push({
      id: "f-settlement-missing",
      field: "settlement",
      fieldLabelKey: "lf.settlement",
      original: draft.settlement || "-",
      reason: "정산 마감일, 지급일 또는 지급 주체가 모호하면 셀러의 대금 회수가 지연될 수 있습니다.",
      recommendation: "매월 말 이용 내역을 마감하고, 바이어는 다음 달 15일까지 확인된 공급 대금을 셀러에게 지급한다.",
    });
  } else if (/익익월|60일|60 ?days/i.test(draft.settlement)) {
    findings.push({
      id: "f-settlement",
      field: "settlement",
      fieldLabelKey: "lf.settlement",
      original: draft.settlement,
      reason: "60일 이후 지급은 셀러의 대금 회수와 현금 흐름에 불리할 수 있습니다. 지급일과 지급 주체를 더 앞당겨 명시해 보세요.",
      recommendation: "매월 말 이용 내역을 마감하고, 바이어는 다음 달 15일까지 셀러에게 공급 대금을 지급한다.",
    });
  }

  if (/모든 사고|일체의 책임|전적으로 책임/.test(draft.liability)) {
    findings.push({
      id: "f-liability-excessive",
      field: "liability",
      fieldLabelKey: "lf.liability",
      original: draft.liability,
      reason: "셀러가 원인과 관계없이 모든 사고 책임을 부담하는 문구는 책임 범위가 과도해 분쟁으로 이어질 수 있습니다.",
      recommendation: "각 당사자는 자신의 귀책 사유로 발생한 손해를 부담하며, 셀러의 배상 범위는 영업배상책임보험 한도와 관련 법령에 따른다.",
    });
  } else if (!draft.liability.trim()) {
    findings.push({
      id: "f-liability",
      field: "liability",
      fieldLabelKey: "lf.liability",
      original: "-",
      reason: "책임·배상 조건이 비어 있어 사고 발생 시 셀러가 부담할 범위와 보험 적용 여부가 불명확합니다.",
      recommendation: "안전사고 배상 책임은 셀러가 영업배상책임보험 한도 내에서 부담하며, 보험 가입 사실을 계약서에 명시한다.",
    });
  }

  return findings;
}

interface ListingClause {
  id: string;
  clause_order: number;
  title: string;
  body: string;
}

interface RiskReviewStepProps {
  draft: ListingDraft;
  applied: Record<string, boolean>;
  onApply: (field: DraftField, value: string, findingId: string) => void;
  /** undefined keeps the manual-writing compatibility path; null means remote analysis has not returned yet. */
  findings?: ContractReviewFinding[] | null;
  clauses?: ListingClause[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

function isLocalFinding(finding: ReviewFinding): finding is LocalFinding {
  return "field" in finding;
}

function fieldForFinding(finding: ReviewFinding): DraftField | null {
  if (isLocalFinding(finding)) return finding.field;
  return CATEGORY_FIELD_MAP[finding.category] ?? null;
}

function titleForFinding(finding: ReviewFinding, translate: (key: string) => string): string {
  return isLocalFinding(finding) ? translate(finding.fieldLabelKey) : finding.title;
}

function explanationForFinding(finding: ReviewFinding): string {
  return isLocalFinding(finding) ? finding.reason : finding.explanation;
}

function recommendationForFinding(finding: ReviewFinding): string {
  return isLocalFinding(finding) ? finding.recommendation : finding.suggested_text ?? "";
}

function severityStyle(finding: ReviewFinding): { color: string; background: string } {
  if (isLocalFinding(finding)) return { color: "var(--coral)", background: "var(--coral-soft)" };
  if (finding.severity === "high") return { color: "#b42318", background: "#fff1f0" };
  if (finding.severity === "low" || finding.severity === "none") return { color: "#946200", background: "#fff8e8" };
  return { color: "var(--coral)", background: "var(--coral-soft)" };
}

function groundingLabel(finding: ReviewFinding): string | null {
  if (isLocalFinding(finding)) return null;
  if (finding.grounding_status === "grounded") return "근거 자료 확인됨";
  if (finding.grounding_status === "insufficient_evidence") return "참고 근거가 충분하지 않음";
  return "계약 조항 기반 검토";
}

export function RiskReviewStep({
  draft,
  applied,
  onApply,
  findings,
  clauses = [],
  loading = false,
  error = null,
  onRetry,
}: RiskReviewStepProps) {
  const { t } = useApp();
  const [editing, setEditing] = useState<Record<string, boolean>>({});
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-xl border border-[var(--ocean)] bg-[var(--info-soft)] p-10 text-center">
        <Loader2 className="size-9 animate-spin" style={{ color: "var(--ocean)" }} />
        <div>
          <p style={{ color: "var(--navy)", fontWeight: 700 }}>AI가 계약서 조항을 검토하고 있습니다.</p>
          <p className="mt-1 text-sm text-muted-foreground">OCR로 추출한 조항과 계약 조건을 바탕으로 위험 요소를 분석하는 중입니다.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-xl border border-red-200 bg-red-50 p-8 text-center">
        <AlertTriangle className="size-8 text-red-600" />
        <div>
          <p className="font-semibold text-red-800">AI 위험 검토를 불러오지 못했습니다.</p>
          <p className="mt-1 text-sm text-red-700">{error}</p>
        </div>
        {onRetry && (
          <Button variant="outline" className="gap-1.5 bg-white" onClick={onRetry}>
            <RefreshCw className="size-4" />
            다시 분석
          </Button>
        )}
      </div>
    );
  }

  const localFindings = findings === undefined ? analyzeDraft(draft) : [];
  const visibleFindings: ReviewFinding[] = findings === undefined ? localFindings : findings ?? [];

  if (visibleFindings.length === 0) {
    return (
      <div>
        <div className="flex flex-col items-center gap-3 rounded-xl border p-10 text-center" style={{ borderColor: "var(--success)", background: "var(--success-soft)" }}>
          <ShieldCheck className="size-8" style={{ color: "var(--success)" }} />
          <p style={{ color: "var(--success)", fontWeight: 600 }}>{findings === undefined ? t("risk.none") : "AI 검토 결과 위험 요소가 발견되지 않았습니다."}</p>
          {findings !== undefined && <p className="text-sm text-muted-foreground">{clauses.length}개 계약 조항을 검토했습니다.</p>}
        </div>
        <p className="mt-4 text-center text-xs text-muted-foreground">AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이나 계약의 법적 효력을 보장하지 않습니다.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--coral)", fontWeight: 600 }}>
        <AlertTriangle className="size-4" />
        {findings === undefined ? t("risk.found") : "AI가 확인한 위험 요소"} {visibleFindings.length}개
      </div>

      <div className="flex flex-col gap-4">
        {visibleFindings.map((finding) => {
          const field = fieldForFinding(finding);
          const isApplied = applied[finding.id];
          const isEditing = editing[finding.id];
          const editValue = draftValues[finding.id] ?? (field ? String(draft[field] ?? "") : "");
          const recommendation = recommendationForFinding(finding);
          const clause = !isLocalFinding(finding) && finding.clause_id
            ? clauses.find((item) => item.id === finding.clause_id)
            : undefined;
          const style = severityStyle(finding);
          const grounding = groundingLabel(finding);

          return (
            <div key={finding.id} className="rounded-xl border p-5" style={{ borderColor: style.color, background: style.background }}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2" style={{ color: style.color, fontWeight: 700 }}>
                  <AlertTriangle className="size-4" />
                  <span>{titleForFinding(finding, t)}</span>
                </div>
                {field && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5 whitespace-nowrap bg-white"
                    onClick={() => {
                      setEditing((prev) => ({ ...prev, [finding.id]: !prev[finding.id] }));
                      setDraftValues((prev) => ({ ...prev, [finding.id]: prev[finding.id] ?? String(draft[field] ?? "") }));
                    }}
                  >
                    <Pencil className="size-4" />
                    {isEditing ? "수정 닫기" : "직접 수정"}
                  </Button>
                )}
              </div>

              {clause && (
                <div className="mt-3 rounded-lg border border-border bg-white p-3">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                    <FileText className="size-4" />
                    제{clause.clause_order}조 · {clause.title}
                  </div>
                  <p className="mt-1 text-sm leading-6 text-foreground">{clause.body}</p>
                </div>
              )}

              <div className="mt-3">
                <div className="whitespace-nowrap text-xs font-semibold text-muted-foreground">검토 이유</div>
                <p className="mt-1 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{explanationForFinding(finding)}</p>
              </div>

              {isEditing && field && (
                <div className="mt-3 rounded-lg border border-border bg-white p-3">
                  <div className="mb-2 whitespace-nowrap text-xs font-semibold text-muted-foreground">현재 조항 직접 수정</div>
                  <Textarea rows={4} value={editValue} onChange={(event) => setDraftValues((prev) => ({ ...prev, [finding.id]: event.target.value }))} />
                  <div className="mt-3 flex justify-end">
                    <Button
                      size="sm"
                      className="gap-1.5 whitespace-nowrap"
                      onClick={() => {
                        onApply(field, editValue, finding.id);
                        setEditing((prev) => ({ ...prev, [finding.id]: false }));
                        toast.success("수정한 문구를 반영했습니다.");
                      }}
                    >
                      <Save className="size-4" />
                      수정 저장
                    </Button>
                  </div>
                </div>
              )}

              {recommendation && (
                <div className="mt-3 rounded-lg bg-white p-3">
                  <div className="flex items-center gap-1.5 whitespace-nowrap text-xs font-semibold" style={{ color: "var(--teal)" }}>
                    <Lightbulb className="size-4" />
                    AI 권장 문구
                  </div>
                  <p className="mt-1 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{recommendation}</p>
                  <div className="mt-3">
                    {isApplied ? (
                      <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm font-semibold" style={{ color: "var(--success)" }}>
                        <CheckCircle2 className="size-4" />
                        {t("risk.applied")}
                      </span>
                    ) : field ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1.5 whitespace-nowrap"
                        style={{ borderColor: "var(--teal)", color: "var(--teal)" }}
                        onClick={() => {
                          onApply(field, recommendation, finding.id);
                          toast.success(t("risk.applyToast"));
                        }}
                      >
                        <Lightbulb className="size-4" />
                        권장 문구 반영
                      </Button>
                    ) : (
                      <p className="text-xs text-muted-foreground">이 조항은 아래 계약 조건 확인 화면에서 직접 수정해 주세요.</p>
                    )}
                  </div>
                </div>
              )}

              {(grounding || (!isLocalFinding(finding) && finding.confidence != null)) && (
                <div className="mt-3 text-xs text-muted-foreground">
                  {grounding}{grounding && finding.confidence != null ? " · " : ""}{!isLocalFinding(finding) && finding.confidence != null ? `신뢰도 ${Math.round(finding.confidence * 100)}%` : ""}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-5 text-center text-xs text-muted-foreground">{!isLocalFinding(visibleFindings[0]) ? visibleFindings[0].disclaimer : "AI 분석은 계약 검토를 돕기 위한 참고 의견이며 법률 자문이나 계약의 법적 효력을 보장하지 않습니다."}</p>
    </div>
  );
}
