import { Check, Minus } from "lucide-react";
import { useApp } from "../../context/AppContext";

export const CONTRACT_STEPS = [1, 2, 3, 4, 5, 6] as const;
export type ContractStep = (typeof CONTRACT_STEPS)[number];

interface ContractStepperProps {
  current: ContractStep;
  skipped?: ContractStep[];
}

/**
 * Contract PROCESS progress (조건 확인 → 체결 완료).
 * Distinct from document versions (v1~v4) which are shown via VersionBadge.
 */
export function ContractStepper({ current, skipped = [] }: ContractStepperProps) {
  const { t } = useApp();
  const progress = Math.round((current / CONTRACT_STEPS.length) * 100);
  const hasSkipped = skipped.length > 0;

  return (
    <div className="w-full">
      <div className="md:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-semibold text-muted-foreground">계약 진행 {current}/{CONTRACT_STEPS.length}</div>
            <div className="mt-0.5 truncate font-semibold" style={{ color: "var(--navy)" }}>{t(`step.${current}`)}</div>
            {hasSkipped && <div className="mt-0.5 text-[11px] text-muted-foreground">협상·최종 검토 생략</div>}
          </div>
          <span className="shrink-0 text-sm font-bold" style={{ color: "var(--ocean)" }}>{progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full transition-[width]" style={{ width: `${progress}%`, background: "var(--ocean)" }} />
        </div>
      </div>
    <ol className="hidden items-start gap-0 md:flex">
      {CONTRACT_STEPS.map((step, i) => {
        const state: "done" | "active" | "skipped" | "todo" =
          skipped.includes(step)
            ? "skipped"
            : step < current
              ? "done"
              : step === current
                ? "active"
                : "todo";
        const isLast = i === CONTRACT_STEPS.length - 1;

        const circleStyle =
          state === "done"
              ? { background: "var(--teal)", color: "#fff", borderColor: "var(--teal)" }
              : state === "active"
                ? { background: "var(--ocean)", color: "#fff", borderColor: "var(--ocean)" }
                : state === "skipped"
                  ? { background: "var(--muted)", color: "var(--muted-foreground)", borderColor: "var(--border)" }
                : { background: "#fff", color: "var(--muted-foreground)", borderColor: "var(--border)" };

        return (
          <li key={step} className="flex min-w-0 flex-1 items-start">
            <div className="flex min-w-0 flex-col items-center gap-1.5">
              <div
                className="flex size-9 shrink-0 items-center justify-center rounded-full border-2"
                style={circleStyle}
                aria-current={state === "active" ? "step" : undefined}
              >
                {state === "done" ? (
                  <Check className="size-4" />
                ) : state === "skipped" ? (
                  <Minus className="size-4" />
                ) : (
                  <span style={{ fontSize: "14px", fontWeight: 600 }}>{step}</span>
                )}
              </div>
              <span
                className="max-w-[96px] break-keep text-center leading-tight"
                style={{
                  fontSize: "12px",
                  fontWeight: state === "active" ? 600 : 400,
                  color: state === "todo" ? "var(--muted-foreground)" : "var(--foreground)",
                }}
              >
                {t(`step.${step}`)}
                {state === "skipped" && <span className="mt-0.5 block text-[10px]">생략</span>}
              </span>
            </div>
            {!isLast && (
              <div
                className="mt-4 h-0.5 flex-1"
                style={{ background: step < current && !skipped.includes(step) ? "var(--teal)" : "var(--border)" }}
              />
            )}
          </li>
        );
      })}
    </ol>
    </div>
  );
}
