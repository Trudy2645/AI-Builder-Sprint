import { useMemo, useState } from "react";
import {
  Building2,
  CalendarDays,
  FileCheck2,
  IdCard,
  Mail,
  MapPin,
  PenLine,
  Phone,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { StatusBadge } from "../../components/requests/StatusBadge";
import { maskBizNo } from "../../data/sellerProfile";
import { useSellerProfile } from "../../store/SellerProfileContext";
import { useRequests, type RequestStatus } from "../../store/RequestsContext";
import { useListings } from "../../store/ListingsContext";

function InfoRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-border py-3 last:border-b-0">
      <span className="mt-0.5 shrink-0" style={{ color: "var(--ocean)" }}>{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>{label}</div>
        <div className="break-all" style={{ fontSize: "14px" }}>{value}</div>
      </div>
    </div>
  );
}

const STAT_ORDER: RequestStatus[] = ["reviewing", "responded", "negotiating", "signing", "completed", "closed"];

export function SellerMyPage() {
  const { profile, updateProfile } = useSellerProfile();
  const { requests } = useRequests();
  const { listings, publicCount } = useListings();

  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState(profile);

  const stats = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of requests) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [requests]);

  const openEdit = () => {
    setForm(profile);
    setEditOpen(true);
  };

  const save = () => {
    updateProfile(form);
    setEditOpen(false);
    toast.success("사업자 정보가 수정되었습니다.");
  };

  return (
    <div className="mx-auto max-w-[920px]">
      <PageHeader title="셀러 마이페이지" description="사업자 정보와 계약 공고·협상·체결 현황을 확인하고 수정하세요." />

      {/* Header card */}
      <Card className="flex flex-col items-start gap-4 p-4 sm:flex-row sm:items-center sm:p-6">
        <div className="flex size-14 shrink-0 items-center justify-center rounded-xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
          <Building2 className="size-7" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="break-words" style={{ color: "var(--navy)", fontWeight: 700, fontSize: "18px" }}>{profile.company}</div>
          <div className="mt-1 flex items-center gap-1.5 text-sm" style={{ color: "var(--success)" }}>
            <ShieldCheck className="size-4 shrink-0" />사업자 인증 완료
          </div>
        </div>
        <Button variant="outline" className="w-full gap-1.5 whitespace-nowrap sm:w-auto sm:shrink-0" onClick={openEdit}>
          <PenLine className="size-4" />사업자 정보 수정
        </Button>
      </Card>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Profile info */}
        <Card className="p-4 sm:p-6">
          <h3 className="mb-3" style={{ color: "var(--navy)" }}>사업자 정보</h3>
          <InfoRow icon={<UserRound className="size-4" />} label="대표자" value={profile.ceoName} />
          <InfoRow icon={<IdCard className="size-4" />} label="사업자등록번호" value={maskBizNo(profile.bizNo)} />
          <InfoRow icon={<UserRound className="size-4" />} label="담당자" value={profile.contactName} />
          <InfoRow icon={<Mail className="size-4" />} label="담당자 이메일" value={profile.email} />
          <InfoRow icon={<Phone className="size-4" />} label="전화번호" value={profile.phone} />
          <InfoRow icon={<MapPin className="size-4" />} label="사업장 주소" value={profile.address} />
          <InfoRow icon={<FileCheck2 className="size-4" />} label="공급 분야" value={profile.supplyFields} />
          <InfoRow icon={<CalendarDays className="size-4" />} label="가입일" value={profile.joinedAt} />
        </Card>

        {/* Stats */}
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-3">
            <Card className="p-4">
              <div className="text-xs text-muted-foreground">임시저장 공고</div>
              <div className="mt-2 text-2xl font-bold" style={{ color: "var(--navy)" }}>
                {listings.filter((item) => item.status === "draft").length}건
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-muted-foreground">공개 중인 공고</div>
              <div className="mt-2 text-2xl font-bold" style={{ color: "var(--navy)" }}>{publicCount}건</div>
            </Card>
          </div>

          <Card className="p-4 sm:p-6">
            <h3 className="mb-3 flex items-center gap-2" style={{ color: "var(--navy)" }}>
              <FileCheck2 className="size-4" />
              계약 현황
            </h3>
            <div className="mb-4 flex items-baseline gap-2">
              <span style={{ fontSize: "28px", fontWeight: 700, color: "var(--navy)" }}>{requests.length}</span>
              <span className="text-muted-foreground" style={{ fontSize: "13px" }}>건 전체</span>
            </div>
            <div className="flex flex-col gap-2">
              {STAT_ORDER.map((s) => (
                <div key={s} className="flex items-center justify-between">
                  <StatusBadge status={s} />
                  <span style={{ fontWeight: 600 }}>{stats[s] ?? 0}건</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>사업자 정보 수정</DialogTitle>
            <DialogDescription>수정한 정보는 저장 즉시 마이페이지에 반영됩니다. (데모용 로컬 저장)</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <Label htmlFor="company">회사명</Label>
              <Input id="company" value={form.company} onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-1.5">
                <Label htmlFor="ceoName">대표자</Label>
                <Input id="ceoName" value={form.ceoName} onChange={(e) => setForm((f) => ({ ...f, ceoName: e.target.value }))} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="contactName">담당자</Label>
                <Input id="contactName" value={form.contactName} onChange={(e) => setForm((f) => ({ ...f, contactName: e.target.value }))} />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="email">이메일</Label>
              <Input id="email" type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="phone">전화번호</Label>
              <Input id="phone" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="address">사업장 주소</Label>
              <Input id="address" value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="supplyFields">공급 분야</Label>
              <Input id="supplyFields" value={form.supplyFields} onChange={(e) => setForm((f) => ({ ...f, supplyFields: e.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>취소</Button>
            <Button style={{ background: "var(--navy)" }} onClick={save}>저장</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
