import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, PenLine, FileCheck2, FastForward } from "lucide-react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import { Checkbox } from "../../components/ui/checkbox";
import { ContractStepper } from "../../components/contract/ContractStepper";
import { useApp } from "../../context/AppContext";
import { getContract, formatKRW, type Contract } from "../../data/contracts";
import { createPublicContractRequest, friendlyApiError, getPublicListingAsContract } from "../../lib/api";
import { buyerProfile } from "../../data/profile";
import { FieldError } from "../../components/auth/AuthFields";

function ReadonlyRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border py-2.5 last:border-b-0">
      <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "13px" }}>{label}</span>
      <span className="text-right" style={{ fontSize: "14px" }}>{value}</span>
    </div>
  );
}

export function RequestAsIsPage() {
  const { t } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialFrom = searchParams.get("from") ?? "";
  const initialTo = searchParams.get("to") ?? "";
  const [serverContract, setServerContract] = useState<Contract | null>(null);
  const [loading, setLoading] = useState(!getContract(id));
  const demoContract = getContract(id);
  useEffect(() => {
    if (demoContract || !id) return;
    void getPublicListingAsContract(id).then(setServerContract).catch((error: unknown) => toast.error(friendlyApiError(error))).finally(() => setLoading(false));
  }, [demoContract, id]);
  const contract = demoContract ?? serverContract;
  const [guests, setGuests] = useState("1");
  const [rooms, setRooms] = useState("1");
  const [nights, setNights] = useState("1");
  const [startDate, setStartDate] = useState(initialFrom || (contract?.start !== "미정" ? contract?.start ?? "" : ""));
  const [endDate, setEndDate] = useState(initialTo || (contract?.end !== "미정" ? contract?.end ?? "" : ""));
  const currency = "KRW";
  const [name, setName] = useState(buyerProfile.contactName);
  const [email, setEmail] = useState(buyerProfile.email);
  const [phone, setPhone] = useState(buyerProfile.phone);
  const [message, setMessage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [confirmError, setConfirmError] = useState<string | undefined>();

  useEffect(() => {
    if (!contract) return;
    if (!initialFrom && contract.start !== "미정") setStartDate(contract.start);
    if (!initialTo && contract.end !== "미정") setEndDate(contract.end);
  }, [contract, initialFrom, initialTo]);

  useEffect(() => {
    if (!startDate || !endDate) return;
    const days = Math.round((Date.parse(`${endDate}T00:00:00`) - Date.parse(`${startDate}T00:00:00`)) / 86_400_000);
    if (days > 0) setNights(String(days));
  }, [startDate, endDate]);

  if (!contract) {
    return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{loading ? "계약 조건을 불러오는 중입니다…" : "공고를 찾을 수 없습니다."}</div>;
  }

  const roomsNum = parseInt(rooms, 10) || 0;
  const nightsNum = parseInt(nights, 10) || 1;
  const total = contract.unitPrice * roomsNum * nightsNum;
  const quantityUnit = contract.quantityUnit ?? (contract.category === "accommodation" ? "room" : contract.category === "vehicle_rental" ? "vehicle" : "person");

  const submit = async () => {
    if (!confirmed) {
      setConfirmError("asis.needConfirm");
      return;
    }
    if (!startDate || !endDate || endDate <= startDate) {
      toast.error("이용 시작일과 종료일을 올바르게 입력해 주세요.");
      return;
    }
    const requiredNights = Math.round((Date.parse(`${endDate}T00:00:00`) - Date.parse(`${startDate}T00:00:00`)) / 86_400_000);
    if (nightsNum !== requiredNights) {
      toast.error(`숙박 일수(${nightsNum}박)가 이용 기간(${requiredNights}박)과 다릅니다. 날짜 또는 숙박 일수를 맞춰 주세요.`);
      return;
    }
    try {
      const created = await createPublicContractRequest(contract.id, {
        people: parseInt(guests, 10) || 1, quantity: roomsNum, quantity_unit: quantityUnit,
        nights: nightsNum, start_date: startDate, end_date: endDate, currency,
        request_message: message, initial_request_kind: "as_is",
      });
      toast.success("계약 요청이 서버에 저장되었습니다. 셀러 검토가 끝난 뒤 전자서명을 진행할 수 있습니다.");
      navigate(`/buyer/contracts/${created.contract_id}/status`);
    } catch (error) { toast.error(friendlyApiError(error)); }
  };

  return (
    <div className="mx-auto max-w-[760px]">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 whitespace-nowrap" onClick={() => navigate(`/buyer/explore/${contract.id}/document`)}>
        <ArrowLeft className="size-4" />
        {t("req.exit")}
      </Button>

      <PageHeader title={t("asis.title")} description={t("asis.section")} />

      <div className="mb-6 rounded-xl border border-border bg-card p-5">
        <ContractStepper current={2} />
      </div>

      <div className="mb-6 flex items-start gap-3 rounded-xl border p-4" style={{ borderColor: "var(--teal)", background: "var(--success-soft)" }}>
        <FastForward className="mt-0.5 size-5 shrink-0" style={{ color: "var(--teal)" }} />
        <div>
          <div className="font-semibold" style={{ color: "var(--navy)" }}>{t("asis.directTitle")}</div>
          <p className="mt-1 text-sm text-muted-foreground">{t("asis.directDescription")}</p>
        </div>
      </div>

      {/* Contract snapshot */}
      <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
        <ReadonlyRow label={t("asis.seller")} value={contract.seller} />
        <ReadonlyRow label={t("asis.contract")} value={contract.title} />
        <ReadonlyRow label={t("asis.period")} value={`${contract.start} ~ ${contract.end}`} />
      </div>

      {/* Editable request info */}
      <div className="mt-6 grid grid-cols-1 gap-4 rounded-xl border border-border bg-card p-4 sm:grid-cols-2 sm:p-6">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="guests">{t("asis.guests")}</Label>
          <Input id="guests" type="number" min={0} value={guests} onChange={(e) => setGuests(e.target.value)} placeholder="0" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rooms">{t("asis.rooms")}</Label>
          <Input id="rooms" type="number" min={0} value={rooms} onChange={(e) => setRooms(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="nights">숙박 일수</Label>
          <Input id="nights" type="number" min={1} value={nights} onChange={(e) => setNights(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5"><Label htmlFor="startDate">이용 시작일 *</Label><Input id="startDate" type="date" min={contract.start !== "미정" ? contract.start : undefined} max={contract.end !== "미정" ? contract.end : undefined} value={startDate} onChange={(e) => setStartDate(e.target.value)} /><span className="text-xs text-muted-foreground">공고 가능 기간 안에서 선택하세요.</span></div>
        <div className="flex flex-col gap-1.5"><Label htmlFor="endDate">이용 종료일 *</Label><Input id="endDate" type="date" min={contract.start !== "미정" ? contract.start : undefined} max={contract.end !== "미정" ? contract.end : undefined} value={endDate} onChange={(e) => setEndDate(e.target.value)} /><span className="text-xs text-muted-foreground">공고 종료일과 같을 필요는 없습니다.</span></div>
        <div className="flex flex-col gap-1.5">
          <Label>{t("asis.currency")}</Label>
          <div className="flex h-9 items-center rounded-md px-3 text-sm" style={{ background: "var(--muted)" }}>
            KRW ₩
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>{t("asis.total")}</Label>
          <div className="flex h-9 items-center rounded-md px-3 whitespace-nowrap" style={{ background: "var(--info-soft)", color: "var(--navy)", fontWeight: 700 }}>
            {formatKRW(total)}
          </div>
        </div>
      </div>

      {/* Contact info */}
      <div className="mt-6 rounded-xl border border-border bg-card p-4 sm:p-6">
        <h3 className="mb-4" style={{ color: "var(--navy)" }}>{t("asis.contactInfo")}</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name">{t("field.contactName")}</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">{t("field.email")}</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="phone">{t("field.phone")}</Label>
            <Input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-1.5">
          <Label htmlFor="message">{t("asis.message")}</Label>
          <Textarea id="message" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} placeholder={t("asis.messagePlaceholder")} />
        </div>
      </div>

      {/* Confirm */}
      <div className="mt-6 rounded-xl border p-4" style={{ borderColor: confirmError ? "var(--coral)" : "var(--border)", background: "var(--card)" }}>
        <label className="flex cursor-pointer items-start gap-2.5">
          <Checkbox
            checked={confirmed}
            onCheckedChange={(v) => {
              setConfirmed(!!v);
              setConfirmError(undefined);
            }}
            className="mt-0.5"
          />
          <span className="flex items-center gap-1.5" style={{ fontSize: "14px" }}>
            <FileCheck2 className="size-4 shrink-0" style={{ color: "var(--ocean)" }} />
            {t("asis.confirmCheck")}
          </span>
        </label>
        <FieldError message={confirmError} />
      </div>

      {/* Actions */}
      <div className="mt-6 flex flex-col gap-2 rounded-xl border border-border bg-card p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end [&_button]:w-full sm:[&_button]:w-auto">
        <Button variant="ghost" className="gap-1.5 whitespace-nowrap" onClick={() => navigate(`/buyer/explore/${contract.id}/document`)}>
          <ArrowLeft className="size-4" />
          {t("req.exit")}
        </Button>
        <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={submit}>
          <PenLine className="size-4" />
          {t("asis.submit")}
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
