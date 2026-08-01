import { useEffect, useState } from "react";
import { CheckCircle2, Download, History, Clock } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { PageHeader } from "../../components/PageHeader";
import { useRoleBase } from "../../hooks/useRoleBase";
import { downloadModusignFile, friendlyApiError, getContractDetail, getSignatureRequest, type ContractDetail, type SignatureRequest } from "../../lib/api";

export function CompletionPage() {
  const navigate = useNavigate(); const [params] = useSearchParams(); const { base } = useRoleBase();
  const contractId = params.get("contractId"); const versionId = params.get("versionId"); const signatureRequestId = params.get("signatureRequestId");
  const [detail, setDetail] = useState<ContractDetail | null>(null); const [request, setRequest] = useState<SignatureRequest | null>(null);
  useEffect(() => { if (!contractId) return; void Promise.all([getContractDetail(contractId), signatureRequestId ? getSignatureRequest(signatureRequestId) : Promise.resolve(null)]).then(([contract, signature]) => { setDetail(contract); setRequest(signature); }).catch((error) => toast.error(friendlyApiError(error))); }, [contractId, signatureRequestId]);
  if (!contractId || !versionId) return <PageHeader title="계약을 선택해 주세요" description="서명 요청 화면에서 상태를 확인해 주세요." />;
  if (!detail) return <PageHeader title="계약 상태를 확인 중" description="서명 완료 여부를 서버에서 확인하고 있습니다." />;
  if (detail.status !== "signed") return <div className="mx-auto max-w-[640px] rounded-xl border border-dashed p-12 text-center"><Clock className="mx-auto mb-3 size-8" style={{ color: "var(--warning)" }} /><p>계약이 아직 체결되지 않았습니다. 모두싸인 상태를 동기화한 뒤 다시 확인해 주세요.</p><Button className="mt-4" onClick={() => navigate(`${base}/signing/sign?contractId=${contractId}&versionId=${versionId}${signatureRequestId ? `&signatureRequestId=${signatureRequestId}` : ""}`)}>전자서명으로</Button></div>;
  const documentId = request?.provider_document_id;
  const download = async (kind: "signed" | "audit-trail") => { if (!documentId) { toast.error("서명 문서 식별자를 아직 불러오지 못했습니다."); return; } try { await downloadModusignFile(documentId, kind); } catch (error) { toast.error(friendlyApiError(error)); } };
  return <div className="mx-auto max-w-[720px]"><div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={6} /></div><div className="rounded-xl border p-7 text-center" style={{ borderColor: "var(--success)", background: "var(--success-soft)" }}><CheckCircle2 className="mx-auto size-12" style={{ color: "var(--success)" }} /><h1 className="mt-4 text-xl font-bold">계약 체결이 완료되었습니다</h1><p className="mt-2 text-sm">{detail.current_version.title}</p><p className="mt-1 text-xs text-muted-foreground">계약 UUID: {detail.id} · 최종 버전 v{detail.current_version.version_no}</p></div><div className="mt-5 grid gap-2 sm:grid-cols-3"><Button disabled={!documentId} variant="outline" onClick={() => void download("signed")}><Download className="mr-1 size-4" />완료 PDF</Button><Button disabled={!documentId} variant="outline" onClick={() => void download("audit-trail")}><History className="mr-1 size-4" />감사이력</Button><Button style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/contracts`)}>계약 목록</Button></div></div>;
}
