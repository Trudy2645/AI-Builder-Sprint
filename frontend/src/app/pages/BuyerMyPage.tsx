import { useMemo } from "react";
import {
  Building2,
  User,
  Mail,
  Phone,
  Globe2,
  Languages,
  Coins,
  CalendarDays,
  KeyRound,
  FileText,
} from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/button";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { StatusBadge } from "../components/requests/StatusBadge";
import { useApp } from "../context/AppContext";
import { buyerProfile } from "../data/profile";
import { useRequests, type RequestStatus } from "../store/RequestsContext";

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

const STAT_ORDER: RequestStatus[] = ["draft", "reviewing", "responded", "negotiating", "signing", "completed", "closed"];

export function BuyerMyPage() {
  const { t, companyName, isDemoSession } = useApp();
  const { requests } = useRequests();
  const company = companyName || (isDemoSession ? buyerProfile.company : "계정 정보 없음");
  const profile = isDemoSession
    ? buyerProfile
    : {
        ...buyerProfile,
        company,
        contactName: "-",
        email: companyName || "-",
        phone: "-",
        country: "-",
        language: "-",
        currency: "-",
        joinedAt: "-",
      };

  const stats = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of requests) c[r.status] = (c[r.status] ?? 0) + 1;
    return c;
  }, [requests]);

  return (
    <div>
      <PageHeader title={t("my.title")} />

      {/* Header card */}
      <div className="flex flex-col items-start gap-4 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:p-6">
        <Avatar className="size-14">
          <AvatarFallback style={{ background: "var(--navy)", color: "#fff", fontWeight: 600 }}>
            {company.slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <div style={{ color: "var(--navy)", fontWeight: 700, fontSize: "18px" }}>{company}</div>
          <div className="text-muted-foreground" style={{ fontSize: "13px" }}>{t("role.buyer")} · {profile.country}</div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Profile */}
        <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
          <h3 className="mb-3" style={{ color: "var(--navy)" }}>{t("my.profile")}</h3>
          <InfoRow icon={<Building2 className="size-4" />} label={t("my.company")} value={company} />
          <InfoRow icon={<User className="size-4" />} label={t("my.contact")} value={profile.contactName} />
          <InfoRow icon={<Mail className="size-4" />} label={t("my.email")} value={profile.email} />
          <InfoRow icon={<Phone className="size-4" />} label={t("my.phone")} value={profile.phone} />
          <InfoRow icon={<Globe2 className="size-4" />} label={t("my.country")} value={profile.country} />
          <InfoRow icon={<Languages className="size-4" />} label={t("my.language")} value={profile.language} />
          <InfoRow icon={<Coins className="size-4" />} label={t("my.currency")} value={profile.currency} />
          <InfoRow icon={<CalendarDays className="size-4" />} label={t("my.joined")} value={profile.joinedAt} />
        </div>

        {/* Password + stats */}
        <div className="flex flex-col gap-6">
          <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
            <h3 className="mb-3" style={{ color: "var(--navy)" }}>{t("my.password")}</h3>
            <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="tracking-widest" style={{ fontSize: "18px", color: "var(--muted-foreground)" }}>••••••••</div>
                <p className="mt-1 text-muted-foreground" style={{ fontSize: "12px" }}>{t("my.passwordHint")}</p>
              </div>
              <Button variant="outline" className="w-full gap-1.5 whitespace-nowrap sm:w-auto sm:shrink-0" onClick={() => toast.success(t("my.passwordToast"))}>
                <KeyRound className="size-4" />
                {t("my.changePassword")}
              </Button>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4 sm:p-6">
            <h3 className="mb-3 flex items-center gap-2" style={{ color: "var(--navy)" }}>
              <FileText className="size-4" />
              {t("my.stats")}
            </h3>
            <div className="mb-4 flex items-baseline gap-2">
              <span style={{ fontSize: "28px", fontWeight: 700, color: "var(--navy)" }}>{requests.length}</span>
              <span className="text-muted-foreground" style={{ fontSize: "13px" }}>{t("my.statTotal")}</span>
            </div>
            <div className="flex flex-col gap-2">
              {STAT_ORDER.map((s) => (
                <div key={s} className="flex items-center justify-between">
                  <StatusBadge status={s} />
                  <span style={{ fontWeight: 600 }}>{stats[s] ?? 0}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
