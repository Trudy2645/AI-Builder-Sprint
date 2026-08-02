import { AlertTriangle, Lightbulb, ShieldCheck } from "lucide-react";
import { useApp } from "../../context/AppContext";
import type { ReviewFinding } from "../../lib/sellerAi";

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
