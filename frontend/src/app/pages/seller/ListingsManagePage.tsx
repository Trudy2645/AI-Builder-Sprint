import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ListingStatusBadge } from "../../components/listings/ListingStatusBadge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { useApp } from "../../context/AppContext";
import { useListings, type ListingStatus } from "../../store/ListingsContext";
import { CATEGORIES, formatKRW } from "../../data/contracts";

type Tab = "all" | ListingStatus;
const TABS: Tab[] = ["all", "draft", "needsReview", "public", "paused", "expired"];
const tabLabel: Record<Tab, string> = {
  all: "tab.all",
  draft: "lstatus.draft",
  needsReview: "lstatus.needsReview",
  public: "lstatus.public",
  paused: "lstatus.paused",
  expired: "lstatus.expired",
};

export function ListingsManagePage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { listings } = useListings();
  const [params, setParams] = useSearchParams();
  const initialStatus = params.get("status") as Tab | null;
  const [tab, setTab] = useState<Tab>(initialStatus && TABS.includes(initialStatus) ? initialStatus : "all");

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: listings.length };
    for (const l of listings) c[l.status] = (c[l.status] ?? 0) + 1;
    return c;
  }, [listings]);

  const rows = tab === "all" ? listings : listings.filter((l) => l.status === tab);

  return (
    <div>
      <PageHeader
        title={t("listings.title")}
        description={t("listings.subtitle")}
        actions={
          <Button className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate("/seller/listings/new")}>
            <Plus className="size-4" />
            {t("listings.new")}
          </Button>
        }
      />

      {/* Status tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((tb) => {
          const active = tab === tb;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => {
                setTab(tb);
                if (tb === "all") setParams({});
                else setParams({ status: tb });
              }}
              className="flex items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 transition-colors"
              style={{
                fontSize: "13px",
                borderColor: active ? "var(--navy)" : "var(--border)",
                background: active ? "var(--navy)" : "var(--card)",
                color: active ? "#fff" : "var(--foreground)",
              }}
            >
              {t(tabLabel[tb])}
              <span
                className="rounded-full px-1.5"
                style={{
                  fontSize: "11px",
                  background: active ? "rgba(255,255,255,0.25)" : "var(--muted)",
                  color: active ? "#fff" : "var(--muted-foreground)",
                }}
              >
                {counts[tb] ?? 0}
              </span>
            </button>
          );
        })}
      </div>

      {/* Table */}
      {rows.length === 0 && (
        <div className="rounded-xl border border-border bg-card p-10 text-center text-muted-foreground lg:hidden">{t("listings.empty")}</div>
      )}
      {rows.length > 0 && (
        <div className="space-y-3 lg:hidden">
          {rows.map((l) => {
            const catKey = CATEGORIES.find((c) => c.value === l.category)?.labelKey ?? "cat.all";
            return (
              <button key={l.id} type="button" onClick={() => navigate("/seller/listings")} className="w-full rounded-xl border border-border bg-card p-4 text-left">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="line-clamp-2 text-base" style={{ color: "var(--navy)" }}>{l.productName}</h3>
                    <p className="mt-1 text-xs text-muted-foreground">{l.quantityLabel}</p>
                  </div>
                  <ListingStatusBadge status={l.status} />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-border pt-3 text-sm">
                  <div><div className="text-xs text-muted-foreground">{t("listings.col.category")}</div><div className="mt-1">{t(catKey)}</div></div>
                  <div className="text-right"><div className="text-xs text-muted-foreground">{t("listings.col.requests")}</div><div className="mt-1">{l.requests}</div></div>
                  <div><div className="text-xs text-muted-foreground">{t("listings.col.period")}</div><div className="mt-1 leading-5">{l.start && l.end ? `${l.start} ~ ${l.end}` : t("wz.tbd")}</div></div>
                  <div className="text-right"><div className="text-xs text-muted-foreground">{t("listings.col.price")}</div><div className="mt-1">{l.priceUnit}<br /><strong>{formatKRW(l.unitPrice)}</strong></div></div>
                </div>
              </button>
            );
          })}
        </div>
      )}
      <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
        {rows.length === 0 ? (
          <div className="p-16 text-center text-muted-foreground">{t("listings.empty")}</div>
        ) : (
          <Table className="table-fixed">
            <colgroup>
              <col className="w-[27%]" />
              <col className="w-[10%]" />
              <col className="w-[18%]" />
              <col className="w-[14%]" />
              <col className="w-[8%]" />
              <col className="w-[13%]" />
              <col className="w-[10%]" />
            </colgroup>
            <TableHeader className="bg-muted/20">
              <TableRow>
                <TableHead className="h-12 whitespace-nowrap">{t("listings.col.product")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap text-center">{t("listings.col.category")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap text-center">{t("listings.col.period")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap text-right">{t("listings.col.price")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap text-center">{t("listings.col.requests")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap text-center">{t("listings.col.status")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap text-center">{t("listings.col.updated")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((l) => {
                const catKey = CATEGORIES.find((c) => c.value === l.category)?.labelKey ?? "cat.all";
                return (
                  <TableRow key={l.id} className="h-16">
                    <TableCell className="min-w-0 py-3">
                      <span className="block truncate" style={{ fontWeight: 600, color: "var(--navy)" }}>{l.productName}</span>
                      <span className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>{l.quantityLabel}</span>
                    </TableCell>
                    <TableCell className="py-3 text-center">
                      <Badge variant="outline" className="whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>{t(catKey)}</Badge>
                    </TableCell>
                    <TableCell className="py-3 text-center text-muted-foreground" style={{ fontSize: "12px" }}>
                      {l.start && l.end ? (
                        <span className="flex flex-col items-center whitespace-nowrap leading-5">
                          <span>{l.start}</span>
                          <span>~ {l.end}</span>
                        </span>
                      ) : t("wz.tbd")}
                    </TableCell>
                    <TableCell className="py-3 text-right">
                      <span className="flex flex-col items-end whitespace-nowrap leading-5">
                        <span className="text-muted-foreground" style={{ fontSize: "11px" }}>{l.priceUnit}</span>
                        <span style={{ fontSize: "13px" }}>{formatKRW(l.unitPrice)}</span>
                      </span>
                    </TableCell>
                    <TableCell className="py-3 text-center">{l.requests}</TableCell>
                    <TableCell className="py-3 text-center"><ListingStatusBadge status={l.status} /></TableCell>
                    <TableCell className="whitespace-nowrap py-3 text-center text-muted-foreground" style={{ fontSize: "13px" }}>{l.updatedAt}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
