import { useEffect, useMemo, useState, type ChangeEvent, type ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileClock,
  FileText,
  History,
  Loader2,
  PenLine,
  Send,
  UploadCloud,
} from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import {
  DEFAULT_BUYER_CONTRACT_DRAFT,
  useBuyerContracts,
  type BuyerContract,
  type BuyerContractDraft,
  type BuyerContractStatus,
} from "../../store/BuyerContractsContext";
import { formatKRW } from "../../data/contracts";
import { friendlyApiError, getBuyerRevisionRequests, getContractDetail, getRevisionRequest, type BuyerRevisionSummary, type ContractDetail, type RevisionDetail, markRevisionRequestRead } from "../../lib/api";

const STATUS_META: Record<BuyerContractStatus, { label: string; tone: string; desc: string }> = {
  draft: { label: "작성 중", tone: "var(--muted-foreground)", desc: "계약 조건을 정리하고 있습니다." },
  seller_review: {
    label: "셀러 검토 중",
    tone: "var(--ocean)",
    desc: "셀러가 요청 조건과 계약서를 확인하고 있습니다.",
  },
  revision_requested: {
    label: "수정 요청",
    tone: "var(--warning)",
    desc: "셀러가 일부 조항 수정을 요청했습니다.",
  },
  signing: {
    label: "전자서명 진행 중",
    tone: "var(--teal)",
    desc: "모두싸인 문서가 발송된 상태입니다.",
  },
  signed: {
    label: "양측 서명 완료",
    tone: "var(--success)",
    desc: "계약 체결이 완료되었습니다.",
  },
  cancelled: { label: "취소됨", tone: "var(--destructive)", desc: "계약 요청이 취소되었습니다." },
};

const OCR_MOCK: BuyerContractDraft = {
  ...DEFAULT_BUYER_CONTRACT_DRAFT,
  title: "해운대 오션스테이 단체 객실 공급",
  cancellationPolicy: "체크인 7일 전까지 무료 취소, 이후 1박 요금의 50% 부과",
  settlementPolicy: "월 마감 후 익월 15일 이내 계좌이체",
};

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function ContractForm({
  draft,
  onChange,
  onSubmit,
  submitLabel = "계약 요청 보내기",
}: {
  draft: BuyerContractDraft;
  onChange: (patch: Partial<BuyerContractDraft>) => void;
  onSubmit: () => void;
  submitLabel?: string;
}) {
  const changeText =
    (key: keyof BuyerContractDraft) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange({ [key]: event.target.value } as Partial<BuyerContractDraft>);
  const changeNumber =
    (key: keyof BuyerContractDraft) => (event: ChangeEvent<HTMLInputElement>) =>
      onChange({ [key]: Number(event.target.value) || 0 } as Partial<BuyerContractDraft>);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="계약명">
          <Input value={draft.title} onChange={changeText("title")} />
        </Field>
        <Field label="상품 유형">
          <Input value={draft.category} onChange={changeText("category")} />
        </Field>
        <Field label="바이어명">
          <Input value={draft.buyerName} onChange={changeText("buyerName")} />
        </Field>
        <Field label="셀러명">
          <Input value={draft.sellerName} onChange={changeText("sellerName")} />
        </Field>
        <Field label="계약 시작일">
          <Input type="date" value={draft.startDate} onChange={changeText("startDate")} />
        </Field>
        <Field label="계약 종료일">
          <Input type="date" value={draft.endDate} onChange={changeText("endDate")} />
        </Field>
        <Field label="인원">
          <Input type="number" min={0} value={draft.peopleCount} onChange={changeNumber("peopleCount")} />
        </Field>
        <Field label="수량">
          <Input type="number" min={0} value={draft.quantity} onChange={changeNumber("quantity")} />
        </Field>
        <Field label="단가">
          <Input type="number" min={0} value={draft.unitPrice} onChange={changeNumber("unitPrice")} />
        </Field>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="취소 정책">
          <Textarea value={draft.cancellationPolicy} onChange={changeText("cancellationPolicy")} />
        </Field>
        <Field label="정산 정책">
          <Textarea value={draft.settlementPolicy} onChange={changeText("settlementPolicy")} />
        </Field>
      </div>
      <div className="flex flex-col gap-2 rounded-xl border border-border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-semibold" style={{ color: "var(--navy)" }}>
            예상 계약 금액 {formatKRW(draft.quantity * draft.unitPrice)}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">mock 계약 요청 데이터가 생성되고 셀러 검토 상태로 전환됩니다.</p>
        </div>
        <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={onSubmit}>
          <Send className="size-4" />
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}

function ContractSummary({ contract }: { contract: BuyerContract }) {
  const meta = STATUS_META[contract.status];
  return (
    <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="text-sm text-muted-foreground">{contract.id}</div>
          <h3 className="mt-1 break-words text-lg" style={{ color: "var(--navy)" }}>
            {contract.title}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {contract.buyerName} · {contract.sellerName}
          </p>
        </div>
        <span
          className="inline-flex w-fit items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold"
          style={{ borderColor: meta.tone, color: meta.tone }}
        >
          <FileClock className="size-4" />
          {meta.label}
        </span>
      </div>
      <div className="mt-4 grid gap-3 text-sm md:grid-cols-4">
        <div>
          <div className="text-muted-foreground">기간</div>
          <div className="mt-1">{contract.startDate} ~ {contract.endDate}</div>
        </div>
        <div>
          <div className="text-muted-foreground">인원/수량</div>
          <div className="mt-1">{contract.peopleCount}명 · {contract.quantity}개</div>
        </div>
        <div>
          <div className="text-muted-foreground">단가</div>
          <div className="mt-1">{formatKRW(contract.unitPrice)}</div>
        </div>
        <div>
          <div className="text-muted-foreground">총액</div>
          <div className="mt-1 font-semibold">{formatKRW(contract.unitPrice * contract.quantity)}</div>
        </div>
      </div>
    </div>
  );
}

function useContractFromRoute() {
  const { id } = useParams();
  const { contracts } = useBuyerContracts();
  return useMemo(() => contracts.find((contract) => contract.id === id) ?? contracts[0], [contracts, id]);
}

export function BuyerContractsHomePage() {
  const navigate = useNavigate();
  const { contracts } = useBuyerContracts();
  const [revisions, setRevisions] = useState<BuyerRevisionSummary[]>([]);
  useEffect(() => { void getBuyerRevisionRequests().then(setRevisions).catch(() => setRevisions([])); }, []);

  return (
    <div>
      <PageHeader
        title="바이어 계약"
        description="계약서를 업로드하거나 직접 조건을 입력해 셀러에게 계약 요청을 보낼 수 있습니다."
      />
      <div className="grid gap-4 md:grid-cols-2">
        <button
          type="button"
          className="rounded-xl border border-border bg-card p-5 text-left transition-colors hover:border-[var(--ocean)]"
          onClick={() => navigate("/buyer/contracts/upload")}
        >
          <div className="flex size-12 items-center justify-center rounded-xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
            <UploadCloud className="size-6" />
          </div>
          <h3 className="mt-4 text-lg" style={{ color: "var(--navy)" }}>계약서 PDF 업로드</h3>
          <p className="mt-1 text-sm text-muted-foreground">기존 계약서를 올리고 OCR 결과를 확인한 뒤 계약 요청을 보냅니다.</p>
        </button>
        <button
          type="button"
          className="rounded-xl border border-border bg-card p-5 text-left transition-colors hover:border-[var(--teal)]"
          onClick={() => navigate("/buyer/contracts/write")}
        >
          <div className="flex size-12 items-center justify-center rounded-xl" style={{ background: "var(--success-soft)", color: "var(--teal)" }}>
            <PenLine className="size-6" />
          </div>
          <h3 className="mt-4 text-lg" style={{ color: "var(--navy)" }}>계약 조건 직접 작성</h3>
          <p className="mt-1 text-sm text-muted-foreground">PDF가 없을 때 필요한 조건을 입력해서 새 계약 요청을 만듭니다.</p>
        </button>
      </div>

      <div className="mt-6 space-y-3">
        <h2 className="text-base" style={{ color: "var(--navy)" }}>최근 계약 요청</h2>
        {contracts.map((contract) => (
          <button
            type="button"
            key={contract.id}
            className="block w-full text-left"
            onClick={() => navigate(`/buyer/contracts/${contract.id}/status`)}
          >
            <ContractSummary contract={contract} />
          </button>
        ))}
      </div>
      {revisions.length > 0 && (
        <div className="mt-8 space-y-3">
          <h2 className="text-base" style={{ color: "var(--navy)" }}>내 수정 요청 내역</h2>
          {revisions.map((revision) => (
            <button
              type="button"
              key={revision.id}
              className="block w-full rounded-xl border border-border bg-card p-4 text-left hover:border-[var(--ocean)]"
              onClick={() => { void markRevisionRequestRead(revision.id); navigate(`/buyer/contracts/${revision.contract_id}/status?revision=${revision.id}`); }}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-semibold" style={{ color: "var(--navy)" }}>{revision.listing_title}</span>
                <span className="text-xs" style={{ color: revision.has_unread ? "var(--coral)" : "var(--muted-foreground)" }}>{revision.has_unread ? "셀러 답변 안 읽음" : "확인함"}</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{revision.item_count}개 조항 수정 요청 · {revision.item_summary.join(" · ")}</p>
              <p className="mt-2 text-xs text-muted-foreground">상태: {revision.status}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function BuyerContractUploadPage() {
  const navigate = useNavigate();
  const { createContractRequest } = useBuyerContracts();
  const [fileName, setFileName] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [draft, setDraft] = useState<BuyerContractDraft | null>(null);

  const runOcr = () => {
    if (!fileName) {
      toast.error("PDF 파일을 먼저 선택해주세요.");
      return;
    }
    setAnalyzing(true);
    setTimeout(() => {
      setDraft(OCR_MOCK);
      setAnalyzing(false);
      toast.success("OCR 결과를 불러왔습니다.");
    }, 1000);
  };

  const submit = () => {
    if (!draft) return;
    const contract = createContractRequest(draft, "upload");
    toast.success("계약 요청을 셀러에게 보냈습니다.");
    navigate(`/buyer/contracts/${contract.id}/status`);
  };

  return (
    <div className="mx-auto max-w-[960px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate("/buyer/contracts")}>
        <ArrowLeft className="size-4" />
        바이어 계약
      </Button>
      <PageHeader title="계약서 업로드" description="기존 PDF 계약서를 올리면 mock OCR 결과로 계약 요청 정보를 채웁니다." />
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          <div className="flex size-16 items-center justify-center rounded-2xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
            <UploadCloud className="size-8" />
          </div>
          <div>
            <h3 style={{ color: "var(--navy)" }}>PDF 계약서를 선택해주세요</h3>
            <p className="mt-1 text-sm text-muted-foreground">Upstage 연동 전까지는 데모 OCR 데이터가 채워집니다.</p>
          </div>
          {fileName && (
            <div className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm">
              <FileText className="size-4" style={{ color: "var(--ocean)" }} />
              {fileName}
            </div>
          )}
          <div className="flex flex-wrap justify-center gap-2">
            <label htmlFor="buyer-contract-file">
              <input
                id="buyer-contract-file"
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(event) => setFileName(event.target.files?.[0]?.name ?? "buyer_contract.pdf")}
              />
              <span className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-border bg-card px-4 py-2 text-sm">
                <UploadCloud className="size-4" />
                파일 선택
              </span>
            </label>
            <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--ocean)" }} onClick={runOcr} disabled={analyzing}>
              {analyzing ? <Loader2 className="size-4 animate-spin" /> : <ClipboardCheck className="size-4" />}
              OCR 결과 확인
            </Button>
          </div>
        </div>
      </div>

      {draft && (
        <div className="mt-5 rounded-xl border border-border bg-card p-5">
          <h3 className="mb-4" style={{ color: "var(--navy)" }}>OCR 추출 결과 확인</h3>
          <ContractForm draft={draft} onChange={(patch) => setDraft((prev) => ({ ...(prev ?? OCR_MOCK), ...patch }))} onSubmit={submit} />
        </div>
      )}
    </div>
  );
}

export function BuyerContractWritePage() {
  const navigate = useNavigate();
  const { createContractRequest } = useBuyerContracts();
  const [draft, setDraft] = useState<BuyerContractDraft>(DEFAULT_BUYER_CONTRACT_DRAFT);

  const submit = () => {
    const required = [draft.title, draft.buyerName, draft.sellerName, draft.startDate, draft.endDate];
    if (required.some((value) => !String(value).trim())) {
      toast.error("계약명, 바이어명, 셀러명, 기간을 입력해주세요.");
      return;
    }
    const contract = createContractRequest(draft, "write");
    toast.success("계약 요청을 셀러에게 보냈습니다.");
    navigate(`/buyer/contracts/${contract.id}/status`);
  };

  return (
    <div className="mx-auto max-w-[960px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate("/buyer/contracts")}>
        <ArrowLeft className="size-4" />
        바이어 계약
      </Button>
      <PageHeader title="바이어 계약 작성" description="PDF가 없을 때 조건을 입력해서 셀러에게 계약 요청을 보냅니다." />
      <div className="rounded-xl border border-border bg-card p-5">
        <ContractForm draft={draft} onChange={(patch) => setDraft((prev) => ({ ...prev, ...patch }))} onSubmit={submit} />
      </div>
    </div>
  );
}

export function BuyerContractStatusPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const contract = useContractFromRoute();
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [revision, setRevision] = useState<RevisionDetail | null>(null);
  const revisionId = searchParams.get("revision");

  useEffect(() => {
    if (!contract?.id || contract.id.startsWith("BL-")) return;
    getContractDetail(contract.id).then(setDetail).catch((error) => toast.error(friendlyApiError(error)));
  }, [contract?.id]);
  useEffect(() => {
    if (!revisionId) return;
    void getRevisionRequest(revisionId).then((value) => { setRevision(value); void markRevisionRequestRead(revisionId); }).catch((error) => toast.error(friendlyApiError(error)));
  }, [revisionId]);

  if (!contract) {
    return <PageHeader title="계약 요청이 없습니다" description="먼저 계약 요청을 생성해주세요." />;
  }

  const status = (detail?.status as BuyerContractStatus | undefined) ?? contract.status;
  const meta = STATUS_META[status];
  const steps: BuyerContractStatus[] = ["seller_review", "signing", "signed"];
  const currentIndex = steps.indexOf(status) === -1 ? 0 : steps.indexOf(status);

  useEffect(() => {
    if (detail?.status === "signed") navigate(`/buyer/signing/complete?contractId=${detail.id}&versionId=${detail.current_version.id}`);
  }, [detail, navigate]);

  return (
    <div>
      <PageHeader title="계약 상태" description="계약 요청 이후 셀러 검토, 전자서명, 체결 완료까지 상태를 확인합니다." />
      <ContractSummary contract={contract} />
      {revision && (
        <div className="mt-5 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 style={{ color: "var(--navy)" }}>내가 보낸 수정 요청</h3>
            <span className="text-xs text-muted-foreground">{revision.status === "sent" ? "셀러 검토 중" : revision.status}</span>
          </div>
          {revision.message && <p className="mt-2 text-sm text-muted-foreground">{revision.message}</p>}
          <div className="mt-4 space-y-3">
            {revision.items.map((item) => (
              <div key={item.id} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2 text-sm font-medium"><span>{item.request_type === "modify" ? "문구 수정" : item.request_type === "delete" ? "조항 삭제" : "조항 추가"}</span><span className="text-xs text-muted-foreground">{item.decision === "pending" ? "답변 대기" : item.decision === "accepted" ? "수락" : item.decision === "rejected" ? "거절" : "대안 제시"}</span></div>
                <p className="mt-1 text-sm">{item.requested_text ?? item.reason}</p>
                {item.seller_reason && <p className="mt-2 text-xs text-muted-foreground">셀러 답변 사유: {item.seller_reason}</p>}
                {item.counter_text && <p className="mt-2 rounded bg-muted p-2 text-sm">셀러 대안: {item.counter_text}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="mt-5 rounded-xl border border-border bg-card p-5">
        <div className="flex items-start gap-3">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-xl" style={{ background: "var(--info-soft)", color: meta.tone }}>
            <FileClock className="size-5" />
          </div>
          <div>
            <h3 style={{ color: "var(--navy)" }}>{meta.label}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{meta.desc}</p>
          </div>
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {steps.map((status, index) => {
            const done = index <= currentIndex;
            return (
              <div key={status} className="rounded-lg border p-4" style={{ borderColor: done ? STATUS_META[status].tone : "var(--border)" }}>
                <div className="flex items-center gap-2 font-semibold" style={{ color: done ? STATUS_META[status].tone : "var(--muted-foreground)" }}>
                  <CheckCircle2 className="size-4" />
                  {STATUS_META[status].label}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{STATUS_META[status].desc}</p>
              </div>
            );
          })}
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          {detail && status !== "signed" && (
            <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate(`/buyer/signing?contractId=${detail.id}&versionId=${detail.current_version.id}`)}>
              계약 상세·최종 검토
              <ArrowRight className="size-4" />
            </Button>
          )}
          <Button variant="outline" className="gap-1.5 whitespace-nowrap" onClick={() => navigate("/buyer/contracts")}>
            내 계약 목록으로
          </Button>
        </div>
      </div>
    </div>
  );
}

export function BuyerContractCompletePage() {
  const navigate = useNavigate();
  const contract = useContractFromRoute();

  if (!contract) {
    return <PageHeader title="계약 요청이 없습니다" description="먼저 계약 요청을 생성해주세요." />;
  }

  return <div className="mx-auto max-w-[700px] rounded-xl border border-border bg-card p-8 text-center"><h1 className="text-xl font-semibold">서버 계약 상태를 확인해 주세요</h1><p className="mt-2 text-sm text-muted-foreground">완료 PDF와 감사이력은 실제 서명 요청이 완료되고 계약 상태가 signed인 경우에만 표시됩니다.</p><Button className="mt-5" style={{ background: "var(--navy)" }} onClick={() => navigate(`/buyer/contracts/${contract.id}/status`)}>계약 상태로</Button></div>;
}
