import { useMemo, useState } from "react";
import { ArrowLeft, Sparkles, ArrowRight, FilePenLine, CheckCircle2, GitBranch } from "lucide-react";
import { useNavigate } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge, type ContractVersion } from "../../components/contract/VersionBadge";
import { ChangeLabelBadge } from "../../components/contract/ChangeLabelBadge";
import { toast } from "sonner";
import { useApp } from "../../context/AppContext";
import { useRoleBase } from "../../hooks/useRoleBase";
import { useNegotiation } from "../../store/NegotiationContext";
import {
  VERSION_ORDER,
  versionMetas,
  getVersionDiff,
  NEGOTIATION_CONTRACT_ID,
} from "../../data/negotiation";
import { getContract } from "../../data/contracts";
import { useAiChangeSummary } from "../../hooks/useAiChangeSummary";

const SELECTABLE: ContractVersion[] = VERSION_ORDER;

export function VersionComparePage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { role, base } = useRoleBase();
  const { approve } = useNegotiation();

  const [target, setTarget] = useState<ContractVersion>("v4");
  const diff = useMemo(() => getVersionDiff(target), [target]);
  const changeSummary = useAiChangeSummary(diff?.changes);
  const original = getContract(NEGOTIATION_CONTRACT_ID);

  const prevMeta = diff ? versionMetas[diff.from] : undefined;
  const newMeta = diff ? versionMetas[diff.to] : undefined;

  const requestMore = () => {
    if (role === "buyer") {
      navigate(`${base}/explore/${NEGOTIATION_CONTRACT_ID}/revise`);
    } else {
      navigate(`${base}/received/rcv-coastline`);
    }
  };

  return (
    <div className="mx-auto max-w-[1000px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate(`${base}/signing`)}>
        <ArrowLeft className="size-4" />
        {t("nav.signing")}
      </Button>

      <PageHeader title={t("vc.title")} description={t("vc.subtitle")} />

      {/* Process stepper — step 4 최종 검토 */}
      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={4} />
      </div>

      {/* Version selector */}
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card px-5 py-4">
        <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "13px", fontWeight: 600 }}>
          {t("vc.selectVersion")}
        </span>
        <div className="flex flex-wrap gap-2">
          {SELECTABLE.map((v) => {
            const active = v === target;
            return (
              <button
                key={v}
                type="button"
                onClick={() => setTarget(v)}
                className="rounded-lg border px-3 py-1.5 transition-colors"
                style={{
                  borderColor: active ? "var(--ocean)" : "var(--border)",
                  background: active ? "var(--info-soft)" : "var(--card)",
                }}
                aria-pressed={active}
              >
                <VersionBadge version={v} />
              </button>
            );
          })}
        </div>
      </div>

      {target === "v1" && original && (
        <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <div className="mb-4 flex items-center gap-2">
            <VersionBadge version="v1" />
            <span className="text-muted-foreground" style={{ fontSize: "13px" }}>셀러 공개 원본</span>
          </div>
          <div className="flex flex-col gap-4">
            {original.clauses.map((clause) => (
              <div key={clause.no} className="rounded-lg border p-4">
                <div className="flex items-center gap-2" style={{ fontWeight: 700, color: "var(--navy)" }}>
                  <span>{clause.no}</span>
                  <span>{clause.title}</span>
                </div>
                <p className="mt-2" style={{ fontSize: "13px", lineHeight: 1.7 }}>{clause.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {diff && prevMeta && newMeta && (
        <>
          {/* Prev → New header */}
          <div className="mb-4 flex flex-wrap items-center justify-center gap-3 rounded-xl border border-border bg-card px-5 py-4">
            <div className="flex flex-col items-center gap-1.5">
              <VersionBadge version={prevMeta.version} />
              <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>
                {t("vc.prevVersion")} · {prevMeta.authorName} · {prevMeta.date}
              </span>
            </div>
            <ArrowRight className="size-5 shrink-0" style={{ color: "var(--ocean)" }} />
            <div className="flex flex-col items-center gap-1.5">
              <VersionBadge version={newMeta.version} />
              <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>
                {t("vc.newVersion")} · {newMeta.authorName} · {newMeta.date}
              </span>
            </div>
          </div>

          {/* AI change summary */}
          <div className="mb-6 rounded-xl border p-5" style={{ borderColor: "var(--ocean)", background: "var(--info-soft)" }}>
            <div className="flex items-center gap-1.5 whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 700 }}>
              <Sparkles className="size-4" />
              {t("vc.aiSummary")}
            </div>
            <ul className="mt-2 flex flex-col gap-1.5">
              {changeSummary.loading && <li className="text-sm text-muted-foreground">AI가 변경 내용을 요약하는 중입니다.</li>}
              {changeSummary.error && <li className="text-sm text-destructive">{changeSummary.error}</li>}
              {changeSummary.lines.map((line, i) => (
                <li key={i} className="flex gap-2 text-foreground" style={{ fontSize: "14px", lineHeight: 1.7 }}>
                  <span style={{ color: "var(--ocean)" }}>•</span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Changed clauses */}
          <div className="mb-2 flex items-center gap-2">
            <h2 className="whitespace-nowrap" style={{ color: "var(--navy)", fontSize: "16px", fontWeight: 700 }}>
              {t("vc.changedClauses")}
            </h2>
            <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "13px" }}>
              {diff.changes.length}{t("vc.changeCount")}
            </span>
          </div>

          <div className="flex flex-col gap-4">
            {diff.changes.map((c) => (
              <div key={c.clauseNo} className="rounded-xl border border-border bg-card p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="whitespace-nowrap" style={{ color: "var(--ocean)", fontWeight: 700 }}>{c.clauseNo}</span>
                  <span style={{ fontWeight: 600 }}>{c.title}</span>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {c.labels.map((l) => (
                      <ChangeLabelBadge key={l} label={l} />
                    ))}
                  </div>
                </div>

                <p className="mt-2 text-muted-foreground" style={{ fontSize: "13px" }}>{c.note}</p>

                {/* Side-by-side prev vs new */}
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="rounded-lg border border-border p-3">
                    <div className="mb-1.5">
                      <VersionBadge version={prevMeta.version} showLabel={false} />
                    </div>
                    {c.prevText ? (
                      <p className="text-foreground" style={{ fontSize: "13px", lineHeight: 1.7 }}>{c.prevText}</p>
                    ) : (
                      <p className="italic text-muted-foreground" style={{ fontSize: "13px" }}>{t("vc.clauseAdded")}</p>
                    )}
                  </div>
                  <div
                    className="rounded-lg border p-3"
                    style={{
                      borderColor: c.newText ? "var(--ocean)" : "var(--coral)",
                      background: c.newText ? "var(--info-soft)" : "var(--coral-soft)",
                    }}
                  >
                    <div className="mb-1.5">
                      <VersionBadge version={newMeta.version} showLabel={false} />
                    </div>
                    {c.newText ? (
                      <p className="text-foreground" style={{ fontSize: "13px", lineHeight: 1.7 }}>{c.newText}</p>
                    ) : (
                      <p className="italic" style={{ fontSize: "13px", color: "var(--coral)" }}>{t("vc.clauseDeleted")}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Role-aware action buttons */}
          <div className="mt-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end [&_button]:w-full sm:[&_button]:w-auto">
            <Button variant="outline" className="gap-1.5 whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }} onClick={requestMore}>
              {role === "buyer" ? <FilePenLine className="size-4" /> : <GitBranch className="size-4" />}
              {role === "buyer" ? t("vc.requestMore") : t("vc.reCounter")}
            </Button>
            <Button
              className="gap-1.5 whitespace-nowrap"
              style={{ background: "var(--navy)" }}
              onClick={() => {
                approve(role);
                toast.success(t("fa.approvedToast"));
                navigate(`${base}/signing`);
              }}
            >
              <CheckCircle2 className="size-4" />
              {t("vc.approveFinal")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
