import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, FileCheck2, FastForward, PenLine } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import { Checkbox } from "../../components/ui/checkbox";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { FieldError } from "../../components/auth/AuthFields";
import { useApp } from "../../context/AppContext";
import { createContractRequest, friendlyApiError, getMe, getPublicListing, type MeProfile, type PublicListingDetail } from "../../lib/api";
import { formatKRW } from "../../lib/catalog";

function ReadonlyRow({ label, value }: { label: string; value: string }) {
  return <div className="flex items-start justify-between gap-4 border-b border-border py-2.5 last:border-b-0"><span className="text-sm text-muted-foreground">{label}</span><span className="text-right text-sm">{value}</span></div>;
}

export function RequestAsIsPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const [listing, setListing] = useState<PublicListingDetail | null>(null);
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [people, setPeople] = useState("");
  const [quantity, setQuantity] = useState("");
  const [nights, setNights] = useState("");
  const [groupName, setGroupName] = useState("");
  const [message, setMessage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [confirmError, setConfirmError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    let active = true;
    Promise.all([getPublicListing(id), getMe()])
      .then(([nextListing, nextProfile]) => {
        if (!active) return;
        setListing(nextListing);
        setProfile(nextProfile);
        const days = nextListing.availability.start_date && nextListing.availability.end_date
          ? Math.max(1, Math.ceil((new Date(nextListing.availability.end_date).getTime() - new Date(nextListing.availability.start_date).getTime()) / 86_400_000))
          : 1;
        setPeople(String(nextListing.minimum_people ?? 1));
        setQuantity(String(nextListing.minimum_quantity ?? 1));
        setNights(String(days));
      })
      .catch((error) => toast.error(friendlyApiError(error)))
      .finally(() => setLoading(false));
    return () => { active = false; };
  }, [id]);

  const quantityUnit = listing?.quantity_unit ?? "unit";
  const unitPrice = listing?.base_price?.amount_minor ?? 0;
  const total = useMemo(() => (Number(quantity) || 0) * (Number(nights) || 0) * unitPrice, [quantity, nights, unitPrice]);

  if (loading) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">상품 정보를 불러오는 중입니다…</div>;
  if (!listing || !id) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">공고를 찾을 수 없습니다.</div>;

  const submit = async () => {
    if (!confirmed) {
      setConfirmError("asis.needConfirm");
      return;
    }
    if (!listing.availability.start_date || !listing.availability.end_date) {
      toast.error("공고에 이용 기간이 없어 요청할 수 없습니다.");
      return;
    }
    setSubmitting(true);
    try {
      const created = await createContractRequest(listing.id, {
        people: Number(people),
        quantity: Number(quantity),
        quantity_unit: quantityUnit,
        nights: Number(nights),
        start_date: listing.availability.start_date,
        end_date: listing.availability.end_date,
        currency: listing.base_price?.currency ?? "KRW",
        group_name: groupName || undefined,
        signing_capacity: groupName ? "group_representative" : "self",
        request_message: message || undefined,
        initial_request_kind: "as_is",
      });
      toast.success(`계약 요청을 보냈습니다. 서버 상태: ${created.status}`);
      navigate("/buyer/sent");
    } catch (error) {
      toast.error(friendlyApiError(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[760px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5" onClick={() => navigate(`/buyer/explore/${listing.id}/document`)}><ArrowLeft className="size-4" />{t("req.exit")}</Button>
      <PageHeader title={t("asis.title")} description={t("asis.section")} />
      <div className="mb-6 rounded-xl border border-border bg-card p-5"><ContractStepper current={2} /></div>
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-[var(--teal)] bg-[var(--success-soft)] p-4"><FastForward className="mt-0.5 size-5 shrink-0" style={{ color: "var(--teal)" }} /><div><div className="font-semibold" style={{ color: "var(--navy)" }}>{t("asis.directTitle")}</div><p className="mt-1 text-sm text-muted-foreground">서버가 공고의 현재 버전과 기준 단가로 계약 조건을 다시 계산합니다.</p></div></div>
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6"><ReadonlyRow label={t("asis.seller")} value={listing.seller.name} /><ReadonlyRow label={t("asis.contract")} value={listing.title} /><ReadonlyRow label={t("asis.period")} value={`${listing.availability.start_date} ~ ${listing.availability.end_date}`} /><ReadonlyRow label="단가" value={`${listing.base_price?.unit ?? ""} ${formatKRW(unitPrice)}`} /></div>
      <div className="mt-6 grid grid-cols-1 gap-4 rounded-xl border border-border bg-card p-4 sm:grid-cols-2 sm:p-6">
        <div className="space-y-1.5"><Label htmlFor="people">여행 인원</Label><Input id="people" type="number" min={1} value={people} onChange={(event) => setPeople(event.target.value)} /></div>
        <div className="space-y-1.5"><Label htmlFor="quantity">과금 수량 ({quantityUnit})</Label><Input id="quantity" type="number" min={1} value={quantity} onChange={(event) => setQuantity(event.target.value)} /></div>
        <div className="space-y-1.5"><Label htmlFor="nights">이용 박수</Label><Input id="nights" type="number" min={1} value={nights} onChange={(event) => setNights(event.target.value)} /></div>
        <div className="space-y-1.5"><Label htmlFor="groupName">단체명 (선택)</Label><Input id="groupName" value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="단체 대표 서명 시 입력" /></div>
        <div className="space-y-1.5"><Label>예상 금액</Label><div className="flex h-9 items-center rounded-md bg-[var(--info-soft)] px-3 font-bold" style={{ color: "var(--navy)" }}>{formatKRW(total)} <span className="ml-2 text-xs font-normal text-muted-foreground">서버에서 최종 재계산</span></div></div>
      </div>
      <div className="mt-6 rounded-xl border border-border bg-card p-4 sm:p-6"><h3 className="mb-4" style={{ color: "var(--navy)" }}>요청자 정보</h3><div className="grid gap-3 sm:grid-cols-3"><div><Label>담당자</Label><Input value={profile?.display_name ?? ""} readOnly /></div><div><Label>이메일</Label><Input value={profile?.email ?? ""} readOnly /></div><div><Label>전화번호</Label><Input value={profile?.phone ?? ""} readOnly /></div></div><div className="mt-4 space-y-1.5"><Label htmlFor="message">요청 메시지</Label><Textarea id="message" rows={3} value={message} onChange={(event) => setMessage(event.target.value)} /></div></div>
      <div className="mt-6 rounded-xl border border-border bg-card p-4"><label className="flex cursor-pointer items-start gap-2.5"><Checkbox checked={confirmed} onCheckedChange={(value) => { setConfirmed(!!value); setConfirmError(undefined); }} className="mt-0.5" /><span className="flex items-center gap-1.5 text-sm"><FileCheck2 className="size-4" style={{ color: "var(--ocean)" }} />공고의 현재 계약 조건을 확인했고 조건 그대로 요청합니다.</span></label><FieldError message={confirmError} /></div>
      <div className="mt-6 flex justify-end rounded-xl border border-border bg-card p-4"><Button disabled={submitting} className="gap-1.5" style={{ background: "var(--navy)" }} onClick={() => void submit()}><PenLine className="size-4" />서버로 계약 요청 보내기<ArrowRight className="size-4" /></Button></div>
    </div>
  );
}
