import { ArrowLeft, Download, FileText } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { Button } from "../../components/ui/button";
import { PageHeader } from "../../components/PageHeader";
import { useListings } from "../../store/ListingsContext";
import { getContract } from "../../data/contracts";

const CONTRACT_BY_LISTING_ID: Record<string, string> = {
  "lst-coastline-room": "coastline-hotel-room-2026",
  "lst-bluewave-surf": "bluewave-surf-lesson-2026",
  "lst-route-rental": "route-rental-van-2026",
};

export function ListingDocumentPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const listing = useListings().listings.find((item) => item.id === id);
  const contract = getContract(listing ? CONTRACT_BY_LISTING_ID[listing.id] : undefined);

  if (!listing || !contract) {
    return <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">계약서 원문을 찾을 수 없습니다.</div>;
  }

  const download = () => {
    const text = [contract.title, contract.seller, "", ...contract.clauses.map((clause) => `${clause.no} ${clause.title}\n${clause.text}`)].join("\n\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${contract.title}-원문.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto max-w-[900px]">
      <Button variant="ghost" size="sm" className="mb-3 gap-1.5 pl-0 whitespace-nowrap" onClick={() => navigate(`/seller/listings/${listing.id}`)}>
        <ArrowLeft className="size-4" />상세로
      </Button>
      <PageHeader
        title="계약서 원문"
        description={`${contract.seller} · ${contract.title}`}
      />
      <div className="rounded-xl border border-border bg-card p-5 sm:p-8">
        <div className="mb-6 flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div><div className="flex items-center gap-2 font-semibold" style={{ color: "var(--navy)" }}><FileText className="size-5" />{contract.title}</div><p className="mt-1 text-sm text-muted-foreground">등록 당시 저장된 셀러 계약서 원문입니다.</p></div>
          <Button variant="outline" className="gap-1.5 whitespace-nowrap" onClick={download}><Download className="size-4" />원문 다운로드</Button>
        </div>
        <div className="flex flex-col gap-5">
          {contract.clauses.map((clause) => (
            <section key={clause.no} className="rounded-lg border border-border p-4 sm:p-5">
              <h2 className="flex items-center gap-2 text-base" style={{ color: "var(--navy)" }}><span style={{ color: "var(--ocean)" }}>{clause.no}</span>{clause.title}</h2>
              <p className="mt-2 text-sm leading-7 text-foreground">{clause.text}</p>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
