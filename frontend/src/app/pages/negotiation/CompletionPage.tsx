import { useEffect, type ReactNode } from "react";
import { CheckCircle2, Download, FileSearch, ListChecks, Hash, FileCheck2, Clock, Building2 } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { Separator } from "../../components/ui/separator";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { useApp } from "../../context/AppContext";
import { useRoleBase } from "../../hooks/useRoleBase";
import { useNegotiation } from "../../store/NegotiationContext";
import { useRequests } from "../../store/RequestsContext";
import { finalContractInfo, NEGOTIATION_CONTRACT_ID } from "../../data/negotiation";

function DetailRow({ icon: Icon, label, children }: { icon: typeof Hash; label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-1 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
      <div className="flex items-center gap-2 text-muted-foreground" style={{ fontSize: "13px", fontWeight: 600 }}>
        <Icon className="size-4 shrink-0" style={{ color: "var(--ocean)" }} />
        {label}
      </div>
      <div className="max-w-full break-all text-left sm:text-right" style={{ fontWeight: 600 }}>{children}</div>
    </div>
  );
}

export function CompletionPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { base, role } = useRoleBase();
  const { flow, directRequestId, directContractId, bothSigned, contractNo, signedAt } = useNegotiation();
  const { updateRequestStatus } = useRequests();
  const isDirect = flow === "direct";

  useEffect(() => {
    if (!bothSigned) return;
    updateRequestStatus(directRequestId ?? "req-summer-main", "completed", {
      currentVersion: isDirect ? "v1" : "v4",
      latestResponse: isDirect
        ? "바이어가 공개 조건에 전자서명하여 계약이 체결되었습니다. 셀러에게 체결 완료 알림을 보냈습니다."
        : "양측 전자서명이 완료되어 계약이 체결되었습니다.",
    });
  }, [bothSigned, directRequestId, isDirect]);

  const downloadContract = () => {
    const content = [
      "BUSAN LINK 최종 전자계약서",
      "",
      "계약명: 2026 부산 여름 객실 공급 계약",
      `계약번호: ${contractNo}`,
      `바이어: ${finalContractInfo.buyer}`,
      `셀러: ${finalContractInfo.seller}`,
      `계약기간: ${finalContractInfo.period}`,
      `최종버전: ${isDirect ? "v1" : finalContractInfo.finalVersion}`,
      `체결시각: ${signedAt}`,
      "",
      "핵심 조건",
      "- 주말 객실 15실, 2박, 일본인 관광객 30명 기준",
      "- 객실당 145,000원 / 총 예상금액 4,350,000원",
      "- 체크인 7일 전까지 무료 취소, 이후 50% 부과",
      "- 노쇼 시 해당 객실 1박 공급 요금 100% 부과",
      "- 매월 말 마감 후 다음 달 15일까지 바이어가 셀러에게 지급",
      "",
      isDirect
        ? "전자서명 상태: 바이어 서명 완료 · 셀러 공개 조건 사전 동의"
        : "전자서명 상태: 바이어·셀러 서명 완료",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${contractNo || "Busan-Link"}-최종계약서.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success(t("cc.pdfToast"));
  };

  if (!bothSigned) {
    return (
      <div className="mx-auto max-w-[640px] rounded-xl border border-dashed p-10 text-center sm:p-16">
        <Clock className="mx-auto mb-3 size-8" style={{ color: "var(--warning)" }} />
        <p className="text-muted-foreground">{t("cc.notYet")}</p>
        <Button className="mt-4 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/signing/sign`)}>
          {t("es.title")}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[720px]">
      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <ContractStepper current={6} skipped={isDirect ? [3, 4] : []} />
      </div>

      {/* Success hero */}
      <div className="mb-6 rounded-xl border p-5 text-center sm:p-8" style={{ borderColor: "var(--success)", background: "var(--success-soft)" }}>
        <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full" style={{ background: "var(--success)" }}>
          <CheckCircle2 className="size-9" style={{ color: "#fff" }} />
        </div>
        <h1 className="break-words" style={{ color: "var(--success)" }}>{t("cc.title")}</h1>
        <p className="mt-2 text-foreground" style={{ fontSize: "14px" }}>{t(isDirect ? "cc.directMessage" : "cc.message")}</p>
      </div>

      {/* Contract detail card */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="flex items-start gap-2 break-words" style={{ fontWeight: 700, color: "var(--navy)" }}>
          <Building2 className="mt-0.5 size-4 shrink-0" style={{ color: "var(--ocean)" }} />
          <span>2026 부산 여름 객실 공급 계약</span>
        </div>
        <div className="text-muted-foreground" style={{ fontSize: "13px" }}>
          {finalContractInfo.buyer} · {finalContractInfo.seller}
        </div>

        <Separator className="my-4" />

        <div className="divide-y divide-border">
          <DetailRow icon={Hash} label={t("cc.contractNo")}>
            <span style={{ color: "var(--navy)", fontFamily: "monospace" }}>{contractNo}</span>
          </DetailRow>
          <DetailRow icon={FileCheck2} label={t("cc.finalVersion")}>
            <span className="inline-flex"><VersionBadge version={isDirect ? "v1" : finalContractInfo.finalVersion} /></span>
          </DetailRow>
          <DetailRow icon={Clock} label={t("cc.signedAt")}>{signedAt}</DetailRow>
          <DetailRow icon={CheckCircle2} label={t(isDirect ? "cc.signingBasis" : "cc.bothSigned")}>
            <span className="inline-flex max-w-full flex-wrap items-center gap-1.5 rounded-md px-2 py-0.5" style={{ background: "var(--success-soft)", color: "var(--success)", fontSize: "13px" }}>
              <CheckCircle2 className="size-3.5 shrink-0" />
              {isDirect ? t("cc.directSigned") : `${finalContractInfo.buyer} · ${finalContractInfo.seller}`}
            </span>
          </DetailRow>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2">
        <Button size="lg" className="gap-2 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={downloadContract}>
          <Download className="size-5" />
          {t("cc.downloadPdf")}
        </Button>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="outline" className="flex-1 gap-1.5 whitespace-nowrap" onClick={() => navigate(role === "buyer" ? `/buyer/explore/${directContractId ?? NEGOTIATION_CONTRACT_ID}` : `${base}/contracts`)}>
            <FileSearch className="size-4" />
            {t("cc.viewDetail")}
          </Button>
          <Button variant="outline" className="flex-1 gap-1.5 whitespace-nowrap" onClick={() => navigate(`${base}/contracts`)}>
            <ListChecks className="size-4" />
            {t("cc.goList")}
          </Button>
        </div>
      </div>
    </div>
  );
}
