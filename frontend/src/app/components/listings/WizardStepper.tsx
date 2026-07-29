import { Check } from "lucide-react";
import { useApp } from "../../context/AppContext";

/**
 * 공고 작성 위저드용 단계 표시.
 * 계약 진행 단계(ContractStepper, 1~6)와는 별개의 흐름이므로 별도 컴포넌트로 둔다.
 */
export function WizardStepper({ steps, current }: { steps: string[]; current: number }) {
  const { t } = useApp();
  const stepNumber = current + 1;
  const progress = Math.round((stepNumber / steps.length) * 100);

  return (
    <div className="w-full">
      <div className="md:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-semibold text-muted-foreground">작성 단계 {stepNumber}/{steps.length}</div>
            <div className="mt-0.5 truncate font-semibold" style={{ color: "var(--navy)" }}>{t(steps[current])}</div>
          </div>
          <span className="shrink-0 text-sm font-bold" style={{ color: "var(--ocean)" }}>{progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full transition-[width]" style={{ width: `${progress}%`, background: "var(--ocean)" }} />
        </div>
      </div>
    <ol className="hidden items-start gap-0 md:flex">
      {steps.map((key, i) => {
        const state: "done" | "active" | "todo" =
          i < current ? "done" : i === current ? "active" : "todo";
        const isLast = i === steps.length - 1;

        const circleStyle =
          state === "done"
            ? { background: "var(--teal)", color: "#fff", borderColor: "var(--teal)" }
            : state === "active"
              ? { background: "var(--ocean)", color: "#fff", borderColor: "var(--ocean)" }
              : { background: "#fff", color: "var(--muted-foreground)", borderColor: "var(--border)" };

        return (
          <li key={key} className="flex min-w-0 flex-1 items-start">
            <div className="flex min-w-0 flex-col items-center gap-1.5">
              <div
                className="flex size-9 shrink-0 items-center justify-center rounded-full border-2"
                style={circleStyle}
                aria-current={state === "active" ? "step" : undefined}
              >
                {state === "done" ? (
                  <Check className="size-4" />
                ) : (
                  <span style={{ fontSize: "14px", fontWeight: 600 }}>{i + 1}</span>
                )}
              </div>
              <span
                className="max-w-[104px] break-keep text-center leading-tight"
                style={{
                  fontSize: "12px",
                  fontWeight: state === "active" ? 600 : 400,
                  color: state === "todo" ? "var(--muted-foreground)" : "var(--foreground)",
                }}
              >
                {t(key)}
              </span>
            </div>
            {!isLast && (
              <div
                className="mt-4 h-0.5 flex-1"
                style={{ background: i < current ? "var(--teal)" : "var(--border)" }}
              />
            )}
          </li>
        );
      })}
    </ol>
    </div>
  );
}
