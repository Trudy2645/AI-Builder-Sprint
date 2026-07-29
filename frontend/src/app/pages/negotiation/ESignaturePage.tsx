import { useEffect, type ReactNode } from "react";
import { ArrowLeft, CheckCircle2, Clock, PenLine, ShieldCheck, Building2, CalendarRange, FileCheck2, Wallet, FastForward } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Separator } from "../../components/ui/separator";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useApp } from "../../context/AppContext";
import { useRoleBase } from "../../hooks/useRoleBase";
import { useNegotiation } from "../../store/NegotiationContext";
import { finalContractInfo } from "../../data/negotiation";
import { formatKRW } from "../../data/contracts";

function InfoRow({ icon: Icon, label, children }: { icon: typeof Building2; label: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-3">
      <Icon className="mt-0.5 size-4 shrink-0" style={{ color: "var(--ocean)" }} />
      <div className="min-w-0 flex-1">
        <div className="text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>{label}</div>
        <div className="mt-0.5 break-words" style={{ fontWeight: 600 }}>{children}</div>
      </div>
    </div>
  );
}

function SignRow({ label, name, signed, signedText, waitingText }: { label: string; name: string; signed: boolean; signedText: string; waitingText: string }) {
  const color = signed ? "var(--success)" : "var(--warning)";
  const bg = signed ? "var(--success-soft)" : "var(--warning-soft)";
  const Icon = signed ? CheckCircle2 : Clock;
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>{label}</div>
        <div className="truncate" style={{ fontWeight: 600 }}>{name}</div>
      </div>
      <span className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1" style={{ background: bg, color, fontSize: "13px", fontWeight: 600 }}>
        <Icon className="size-4" />
        {signed ? signedText : waitingText}
      </span>
    </div>
  );
}

export function ESignaturePage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { role, base } = useRoleBase();
  const { flow, directContractId, directContract, bothApproved, buyerSigned, sellerSigned, bothSigned, sign } = useNegotiation();
  const isDirect = flow === "direct";
  const contractInfo = isDirect && directContract
    ? {
        ...finalContractInfo,
        title: directContract.title,
        seller: directContract.seller,
        period: directContract.period,
        estimatedTotal: directContract.total,
        currency: directContract.currency,
      }
    : finalContractInfo;
  const estimatedNote = isDirect && directContract
    ? `${directContract.rooms}실 × ${directContract.nights}박 · ${directContract.currency}`
    : t("es.estimatedNote");

  const mySigned = role === "buyer" ? buyerSigned : sellerSigned;

  // 협상 경로의 모두싸인 데모: 상대방은 먼저 서명을 완료하고 현재 사용자가 마지막 서명을 진행한다.
  // 조건 그대로 경로는 셀러의 공개 조건을 사전 동의로 간주해 바이어 서명만 받는다.
  useEffect(() => {
    if (isDirect) return;
    if (role === "buyer" && !sellerSigned) sign("seller");
    if (role === "seller" && !buyerSigned) sign("buyer");
  }, [isDirect, role, buyerSigned, sellerSigned]);

  // 양측 서명이 완료되면 자동으로 체결 완료 화면으로 이동.
  useEffect(() => {
    if (bothSigned) {
      const id = setTimeout(() => navigate(`${base}/signing/complete`), 800);
      return () => clearTimeout(id);
    }
  }, [bothSigned, base, navigate]);

  return (
    <div className="mx-auto max-w-[820px]">
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 gap-1.5 whitespace-nowrap"
        onClick={() => navigate(isDirect && directContractId ? `/buyer/explore/${directContractId}/request` : `${base}/signing`)}
      >
        <ArrowLeft className="size-4" />
        {t(isDirect ? "asis.title" : "fa.title")}
      </Button>

      <PageHeader title={t("es.title")} description={t("es.subtitle")} />

      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <ContractStepper current={5} skipped={isDirect ? [3, 4] : []} />
      </div>

      {isDirect && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--teal)", background: "var(--success-soft)" }}>
          <FastForward className="mt-0.5 size-5 shrink-0" style={{ color: "var(--teal)" }} />
          <p className="text-sm" style={{ color: "var(--navy)" }}>{t("es.directNotice")}</p>
        </div>
      )}

      {!isDirect && !bothApproved && (
        <div className="mb-6 flex items-start gap-2 break-words rounded-xl border p-4" style={{ borderColor: "var(--warning)", background: "var(--warning-soft)", color: "var(--warning)", fontSize: "13px", fontWeight: 600 }}>
          <Clock className="mt-0.5 size-4 shrink-0" />
          {t("fa.waiting")}
        </div>
      )}

      {/* Final contract info */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <h2 className="mb-2 break-words" style={{ color: "var(--navy)", fontSize: "16px", fontWeight: 700 }}>
          {t("es.contractInfo")}
        </h2>
        <div className="divide-y divide-border">
          {isDirect && directContract && (
            <InfoRow icon={FileCheck2} label={t("asis.contract")}>{directContract.title}</InfoRow>
          )}
          <InfoRow icon={Building2} label={t("es.parties")}>
            {contractInfo.buyer} <span className="text-muted-foreground">·</span> {contractInfo.seller}
          </InfoRow>
          <InfoRow icon={CalendarRange} label={t("es.period")}>{contractInfo.period}</InfoRow>
          <InfoRow icon={FileCheck2} label={t("es.finalVersion")}>
            <span className="inline-flex"><VersionBadge version={isDirect ? "v1" : finalContractInfo.finalVersion} /></span>
          </InfoRow>
          <InfoRow icon={Wallet} label={t("es.estimatedTotal")}>
            <span style={{ color: "var(--navy)" }}>{formatKRW(contractInfo.estimatedTotal)}</span>
            <div className="text-muted-foreground" style={{ fontSize: "12px", fontWeight: 400 }}>{estimatedNote}</div>
          </InfoRow>
        </div>
      </div>

      {/* Signature status */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <h2 className="mb-4 break-words" style={{ color: "var(--navy)", fontSize: "16px", fontWeight: 700 }}>
          {t("es.signStatus")}
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <SignRow label={t("fa.buyer")} name={contractInfo.buyer} signed={buyerSigned} signedText={t("es.signed")} waitingText={t("es.notSigned")} />
          <SignRow label={t("fa.seller")} name={contractInfo.seller} signed={sellerSigned} signedText={isDirect ? t("es.preApproved") : t("es.signed")} waitingText={t("es.notSigned")} />
        </div>

        <Separator className="my-5" />

        <div className="flex flex-col items-center gap-3">
          <Button
            size="lg"
            className="w-full gap-2 whitespace-nowrap sm:w-auto"
            style={{ background: "var(--navy)" }}
            disabled={(!isDirect && !bothApproved) || mySigned}
            onClick={() => {
              if (mySigned) {
                toast.info(t("es.alreadySigned"));
                return;
              }
              sign(role);
              toast.success(t("es.signedToast"));
            }}
          >
            <PenLine className="size-5" />
            {t("es.signButton")}
          </Button>
          <div className="flex items-start gap-1.5 text-center text-muted-foreground" style={{ fontSize: "12px" }}>
            <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
            {t("es.poweredBy")}
          </div>
        </div>
      </div>
    </div>
  );
}
