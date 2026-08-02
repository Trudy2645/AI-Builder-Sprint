import { useEffect, useState } from "react";
import { CalendarRange, CheckCircle2, Clock, Download, FileCheck2, FileSearch, History, ListChecks, UsersRound, Wallet } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { PageHeader } from "../../components/PageHeader";
import { VersionBadge } from "../../components/contract/VersionBadge";
import { Separator } from "../../components/ui/separator";
import { useRoleBase } from "../../hooks/useRoleBase";
import { downloadModusignFile, friendlyApiError, getContractDetail, getSignatureRequest, type ContractDetail, type SignatureRequest } from "../../lib/api";
import { formatKRW } from "../../lib/catalog";

export function CompletionPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { base, role } = useRoleBase();
  const contractId = params.get("contractId");
  const versionId = params.get("versionId");
  const signatureRequestId = params.get("signatureRequestId");
  const [detail, setDetail] = useState<ContractDetail | null>(null);
  const [request, setRequest] = useState<SignatureRequest | null>(null);
  useEffect(() => { if (!contractId) return; void Promise.all([getContractDetail(contractId), signatureRequestId ? getSignatureRequest(signatureRequestId) : Promise.resolve(null)]).then(([nextDetail, nextRequest]) => { setDetail(nextDetail); setRequest(nextRequest); }).catch((error) => toast.error(friendlyApiError(error))); }, [contractId, signatureRequestId]);
  if (!contractId || !versionId) return <PageHeader title="계약을 선택해 주세요" description="서명 요청 화면에서 체결 상태를 확인해 주세요." />;
  if (!detail) return <PageHeader title="계약 상태를 확인 중" description="서버에서 서명 완료 여부를 확인하고 있습니다." />;
  if (detail.status !== "signed") return <div className="mx-auto max-w-[640px] rounded-xl border border-dashed p-12 text-center"><Clock className="mx-auto mb-3 size-8 text-[var(--warning)]" /><p>계약이 아직 체결되지 않았습니다. 모두싸인 상태를 동기화한 뒤 다시 확인해 주세요.</p><Button className="mt-4" onClick={() => navigate(`${base}/signing/sign?contractId=${contractId}&versionId=${versionId}${signatureRequestId ? `&signatureRequestId=${signatureRequestId}` : ""}`)}>전자서명으로</Button></div>;
  const buyer = detail.parties.find((party) => party.role === "buyer")?.name ?? "바이어";
  const seller = detail.parties.find((party) => party.role === "seller")?.name ?? "셀러";
  const documentId = request?.provider_document_id;
  const download = async (kind: "signed" | "audit-trail") => { if (!documentId) { toast.error("서명 문서 식별자를 아직 불러오지 못했습니다."); return; } try { await downloadModusignFile(documentId, kind); } catch (error) { toast.error(friendlyApiError(error)); } };
  const amount = detail.terms.amount_minor ?? 0;
  return <div className="mx-auto max-w-[720px]"><div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={6} /></div><div className="rounded-xl border border-[var(--success)] bg-[var(--success-soft)] p-7 text-center"><CheckCircle2 className="mx-auto size-12 text-[var(--success)]" /><h1 className="mt-4 text-xl font-bold">계약 체결이 완료되었습니다</h1><p className="mt-2 text-sm">{detail.current_version.title}</p><p className="mt-1 text-xs text-muted-foreground">계약 UUID: {detail.id} · 최종 버전 v{detail.current_version.version_no}</p></div><div className="mt-5 grid gap-2 sm:grid-cols-3"><Button disabled={!documentId} variant="outline" onClick={() => void download("signed")}><Download className="mr-1 size-4" />완료 PDF</Button><Button disabled={!documentId} variant="outline" onClick={() => void download("audit-trail")}><History className="mr-1 size-4" />감사이력</Button><Button style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/contracts`)}>계약 목록</Button></div><div className="mt-5 rounded-xl border border-border bg-card p-5"><div className="font-semibold" style={{ color: "var(--navy)" }}>{detail.current_version.title}</div><div className="mt-1 text-sm text-muted-foreground">{buyer} · {seller}</div><Separator className="my-4" /><div className="divide-y divide-border"><div className="flex items-center justify-between py-3 text-sm"><span className="flex items-center gap-2 text-muted-foreground"><CalendarRange className="size-4" />계약 기간</span><span>{detail.terms.start_date} ~ {detail.terms.end_date}</span></div><div className="flex items-center justify-between py-3 text-sm"><span className="flex items-center gap-2 text-muted-foreground"><UsersRound className="size-4" />요청 인원/수량</span><span>{detail.terms.people}명 · {detail.terms.quantity}{detail.terms.quantity_unit}</span></div><div className="flex items-center justify-between py-3 text-sm"><span className="flex items-center gap-2 text-muted-foreground"><Wallet className="size-4" />계약 금액</span><span>{formatKRW(amount)}</span></div><div className="flex items-center justify-between py-3 text-sm"><span className="flex items-center gap-2 text-muted-foreground"><FileCheck2 className="size-4" />최종 버전</span><VersionBadge version={`v${Math.min(4, detail.current_version.version_no)}` as "v1" | "v2" | "v3" | "v4"} /></div></div></div><div className="mt-4 flex gap-2"><Button variant="outline" className="flex-1" onClick={() => navigate(role === "buyer" ? `/buyer/explore/${detail.listing_id ?? ""}` : `${base}/contracts`)}><FileSearch className="mr-1 size-4" />상세 보기</Button><Button variant="outline" className="flex-1" onClick={() => navigate(`${base}/contracts`)}><ListChecks className="mr-1 size-4" />목록으로</Button></div></div>;
}
