import { useEffect, useState, type ReactNode } from "react";
import {
  Building2,
  CalendarRange,
  CheckCircle2,
  Clock,
  Download,
  FileCheck2,
  FileSearch,
  Hash,
  History,
  ListChecks,
  UsersRound,
  Wallet,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { PageHeader } from "../../components/PageHeader";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { Separator } from "../../components/ui/separator";
import { useApp } from "../../context/AppContext";
import { useRoleBase } from "../../hooks/useRoleBase";
import { useNegotiation } from "../../store/NegotiationContext";
import { useRequests } from "../../store/RequestsContext";
import { finalContractInfo, NEGOTIATION_CONTRACT_ID } from "../../data/negotiation";
import { formatKRW } from "../../data/contracts";
import {
  downloadModusignFile,
  friendlyApiError,
  getContractDetail,
  getSignatureRequest,
  type ContractDetail,
  type SignatureRequest,
} from "../../lib/api";

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
  const [params] = useSearchParams();
  const { base, role } = useRoleBase();
  const contractId = params.get("contractId");
  const versionId = params.get("versionId");
  const signatureRequestId = params.get("signatureRequestId");
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [request, setRequest] = useState<SignatureRequest | null>(null);

  const { flow, directRequestId, directContractId, directContract, bothSigned, contractNo, signedAt } = useNegotiation();
  const { updateRequestStatus } = useRequests();
  const isDirect = flow === "direct";
  const direct = isDirect ? directContract : undefined;
  const contractTitle = direct?.title ?? "2026 해운대 단체 객실 공급 계약";
  const contractSeller = direct?.seller ?? finalContractInfo.seller;
  const contractPeriod = direct?.period ?? finalContractInfo.period;
  const contractTotal = direct?.total ?? finalContractInfo.estimatedTotal;
  const quantityText = direct
    ? `${direct.guests ?? "-"}명 · ${direct.rooms}실 · ${direct.nights}박`
    : "30명 · 15실 · 2박";

  useEffect(() => {
    if (!contractId) return;
    void Promise.all([
      getContractDetail(contractId),
      signatureRequestId ? getSignatureRequest(signatureRequestId) : Promise.resolve(null),
    ])
      .then(([contract, signature]) => {
        setDetail(contract);
        setRequest(signature);
      })
      .catch((error) => toast.error(friendlyApiError(error)));
  }, [contractId, signatureRequestId]);

  useEffect(() => {
    if (contractId || !bothSigned) return;
    updateRequestStatus(directRequestId ?? "req-hotel-main", "completed", {
      currentVersion: isDirect ? "v1" : "v4",
      latestResponse: isDirect
        ? "바이어가 공개 조건에 전자서명하여 계약이 체결되었습니다. 셀러에게 체결 완료 알림을 보냈습니다."
        : "양측 전자서명이 완료되어 계약이 체결되었습니다.",
    });
  }, [bothSigned, contractId, directRequestId, isDirect, updateRequestStatus]);

  if (contractId || versionId) {
    if (!contractId || !versionId) return <PageHeader title="계약을 선택해 주세요" description="서명 요청 화면에서 상태를 확인해 주세요." />;
    if (!detail) return <PageHeader title="계약 상태를 확인 중" description="서명 완료 여부를 서버에서 확인하고 있습니다." />;
    if (detail.status !== "signed") {
      return (
        <div className="mx-auto max-w-[640px] rounded-xl border border-dashed p-12 text-center">
          <Clock className="mx-auto mb-3 size-8" style={{ color: "var(--warning)" }} />
          <p>계약이 아직 체결되지 않았습니다. 모두싸인 상태를 동기화한 뒤 다시 확인해 주세요.</p>
          <Button className="mt-4" onClick={() => navigate(`${base}/signing/sign?contractId=${contractId}&versionId=${versionId}${signatureRequestId ? `&signatureRequestId=${signatureRequestId}` : ""}`)}>전자서명으로</Button>
        </div>
      );
    }
    const documentId = request?.provider_document_id;
    const download = async (kind: "signed" | "audit-trail") => {
      if (!documentId) {
        toast.error("서명 문서 식별자를 아직 불러오지 못했습니다.");
        return;
      }
      try {
        await downloadModusignFile(documentId, kind);
      } catch (error) {
        toast.error(friendlyApiError(error));
      }
    };
    return (
      <div className="mx-auto max-w-[720px]">
        <div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={6} /></div>
        <div className="rounded-xl border p-7 text-center" style={{ borderColor: "var(--success)", background: "var(--success-soft)" }}>
          <CheckCircle2 className="mx-auto size-12" style={{ color: "var(--success)" }} />
          <h1 className="mt-4 text-xl font-bold">계약 체결이 완료되었습니다</h1>
          <p className="mt-2 text-sm">{detail.current_version.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">계약 UUID: {detail.id} · 최종 버전 v{detail.current_version.version_no}</p>
        </div>
        <div className="mt-5 grid gap-2 sm:grid-cols-3">
          <Button disabled={!documentId} variant="outline" onClick={() => void download("signed")}><Download className="mr-1 size-4" />완료 PDF</Button>
          <Button disabled={!documentId} variant="outline" onClick={() => void download("audit-trail")}><History className="mr-1 size-4" />감사이력</Button>
          <Button style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/contracts`)}>계약 목록</Button>
        </div>
      </div>
    );
  }

  const downloadContract = () => {
    const content = [
      "BUSAN LINK 최종 전자계약서",
      "",
      `계약명: ${contractTitle}`,
      `계약번호: ${contractNo}`,
      `바이어: ${finalContractInfo.buyer}`,
      `셀러: ${contractSeller}`,
      `계약기간: ${contractPeriod}`,
      `최종버전: ${isDirect ? "v1" : finalContractInfo.finalVersion}`,
      `체결시각: ${signedAt}`,
      "",
      "핵심 조건",
      `- 요청 조건: ${quantityText}`,
      `- 총 예상금액: ${formatKRW(contractTotal)}`,
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

  if (!bothSigned) {
    return <div className="mx-auto max-w-[640px] rounded-xl border border-dashed p-12 text-center"><Clock className="mx-auto mb-3 size-8" style={{ color: "var(--warning)" }} /><p>모두싸인 이메일에서 서명이 완료된 뒤 계약 체결이 확정됩니다.</p><Button className="mt-4" onClick={() => navigate(`${base}/signing`)}>서명 대기 화면으로</Button></div>;
  }

  return (
    <div className="mx-auto max-w-[720px]">
      <div className="mb-5 rounded-xl border border-border bg-card p-4 sm:mb-6 sm:p-5">
        <ContractStepper current={6} skipped={isDirect ? [3, 4] : []} />
      </div>

      <div className="mb-6 rounded-xl border p-5 text-center sm:p-8" style={{ borderColor: "var(--success)", background: "var(--success-soft)" }}>
        <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full" style={{ background: "var(--success)" }}>
          <CheckCircle2 className="size-9" style={{ color: "#fff" }} />
        </div>
        <h1 className="break-words" style={{ color: "var(--success)" }}>{t("cc.title")}</h1>
        <p className="mt-2 text-foreground" style={{ fontSize: "14px" }}>{t(isDirect ? "cc.directMessage" : "cc.message")}</p>
      </div>

      <div className="mb-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <div className="flex items-start gap-2 break-words" style={{ fontWeight: 700, color: "var(--navy)" }}>
          <Building2 className="mt-0.5 size-4 shrink-0" style={{ color: "var(--ocean)" }} />
          <span>{contractTitle}</span>
        </div>
        <div className="text-muted-foreground" style={{ fontSize: "13px" }}>
          {finalContractInfo.buyer} · {contractSeller}
        </div>

        <Separator className="my-4" />

        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-muted/20 p-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground"><UsersRound className="size-3.5" style={{ color: "var(--ocean)" }} />요청 조건</div>
            <div className="mt-1 text-sm font-bold" style={{ color: "var(--navy)" }}>{quantityText}</div>
          </div>
          <div className="rounded-lg border border-border bg-muted/20 p-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground"><CalendarRange className="size-3.5" style={{ color: "var(--ocean)" }} />이용 기간</div>
            <div className="mt-1 text-sm font-bold" style={{ color: "var(--navy)" }}>{contractPeriod}</div>
          </div>
          <div className="rounded-lg border border-border bg-muted/20 p-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground"><Wallet className="size-3.5" style={{ color: "var(--ocean)" }} />총 예상금액</div>
            <div className="mt-1 text-sm font-bold" style={{ color: "var(--navy)" }}>{formatKRW(contractTotal)}</div>
          </div>
        </div>

        <div className="divide-y divide-border">
          <DetailRow icon={Hash} label={t("cc.contractNo")}><span style={{ color: "var(--navy)", fontFamily: "monospace" }}>{contractNo}</span></DetailRow>
          <DetailRow icon={CalendarRange} label="계약 기간">{contractPeriod}</DetailRow>
          <DetailRow icon={UsersRound} label="입력 조건">{quantityText}</DetailRow>
          <DetailRow icon={Wallet} label="계약 금액">{formatKRW(contractTotal)}</DetailRow>
          <DetailRow icon={FileCheck2} label={t("cc.finalVersion")}><span className="inline-flex"><VersionBadge version={isDirect ? "v1" : finalContractInfo.finalVersion} /></span></DetailRow>
          <DetailRow icon={Clock} label={t("cc.signedAt")}>{signedAt}</DetailRow>
          <DetailRow icon={CheckCircle2} label={t(isDirect ? "cc.signingBasis" : "cc.bothSigned")}>
            <span className="inline-flex max-w-full flex-wrap items-center gap-1.5 rounded-md px-2 py-0.5" style={{ background: "var(--success-soft)", color: "var(--success)", fontSize: "13px" }}>
              <CheckCircle2 className="size-3.5 shrink-0" />
              {isDirect ? t("cc.directSigned") : `${finalContractInfo.buyer} · ${finalContractInfo.seller}`}
            </span>
          </DetailRow>
        </div>
      </div>

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
