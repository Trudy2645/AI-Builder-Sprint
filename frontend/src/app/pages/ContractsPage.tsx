import { FileCheck2 } from "lucide-react";
import { useNavigate } from "react-router";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { useApp, type Role } from "../context/AppContext";
import { useRequests } from "../store/RequestsContext";
import { useNegotiation } from "../store/NegotiationContext";

export function ContractsPage({ role }: { role: Role }) {
  const { t } = useApp();
  const navigate = useNavigate();
  const { requests } = useRequests();
  const { bothSigned } = useNegotiation();
  const base = role === "buyer" ? "/buyer" : "/seller";
  const rows = requests.filter((request) => request.status === "signing" || request.status === "completed");
  const completedCount = rows.filter((request) => request.status === "completed").length + (bothSigned ? 1 : 0);
  const thisMonthCount = rows.filter((request) => request.createdAt.startsWith("2026.07")).length;

  return (
    <div>
      <PageHeader title={t("contracts.title")} description={t("contracts.subtitle")} />

      <div className="grid gap-4 md:grid-cols-3">
        {[
          [t("contracts.completed"), `${completedCount}건`, "var(--navy)"],
          [t("contracts.thisMonth"), `${thisMonthCount}건`, "var(--success)"],
          [t("contracts.signRate"), rows.length ? "100%" : "-", "var(--ocean)"],
        ].map(([label, value, color]) => (
          <Card key={label} className="min-h-[132px] p-5">
            <div className="text-sm text-muted-foreground">{label}</div>
            <div className="mt-3 text-3xl font-bold" style={{ color }}>{value}</div>
          </Card>
        ))}
      </div>

      <Card className="mt-6 overflow-hidden">
        <div className="grid min-w-[720px] grid-cols-[1.2fr_1.8fr_1fr_1fr] gap-4 border-b bg-muted/40 px-5 py-4 text-xs font-semibold text-muted-foreground">
          <div>{t("contracts.partner")}</div>
          <div>{t("contracts.name")}</div>
          <div>{t("contracts.date")}</div>
          <div>{t("contracts.action")}</div>
        </div>
        {rows.length === 0 ? (
          <div className="flex min-h-[210px] min-w-[720px] flex-col items-center justify-center gap-3 text-muted-foreground">
            <FileCheck2 className="size-7" style={{ color: "var(--ocean)" }} />
            <p>{t("contracts.empty")}</p>
          </div>
        ) : rows.map((request) => {
          const completed = request.status === "completed";
          return (
            <div key={request.id} className="grid min-w-[720px] grid-cols-[1.2fr_1.8fr_1fr_1fr] items-center gap-4 border-b px-5 py-4 last:border-b-0">
              <div className="truncate font-semibold">{role === "buyer" ? request.seller : "GlobalTrip Japan"}</div>
              <div className="truncate">{request.title}</div>
              <div className="text-sm text-muted-foreground">{completed ? request.createdAt : t("contracts.waiting")}</div>
              <Button size="sm" variant="outline" className="whitespace-nowrap" onClick={() => navigate(completed ? `${base}/signing/complete` : `${base}/signing`)}>
                {t("contracts.detail")}
              </Button>
            </div>
          );
        })}
      </Card>
    </div>
  );
}
