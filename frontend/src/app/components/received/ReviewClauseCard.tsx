import { Check, X, GitBranch, Sparkles, AlertTriangle, Lightbulb, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { VersionBadge } from "../contract/VersionBadge";
import { useApp } from "../../context/AppContext";

export interface ReceivedRevision {
  id: string;
  clauseNo: string;
  clauseTitle: string;
  original: string;
  requested: string;
  reason: string;
  aiImpact: string;
  aiRecommend: string;
}

export type DecisionKind = "accept" | "reject" | "counter";

export interface Decision {
  kind?: DecisionKind;
  counterText: string;
  counterReason: string;
  message: string;
}

export function emptyDecision(): Decision {
  return { kind: undefined, counterText: "", counterReason: "", message: "" };
}

function DecisionButton({
  active,
  color,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  color: string;
  icon: typeof Check;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border px-3 py-2 transition-colors"
      style={{
        fontSize: "14px",
        fontWeight: 600,
        borderColor: active ? color : "var(--border)",
        background: active ? color : "var(--card)",
        color: active ? "#fff" : "var(--foreground)",
      }}
      aria-pressed={active}
    >
      <Icon className="size-4" />
      {label}
    </button>
  );
}

interface Props {
  index: number;
  revision: ReceivedRevision;
  decision: Decision;
  onChange: (d: Decision) => void;
}

export function ReviewClauseCard({ index, revision, decision, onChange }: Props) {
  const { t } = useApp();
  const set = (patch: Partial<Decision>) => onChange({ ...decision, ...patch });

  return (
    <div className="rounded-xl border border-border bg-card p-6">
      {/* Header: clause no + title */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="flex size-6 items-center justify-center rounded-full"
          style={{ background: "var(--navy)", color: "#fff", fontSize: "12px", fontWeight: 700 }}
        >
          {index + 1}
        </span>
        <span className="whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 700 }}>{revision.clauseNo}</span>
        <span style={{ fontWeight: 600 }}>{revision.clauseTitle}</span>
      </div>

      {/* Original vs requested */}
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-border p-3">
          <div className="mb-1.5 flex items-center gap-1.5">
            <VersionBadge version="v1" />
            <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>{t("rvw.clauseOriginal")}</span>
          </div>
          <p className="text-foreground" style={{ fontSize: "13px", lineHeight: 1.7 }}>{revision.original}</p>
        </div>
        <div className="rounded-lg border p-3" style={{ borderColor: "var(--ocean)", background: "var(--info-soft)" }}>
          <div className="mb-1.5 flex items-center gap-1.5">
            <VersionBadge version="v2" />
            <span className="whitespace-nowrap" style={{ color: "var(--ocean)", fontSize: "12px", fontWeight: 600 }}>{t("rvw.buyerRequested")}</span>
          </div>
          <p className="text-foreground" style={{ fontSize: "13px", lineHeight: 1.7 }}>{revision.requested}</p>
        </div>
      </div>

      {/* Reason */}
      <div className="mt-3">
        <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>{t("rvw.reason")}</div>
        <p className="mt-1 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>{revision.reason}</p>
      </div>

      {/* AI impact analysis */}
      <div className="mt-3 rounded-lg p-3" style={{ background: "var(--surface)" }}>
        <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--ocean)", fontSize: "12px", fontWeight: 700 }}>
          <Sparkles className="size-4" />
          {t("rvw.aiImpact")}
        </div>
        <p className="mt-1 text-foreground" style={{ fontSize: "13px", lineHeight: 1.7 }}>{revision.aiImpact}</p>
      </div>

      {/* Decision buttons */}
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <DecisionButton active={decision.kind === "accept"} color="var(--success)" icon={Check} label={t("rvw.accept")} onClick={() => set({ kind: "accept" })} />
        <DecisionButton active={decision.kind === "reject"} color="var(--coral)" icon={X} label={t("rvw.reject")} onClick={() => set({ kind: "reject" })} />
        <DecisionButton active={decision.kind === "counter"} color="var(--ocean)" icon={GitBranch} label={t("rvw.counter")} onClick={() => set({ kind: "counter" })} />
      </div>

      {/* Counter-offer form */}
      {decision.kind === "counter" && (
        <div className="mt-4 flex flex-col gap-4 rounded-lg border p-4" style={{ borderColor: "var(--ocean)" }}>
          <div className="flex flex-col gap-1.5">
            <Label className="whitespace-nowrap">{t("rvw.counterText")}</Label>
            <Textarea rows={3} value={decision.counterText} placeholder={t("rvw.counterTextPh")} onChange={(e) => set({ counterText: e.target.value })} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="whitespace-nowrap">{t("rvw.counterReason")}</Label>
            <Textarea rows={2} value={decision.counterReason} placeholder={t("rvw.counterReasonPh")} onChange={(e) => set({ counterReason: e.target.value })} />
          </div>

          {/* AI recommendation */}
          <div className="rounded-lg p-3" style={{ background: "var(--success-soft)" }}>
            <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--teal)", fontSize: "12px", fontWeight: 700 }}>
              <Lightbulb className="size-4" />
              {t("rvw.aiRecommend")}
            </div>
            <p className="mt-1 text-foreground" style={{ fontSize: "13px", lineHeight: 1.7 }}>{revision.aiRecommend}</p>
            <Button
              size="sm"
              variant="outline"
              className="mt-2 gap-1.5 whitespace-nowrap"
              style={{ borderColor: "var(--teal)", color: "var(--teal)" }}
              onClick={() => {
                set({ counterText: revision.aiRecommend });
                toast.success(t("risk.applyToast"));
              }}
            >
              <Lightbulb className="size-4" />
              {t("rvw.applyAi")}
            </Button>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="whitespace-nowrap">{t("rvw.message")}</Label>
            <Textarea rows={2} value={decision.message} placeholder={t("rvw.messagePh")} onChange={(e) => set({ message: e.target.value })} />
          </div>
        </div>
      )}

      {/* Rejection note (optional message) */}
      {decision.kind === "reject" && (
        <div className="mt-4 flex flex-col gap-1.5 rounded-lg border p-4" style={{ borderColor: "var(--coral)" }}>
          <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--coral)", fontSize: "13px", fontWeight: 600 }}>
            <AlertTriangle className="size-4" />
            {t("rvw.message")}
          </div>
          <Textarea rows={2} value={decision.message} placeholder={t("rvw.messagePh")} onChange={(e) => set({ message: e.target.value })} />
        </div>
      )}

      {/* Accept note */}
      {decision.kind === "accept" && (
        <div className="mt-4 flex items-center gap-1.5 whitespace-nowrap rounded-lg p-3" style={{ background: "var(--success-soft)", color: "var(--success)", fontSize: "13px", fontWeight: 600 }}>
          <Check className="size-4" />
          {t("rvw.buyerRequested")}
          <ArrowRight className="size-4" />
          {t("version.v4")}
        </div>
      )}
    </div>
  );
}
