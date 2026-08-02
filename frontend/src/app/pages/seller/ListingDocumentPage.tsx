import { useEffect, useState } from "react";
import { ArrowLeft, Download, FileText } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { PageHeader } from "../../components/PageHeader";
import { friendlyApiError, getSellerListing, type SellerListingDetail } from "../../lib/api";

export function ListingDocumentPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [listing, setListing] = useState<SellerListingDetail | null>(null);
  const [error, setError] = useState<string>();
  useEffect(() => { if (id) void getSellerListing(id).then(setListing).catch((reason) => setError(friendlyApiError(reason))); }, [id]);
  if (error) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{error}</div>;
  if (!listing) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">계약서 원문을 불러오는 중입니다…</div>;
  const download = () => { const text = [listing.current_version.title, "", ...listing.current_version.clauses.map((clause) => `제${clause.clause_order}조 ${clause.title}\n${clause.body}`)].join("\n\n"); const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" })); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${listing.current_version.title}-원문.txt`; anchor.click(); URL.revokeObjectURL(url); toast.success("계약서 원문을 다운로드했습니다."); };
  return <div className="mx-auto max-w-[900px]"><Button variant="ghost" size="sm" className="mb-3 gap-1.5 pl-0" onClick={() => navigate(`/seller/listings/${listing.id}`)}><ArrowLeft className="size-4" />상세로</Button><PageHeader title="계약서 원문" description={`${listing.display_company_name ?? "셀러"} · ${listing.current_version.title}`} /><div className="rounded-xl border border-border bg-card p-5 sm:p-8"><div className="mb-6 flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2 font-semibold" style={{ color: "var(--navy)" }}><FileText className="size-5" />{listing.current_version.title}</div><p className="mt-1 text-sm text-muted-foreground">서버에 저장된 현재 공고 버전의 계약서 원문입니다.</p></div><Button variant="outline" className="gap-1.5" onClick={download}><Download className="size-4" />원문 다운로드</Button></div><div className="flex flex-col gap-5">{listing.current_version.clauses.map((clause) => <section key={clause.id} className="rounded-lg border border-border p-4 sm:p-5"><h2 className="flex items-center gap-2 text-base" style={{ color: "var(--navy)" }}><span style={{ color: "var(--ocean)" }}>제{clause.clause_order}조</span>{clause.title}</h2><p className="mt-2 text-sm leading-7">{clause.body}</p></section>)}</div></div></div>;
}
