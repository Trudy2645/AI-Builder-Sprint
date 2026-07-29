import { FilePenLine, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../components/ui/table";
import { useApp } from "../../context/AppContext";
import { receivedRequests } from "../../data/receivedRequests";

export function ReceivedRequestsPage() {
  const { t } = useApp();
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader title={t("recv.title")} description={t("recv.subtitle")} />

      {receivedRequests.length === 0 && (
        <div className="rounded-xl border border-border bg-card p-10 text-center text-muted-foreground lg:hidden">{t("recv.empty")}</div>
      )}
      {receivedRequests.length > 0 && (
        <div className="space-y-3 lg:hidden">
          {receivedRequests.map((r) => (
            <div key={r.id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="line-clamp-2 text-base" style={{ color: "var(--navy)" }}>{r.contractTitle}</h3>
                  <p className="mt-1 truncate text-sm text-muted-foreground">{r.buyer}</p>
                </div>
                <Badge variant="outline" className="shrink-0 gap-1 whitespace-nowrap" style={{ borderColor: "var(--teal)", color: "var(--teal)" }}>
                  <FilePenLine className="size-3" />
                  {t("recv.type.revision")}
                </Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 border-y border-border py-3 text-sm">
                <div><div className="text-xs text-muted-foreground">{t("recv.col.count")}</div><div className="mt-1">{r.revisions.length}{t("recv.countUnit")}</div></div>
                <div className="text-right"><div className="text-xs text-muted-foreground">{t("recv.col.date")}</div><div className="mt-1 whitespace-nowrap">{r.createdAt}</div></div>
              </div>
              <Button className="mt-3 w-full gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/received/${r.id}`)}>
                {t("recv.review")}
                <ArrowRight className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
      <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
        {receivedRequests.length === 0 ? (
          <div className="p-16 text-center text-muted-foreground">{t("recv.empty")}</div>
        ) : (
          <Table className="table-fixed">
            <colgroup>
              <col className="w-[18%]" />
              <col className="w-[30%]" />
              <col className="w-[14%]" />
              <col className="w-[10%]" />
              <col className="w-[14%]" />
              <col className="w-[14%]" />
            </colgroup>
            <TableHeader className="bg-muted/20">
              <TableRow>
                <TableHead className="h-12 whitespace-nowrap px-3">{t("recv.col.buyer")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3">{t("recv.col.contract")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.col.type")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.col.count")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.col.date")}</TableHead>
                <TableHead className="h-12 whitespace-nowrap px-3 text-center">{t("recv.review")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {receivedRequests.map((r) => (
                <TableRow key={r.id} className="h-16">
                  <TableCell className="whitespace-nowrap px-3 py-3" style={{ fontWeight: 600 }}>{r.buyer}</TableCell>
                  <TableCell className="min-w-0 px-3 py-3">
                    <span className="block truncate">{r.contractTitle}</span>
                  </TableCell>
                  <TableCell className="px-3 py-3 text-center">
                    <Badge variant="outline" className="gap-1 whitespace-nowrap" style={{ borderColor: "var(--teal)", color: "var(--teal)" }}>
                      <FilePenLine className="size-3" />
                      {t("recv.type.revision")}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap px-3 py-3 text-center">
                    {r.revisions.length}{t("recv.countUnit")}
                  </TableCell>
                  <TableCell className="whitespace-nowrap px-3 py-3 text-center text-muted-foreground">{r.createdAt}</TableCell>
                  <TableCell className="px-3 py-3 text-center">
                    <Button size="sm" className="gap-1.5 whitespace-nowrap" style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/received/${r.id}`)}>
                      {t("recv.review")}
                      <ArrowRight className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
