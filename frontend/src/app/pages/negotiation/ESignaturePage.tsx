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
  if (!contractId || !versionId) return <div className="mx-auto max-w-[820px]"><PageHeader title="전자서명 계약을 확인할 수 없습니다" description="실제 계약 상태 화면에서 전자서명을 시작해 주세요." /><div className="rounded-xl border border-dashed p-8 text-center"><p className="text-sm text-muted-foreground">모두싸인 메일에서 서명하기 전에는 계약을 체결 완료로 처리할 수 없습니다.</p><Button className="mt-5" style={{ background: "var(--navy)" }} onClick={() => navigate(`${base}/contracts`)}>내 계약 목록으로</Button></div></div>;
  if (!detail) return <PageHeader title="계약을 불러오는 중" description="전자서명에 필요한 계약 정보를 확인하고 있습니다." />;
  const buyer = detail.parties.find((party) => party.role === "buyer"); const seller = detail.parties.find((party) => party.role === "seller");
  return <div className="mx-auto max-w-[820px]"><Button variant="ghost" onClick={() => navigate(`${base}/signing?contractId=${contractId}&versionId=${versionId}`)}><ArrowLeft className="mr-1 size-4" />최종 검토</Button><PageHeader title="전자서명" description="양측 승인 후 모두싸인 서명 요청과 진행 상태를 관리합니다." /><div className="mb-5 rounded-xl border border-border bg-card p-4"><ContractStepper current={5} /></div><div className="mb-6 rounded-xl border border-border bg-card p-5"><h2 className="font-semibold">{detail.current_version.title}</h2><p className="mt-1 text-sm text-muted-foreground">계약 UUID: {contractId} · 버전 v{detail.current_version.version_no}</p><div className="mt-4 grid gap-3 md:grid-cols-2"><div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">바이어</p><p>{buyer?.name}</p></div><div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">셀러</p><p>{seller?.name}</p></div></div></div>{request ? <div className="rounded-xl border border-border bg-card p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold">현재 모두싸인 서명 대기 중</h2><p className="mt-1 text-sm text-muted-foreground">메일 발송 상태: {request.provider_status ?? request.status}</p></div><Clock className="size-7" style={{ color: "var(--warning)" }} /></div><p className="mt-3 rounded-lg bg-muted p-3 text-sm">바이어 이메일의 모두싸인 링크에서 서명하면 자동으로 상태가 갱신됩니다.</p><p className="mt-4 flex gap-1 text-xs text-muted-foreground"><ShieldCheck className="size-3.5" />서명 대기 화면에서는 별도 확정 버튼을 제공하지 않습니다.</p></div> : <PageHeader title="서명 요청을 준비 중입니다" description="최종 확정 직후 서버가 모두싸인 이메일을 발송합니다." />}</div>;
}
