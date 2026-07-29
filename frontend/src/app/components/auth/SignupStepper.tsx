import { Check } from "lucide-react";
import { useApp } from "../../context/AppContext";

/**
 * SIGNUP flow progress (역할 선택 → 계정 정보 → 회사/사업자 정보 → 가입 완료).
 * This is the account-onboarding stepper — NOT the contract process stepper.
 */
export function SignupStepper({
  steps,
  current,
}: {
  steps: string[]; // translation keys
  current: number; // 0-based index of active step
}) {
  const { t } = useApp();
  const stepNumber = current + 1;
  const progress = Math.round((stepNumber / steps.length) * 100);
  return (
    <>
      <div className="mb-6 sm:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0"><div className="text-xs text-muted-foreground">가입 단계 {stepNumber}/{steps.length}</div><div className="mt-0.5 truncate font-semibold" style={{ color: "var(--navy)" }}>{t(steps[current])}</div></div>
          <span className="shrink-0 text-sm font-bold" style={{ color: "var(--ocean)" }}>{progress}%</span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${progress}%`, background: "var(--ocean)" }} /></div>
      </div>
    <ol className="mb-8 hidden w-full items-start sm:flex">
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
                className="flex size-8 shrink-0 items-center justify-center rounded-full border-2"
                style={circleStyle}
                aria-current={state === "active" ? "step" : undefined}
              >
                {state === "done" ? (
                  <Check className="size-4" />
                ) : (
                  <span style={{ fontSize: "13px", fontWeight: 600 }}>{i + 1}</span>
                )}
              </div>
              <span
                className="whitespace-nowrap text-center"
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
                className="mt-3.5 h-0.5 flex-1"
                style={{ background: i < current ? "var(--teal)" : "var(--border)" }}
              />
            )}
          </li>
        );
      })}
    </ol>
    </>
  );
}
