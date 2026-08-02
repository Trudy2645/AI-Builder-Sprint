import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CalendarDays,
  Coins,
  FileText,
  MapPin,
  Package,
  ShieldCheck,
  Sparkles,
  UserX,
  UsersRound,
  Wallet,
} from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { ImageWithFallback } from "../../components/figma/ImageWithFallback";
import { PageHeader } from "../../components/PageHeader";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { ListingStatusBadge } from "../../components/listings/ListingStatusBadge";
import { useApp } from "../../context/AppContext";
import { CATEGORIES, formatKRW, getContract, type Contract } from "../../data/contracts";
import { useListings, type Listing } from "../../store/ListingsContext";

const CONTRACT_BY_LISTING_ID: Record<string, string> = {
  "lst-coastline-room": "coastline-hotel-room-2026",
  "lst-bluewave-surf": "bluewave-surf-lesson-2026",
  "lst-route-rental": "route-rental-van-2026",
};

function DetailRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-border py-3 last:border-b-0">
      <span className="mt-0.5 shrink-0" style={{ color: "var(--ocean)" }}>{icon}</span>
      <div className="min-w-0">
        <div className="whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>{label}</div>
        <div className="text-foreground" style={{ fontSize: "14px" }}>{value}</div>
      </div>
    </div>
  );
}

function detailFromListing(listing: Listing, contract: Contract | undefined) {
  if (contract) return contract;
  return {
    title: listing.productName,
    seller: "해운대 오션스테이",
    image: "",
    available: listing.status === "public",
    district: listing.district,
    category: listing.category,
    aiSummary: ["셀러가 등록한 공급 조건을 기준으로 작성된 계약 공고입니다."],
    details: {
      period: listing.start && listing.end ? `${listing.start} ~ ${listing.end}` : "공급 기간 미정",
      supplyQuantity: listing.quantityLabel,
      unitPrice: `${listing.priceUnit} ${formatKRW(listing.unitPrice)}`,
      cancellation: "계약서 원문 확인 필요",
      noShow: "계약서 원문 확인 필요",
      settlement: "계약서 원문 확인 필요",
    },
    clauses: [],
  } as Pick<Contract, "title" | "seller" | "image" | "available" | "district" | "category" | "aiSummary" | "details" | "clauses">;
}

export function ListingDetailPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { id } = useParams();
  const listing = useListings().listings.find((item) => item.id === id);

  if (!listing) {
    return <div className="rounded-xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">공고를 찾을 수 없습니다.</div>;
  }

  const contract = getContract(CONTRACT_BY_LISTING_ID[listing.id]);
  const detail = { ...detailFromListing(listing, contract), available: listing.status === "public" };
  const catKey = CATEGORIES.find((item) => item.value === listing.category)?.labelKey ?? "cat.all";
  const riskCount = contract?.clauses.filter((clause) => clause.risk).length ?? listing.riskCount;

  return (
    <div className="mx-auto max-w-[1120px]">
      <Button variant="ghost" size="sm" className="mb-3 gap-1.5 pl-0 whitespace-nowrap" onClick={() => navigate("/seller/listings")}>
        <ArrowLeft className="size-4" />목록으로
      </Button>
      <PageHeader
        title="공고 상세"
        description="바이어에게 공개되는 공고 내용과 계약서 원문을 확인합니다."
      />

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="relative h-48 w-full overflow-hidden bg-secondary sm:h-64">
          <ImageWithFallback src={detail.image} alt={detail.title} className="size-full object-cover" />
          <div className="absolute left-5 top-5 flex items-center gap-2">
            <Badge variant="outline" className="bg-white/95 whitespace-nowrap" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>{t(catKey)}</Badge>
            <Badge className="gap-1 whitespace-nowrap border-transparent" style={{ background: detail.available ? "var(--success-soft)" : "var(--muted)", color: detail.available ? "var(--success)" : "var(--muted-foreground)" }}>
              <ShieldCheck className="size-3.5" />{detail.available ? "계약 가능" : "계약 마감"}
            </Badge>
          </div>
        </div>
        <div className="p-5 sm:p-7">
          <div className="flex flex-wrap items-center gap-2 text-muted-foreground" style={{ fontSize: "14px" }}><MapPin className="size-4" />{detail.district}</div>
          <div className="mt-2 text-muted-foreground" style={{ fontSize: "14px" }}>{detail.seller}</div>
          <h1 className="mt-1" style={{ color: "var(--navy)" }}>{detail.title}</h1>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6">
        <div className="rounded-xl border border-border bg-card p-5 sm:p-6">
          <h2 className="mb-2" style={{ color: "var(--navy)" }}>이용 기간 · 정산 조건</h2>
          <DetailRow icon={<CalendarDays className="size-4" />} label="이용 기간" value={detail.details.period} />
          <DetailRow icon={<Package className="size-4" />} label="공급 수량" value={detail.details.supplyQuantity} />
          <DetailRow icon={<UsersRound className="size-4" />} label="최소 제안 기준" value={listing.category === "accommodation" ? "10실 이상 · 객실당 기준 인원 2명" : "최소 제안 수량은 계약서 기준"} />
          <DetailRow icon={<Coins className="size-4" />} label="단가" value={detail.details.unitPrice} />
          <DetailRow icon={<Ban className="size-4" />} label="무료 취소" value={detail.details.cancellation} />
          <DetailRow icon={<UserX className="size-4" />} label="노쇼" value={detail.details.noShow} />
          <DetailRow icon={<Wallet className="size-4" />} label="정산" value={detail.details.settlement} />
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-xl border p-5" style={{ background: "var(--info-soft)", borderColor: "var(--ocean)" }}>
            <div className="flex items-center gap-1.5" style={{ color: "var(--ocean)", fontWeight: 700 }}><Sparkles className="size-4" />AI 3줄 요약</div>
            <ul className="mt-3 flex flex-col gap-2">
              {detail.aiSummary.map((line, index) => <li key={index} className="flex gap-2 text-foreground" style={{ fontSize: "14px", lineHeight: 1.6 }}><span style={{ color: "var(--ocean)", fontWeight: 700 }}>{index + 1}</span><span>{line}</span></li>)}
            </ul>
          </div>
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-center gap-2" style={{ color: "var(--navy)", fontWeight: 700 }}><AlertTriangle className="size-4" style={{ color: "var(--coral)" }} />확인 필요 조항 {riskCount}개</div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">공고 내용을 수정하지 않고 등록 당시의 계약 조건을 기준으로 확인합니다.</p>
          </div>
          {contract && <Button className="w-full gap-1.5" style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/listings/${listing.id}/document`)}><FileText className="size-4" />계약서 원문 보기</Button>}
        </div>
      </div>

      {contract && (
        <div className="mt-6 rounded-xl border border-border bg-card p-5 sm:p-6">
          <h2 className="mb-3" style={{ color: "var(--navy)" }}>주요 계약 조항</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {contract.clauses.slice(0, 6).map((clause) => (
              <div key={clause.no} className="rounded-lg border border-border p-4">
                <div className="flex items-center gap-2"><span style={{ color: "var(--ocean)", fontWeight: 700 }}>{clause.no}</span><span className="font-semibold">{clause.title}</span></div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{clause.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
