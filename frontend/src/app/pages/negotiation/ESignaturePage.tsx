import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, Clock, PenLine, ShieldCheck } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { useRoleBase } from "../../hooks/useRoleBase";
import { createSignatureRequest, friendlyApiError, getContractDetail, getSignatureRequest, syncSignatureRequest, type ContractDetail, type SignatureRequest } from "../../lib/api";

export function ESignaturePage() {
  const navigate = useNavigate(); const [params] = useSearchParams(); const { base } = useRoleBase();
  const contractId = params.get("contractId"); const versionId = params.get("versionId");
  const [detail, setDetail] = useState<ContractDetail | null>(null); const [request, setRequest] = useState<SignatureRequest | null>(null);
  const [buyerEmail, setBuyerEmail] = useState(""); const [sellerEmail, setSellerEmail] = useState(""); const [busy, setBusy] = useState(false);
  const loadContract = async () => { if (!contractId) return; try { setDetail(await getContractDetail(contractId)); } catch (error) { toast.error(friendlyApiError(error)); } };
  useEffect(() => { void loadContract(); }, [contractId]);
  useEffect(() => { const id = params.get("signatureRequestId"); if (id) void getSignatureRequest(id).then(setRequest).catch((error) => toast.error(friendlyApiError(error))); }, [params]);
  const query = request ? `?contractId=${contractId}&versionId=${versionId}&signatureRequestId=${request.id}` : `?contractId=${contractId}&versionId=${versionId}`;
  const create = async () => {
    if (!contractId || !versionId || !detail) return;
    if (!buyerEmail || !sellerEmail) { toast.error("바이어와 셀러의 서명 수신 이메일을 입력해 주세요."); return; }
    setBusy(true); try {
      const buyer = detail.parties.find((party) => party.role === "buyer"); const seller = detail.parties.find((party) => party.role === "seller");
      const created = await createSignatureRequest(contractId, versionId, { title: detail.current_version.title, buyer: { name: buyer?.name ?? "Buyer", email: buyerEmail }, seller: { name: seller?.name ?? "Seller", email: sellerEmail } });
      setRequest(created); toast.success("모두싸인 서명 요청을 생성했습니다."); navigate(`${base}/signing/sign?contractId=${contractId}&versionId=${versionId}&signatureRequestId=${created.id}`, { replace: true });
    } catch (error) { toast.error(friendlyApiError(error)); } finally { setBusy(false); }
  };
  const sync = async () => { if (!request) return; setBusy(true); try { const next = await syncSignatureRequest(request.id); setRequest(next); const contract = await getContractDetail(next.contract_id); setDetail(contract); if (next.status === "completed" && contract.status === "signed") navigate(`${base}/signing/complete?contractId=${contract.id}&versionId=${next.contract_version_id}&signatureRequestId=${next.id}`); else toast.info("서명 상태를 갱신했습니다."); } catch (error) { toast.error(friendlyApiError(error)); } finally { setBusy(false); } };
  if (!contractId || !versionId) return <PageHeader title="계약을 선택해 주세요" description="최종 승인 화면에서 전자서명을 시작해 주세요." />;
  if (!detail) return <PageHeader title="계약을 불러오는 중" description="전자서명에 필요한 계약 정보를 확인하고 있습니다." />;
  const buyer = detail.parties.find((party) => party.role === "buyer"); const seller = detail.parties.find((party) => party.role === "seller");
  return <div><Button variant="ghost" onClick={() => navigate(`${base}/signing?contractId=${contractId}&versionId=${versionId}`)}><ArrowLeft className="mr-1 size-4" />최종 검토</Button><PageHeader title="전자서명" description="양측 승인 후 모두싸인 서명 요청과 진행 상태를 관리합니다." /><div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={5} /></div><div className="mb-6 rounded-xl border border-border bg-card p-5"><h2 className="font-semibold">{detail.current_version.title}</h2><p className="mt-1 text-sm text-muted-foreground">계약 UUID: {contractId}</p><div className="mt-4 grid gap-3 md:grid-cols-2"><div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">바이어</p><p>{buyer?.name}</p></div><div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">셀러</p><p>{seller?.name}</p></div></div></div>{!request ? <div className="rounded-xl border border-border bg-card p-5"><h2 className="font-semibold">서명 수신자</h2><p className="mt-1 text-sm text-muted-foreground">서명 요청 API는 계약별 수신자 정보를 명시적으로 요구합니다.</p><div className="mt-4 grid gap-3 md:grid-cols-2"><Input type="email" value={buyerEmail} onChange={(event) => setBuyerEmail(event.target.value)} placeholder="바이어 이메일" /><Input type="email" value={sellerEmail} onChange={(event) => setSellerEmail(event.target.value)} placeholder="셀러 이메일" /></div><Button className="mt-4" disabled={busy} style={{ background: "var(--navy)" }} onClick={() => void create()}><PenLine className="mr-1 size-4" />모두싸인 요청 생성</Button></div> : <div className="rounded-xl border border-border bg-card p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold">서명 요청 상태</h2><p className="mt-1 text-sm text-muted-foreground">{request.provider_status ?? request.status}</p></div>{request.status === "completed" ? <CheckCircle2 className="size-7" style={{ color: "var(--success)" }} /> : <Clock className="size-7" style={{ color: "var(--warning)" }} />}</div><Button className="mt-4" disabled={busy} variant="outline" onClick={() => void sync()}>상태 동기화</Button><p className="mt-4 flex gap-1 text-xs text-muted-foreground"><ShieldCheck className="size-3.5" />완료 화면은 서버 계약 상태가 signed일 때만 표시됩니다.</p></div>}</div>;
}
