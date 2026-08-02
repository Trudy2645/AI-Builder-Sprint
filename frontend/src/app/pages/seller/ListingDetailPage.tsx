import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, Ban, CalendarDays, Coins, FileText, MapPin, Package, ShieldCheck, Sparkles, UserX, UsersRound, Wallet } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { PageHeader } from "../../components/PageHeader";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { ImageWithFallback } from "../../components/figma/ImageWithFallback";
import { ListingStatusBadge } from "../../components/listings/ListingStatusBadge";
import { useApp } from "../../context/AppContext";
import { friendlyApiError, getSellerListing, type SellerListingDetail } from "../../lib/api";
import { CATEGORIES, formatKRW } from "../../lib/catalog";
import type { ListingStatus } from "../../store/ListingsContext";

function DetailRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="flex items-start gap-3 border-b border-border py-3 last:border-b-0"><span className="mt-0.5 shrink-0" style={{ color: "var(--ocean)" }}>{icon}</span><div><div className="text-xs text-muted-foreground">{label}</div><div className="text-sm">{value || "정보 없음"}</div></div></div>;
}

export function ListingDetailPage() {
  const { t } = useApp();
  const navigate = useNavigate();
  const { id } = useParams();
  const [listing, setListing] = useState<SellerListingDetail | null>(null);
  const [error, setError] = useState<string>();
  useEffect(() => { if (id) void getSellerListing(id).then(setListing).catch((reason) => setError(friendlyApiError(reason))); }, [id]);
  if (error) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">{error}</div>;
  if (!listing) return <div className="rounded-xl border border-dashed p-16 text-center text-muted-foreground">공고를 불러오는 중입니다…</div>;
  const catKey = CATEGORIES.find((item) => item.value === listing.category)?.labelKey ?? "cat.all";
  const terms = listing.terms;
  const uiStatus: ListingStatus = listing.status === "published" ? "public" : listing.status === "processing" || listing.status === "ready" ? "needsReview" : listing.status === "paused" ? "paused" : listing.status === "expired" ? "expired" : "draft";
  const period = `${terms.service_start_date ?? ""} ~ ${terms.service_end_date ?? ""}`;
  const price = terms.base_price_amount_minor == null ? "정보 없음" : `${terms.price_display_basis ?? terms.price_unit ?? ""} ${formatKRW(terms.base_price_amount_minor)}`;
  return <div className="mx-auto max-w-[1120px]"><Button variant="ghost" size="sm" className="mb-3 gap-1.5 pl-0" onClick={() => navigate("/seller/listings")}><ArrowLeft className="size-4" />목록으로</Button><PageHeader title="공고 상세" description="바이어에게 공개되는 공고 내용과 계약서 원문을 확인합니다." /><div className="overflow-hidden rounded-xl border border-border bg-card"><div className="relative h-48 w-full overflow-hidden bg-secondary sm:h-64"><ImageWithFallback src={""} alt={listing.title} className="size-full object-cover" /><div className="absolute left-5 top-5"><Badge variant="outline" className="bg-white/95" style={{ borderColor: "var(--ocean)", color: "var(--ocean)" }}>{t(catKey)}</Badge></div></div><div className="p-5 sm:p-7"><div className="flex items-center gap-2 text-sm text-muted-foreground"><MapPin className="size-4" />{listing.district}</div><div className="mt-2 text-sm text-muted-foreground">{listing.display_company_name ?? listing.title}</div><h1 className="mt-1" style={{ color: "var(--navy)" }}>{listing.display_title ?? listing.title}</h1><div className="mt-2"><ListingStatusBadge status={uiStatus} /></div></div></div><div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2"><div className="rounded-xl border border-border bg-card p-5 sm:p-6"><h2 className="mb-2" style={{ color: "var(--navy)" }}>이용 기간 · 정산 조건</h2><DetailRow icon={<CalendarDays className="size-4" />} label="이용 기간" value={period} /><DetailRow icon={<Package className="size-4" />} label="공급 수량" value={terms.supply_quantity_description ?? ""} /><DetailRow icon={<UsersRound className="size-4" />} label="최소 제안 기준" value={terms.minimum_quantity ? `${terms.minimum_quantity}${terms.quantity_unit ?? ""} 이상` : terms.minimum_people ? `${terms.minimum_people}명 이상` : ""} /><DetailRow icon={<Coins className="size-4" />} label="단가" value={price} /><DetailRow icon={<Ban className="size-4" />} label="무료 취소" value={terms.cancellation_policy ?? ""} /><DetailRow icon={<UserX className="size-4" />} label="노쇼" value={terms.no_show_policy ?? ""} /><DetailRow icon={<Wallet className="size-4" />} label="정산" value={terms.settlement_policy ?? ""} /></div><div className="flex flex-col gap-4"><div className="rounded-xl border border-[var(--ocean)] bg-[var(--info-soft)] p-5"><div className="flex items-center gap-1.5 font-bold" style={{ color: "var(--ocean)" }}><Sparkles className="size-4" />AI 요약</div><p className="mt-3 text-sm leading-6">{listing.ai_summary ?? "AI 요약이 아직 준비되지 않았습니다."}</p></div><div className="rounded-xl border border-border bg-card p-5"><div className="flex items-center gap-2 font-bold" style={{ color: "var(--navy)" }}><AlertTriangle className="size-4" style={{ color: "var(--coral)" }} />확인 필요 조항 {listing.attention_required_count}개</div></div><Button className="w-full gap-1.5" style={{ background: "var(--navy)" }} onClick={() => navigate(`/seller/listings/${listing.id}/document`)}><FileText className="size-4" />계약서 원문 보기</Button></div></div><div className="mt-6 rounded-xl border border-border bg-card p-5 sm:p-6"><h2 className="mb-3" style={{ color: "var(--navy)" }}>주요 계약 조항</h2><div className="grid gap-3 md:grid-cols-2">{listing.current_version.clauses.map((clause) => <div key={clause.id} className="rounded-lg border border-border p-4"><div className="font-semibold"><span className="mr-2" style={{ color: "var(--ocean)" }}>제{clause.clause_order}조</span>{clause.title}</div><p className="mt-2 text-sm leading-6 text-muted-foreground">{clause.body}</p></div>)}</div></div></div>;
}
