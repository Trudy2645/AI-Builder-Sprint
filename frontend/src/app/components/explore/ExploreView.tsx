import { useEffect, useMemo, useState } from "react";
import {
  Banknote,
  CalendarRange,
  ChevronDown,
  MapPin,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Users,
  X,
} from "lucide-react";
import { ContractCard } from "./ContractCard";
import { Label } from "../ui/label";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Slider } from "../ui/slider";
import { Checkbox } from "../ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { useApp } from "../../context/AppContext";
import {
  CATEGORIES,
  DISTRICTS,
  formatKRW,
  type Category,
  type Contract,
} from "../../data/contracts";
import { friendlyApiError, getPublicListings, type PublicListing } from "../../lib/api";

type Sort = "recommended" | "latest" | "popular" | "priceLow" | "priceHigh";
const PRICE_MAX = 10_000_000;

const categoryByApiCategory: Record<PublicListing["category"], Category> = {
  accommodation: "accommodation",
  activity: "activity",
  tour: "tour",
  vehicle_rental: "vehicle_rental",
};

function toContract(listing: PublicListing): Contract {
  const price = listing.base_price?.amount_minor ?? 0;
  const currency = listing.base_price?.currency ?? "KRW";
  const period = `${listing.availability.start_date ?? "미정"} ~ ${listing.availability.end_date ?? "미정"}`;
  return {
    id: listing.id,
    seller: listing.seller.name,
    title: listing.title,
    category: categoryByApiCategory[listing.category],
    district: listing.district,
    start: listing.availability.start_date ?? "미정",
    end: listing.availability.end_date ?? "미정",
    unitPrice: price,
    priceUnit: listing.base_price?.unit ?? "기준 단가",
    quantityLabel: listing.supply_quantity_description ?? "미정",
    capacity: Number.MAX_SAFE_INTEGER,
    available: listing.contract_available,
    popularity: 0,
    createdOrder: 0,
    recommendScore: 0,
    image: listing.hero_image_url ?? "",
    aiSummary: listing.ai_summary?.split("\n") ?? ["AI 요약이 아직 준비되지 않았습니다."],
    details: {
      period,
      supplyQuantity: "상세 페이지에서 확인",
      unitPrice: `${price.toLocaleString("ko-KR")} ${currency}`,
      cancellation: "상세 페이지에서 확인",
      noShow: "상세 페이지에서 확인",
      settlement: "상세 페이지에서 확인",
    },
    clauses: [],
  };
}

function toDate(s: string) {
  return new Date(s.replace(/\./g, "-"));
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <Badge
      variant="outline"
      className="h-7 gap-1 rounded-full border-transparent px-2.5 whitespace-nowrap"
      style={{ background: "var(--info-soft)", color: "var(--ocean)" }}
    >
      {label}
      <button type="button" onClick={onRemove} aria-label={`${label} 필터 제거`} className="rounded-full p-0.5 hover:bg-white/70">
        <X className="size-3" />
      </button>
    </Badge>
  );
}

export function ExploreView({ base }: { base: string }) {
  const { t } = useApp();

  const [category, setCategory] = useState<Category | "all">("all");
  const [search, setSearch] = useState("");
  const [district, setDistrict] = useState<string>("all");
  const [guests, setGuests] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [price, setPrice] = useState<[number, number] | null>(null);
  const [availableOnly, setAvailableOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("recommended");
  const [serverContracts, setServerContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const refresh = () => getPublicListings()
      .then((listings) => {
        if (active) { setServerContracts(listings.map(toContract)); setLoadError(null); }
      })
      .catch((error: unknown) => { if (active) setLoadError(friendlyApiError(error)); })
      .finally(() => { if (active) setLoading(false); });
    refresh();
    window.addEventListener("focus", refresh);
    return () => { active = false; window.removeEventListener("focus", refresh); };
  }, []);

  const reset = () => {
    setCategory("all");
    setSearch("");
    setDistrict("all");
    setGuests("");
    setFrom("");
    setTo("");
    setPrice(null);
    setAvailableOnly(false);
  };

  const results = useMemo(() => {
    const list: Contract[] = serverContracts.filter((c) => {
      const keyword = search.trim().toLocaleLowerCase();
      if (keyword && !`${c.seller} ${c.title}`.toLocaleLowerCase().includes(keyword)) return false;
      if (category !== "all" && c.category !== category) return false;
      if (district !== "all" && c.district !== district) return false;
      const g = parseInt(guests, 10);
      if (!Number.isNaN(g) && g > 0 && c.capacity < g) return false;
      if (from && toDate(c.end) < new Date(from)) return false;
      if (to && toDate(c.start) > new Date(to)) return false;
      if (price && (c.unitPrice < price[0] || c.unitPrice > price[1])) return false;
      if (availableOnly && !c.available) return false;
      return true;
    });

    const sorters: Record<Sort, (a: Contract, b: Contract) => number> = {
      recommended: (a, b) => b.recommendScore - a.recommendScore,
      latest: (a, b) => b.createdOrder - a.createdOrder,
      popular: (a, b) => b.popularity - a.popularity,
      priceLow: (a, b) => a.unitPrice - b.unitPrice,
      priceHigh: (a, b) => b.unitPrice - a.unitPrice,
    };
    return [...list].sort(sorters[sort]);
  }, [search, category, district, guests, from, to, price, availableOnly, sort, serverContracts]);

  const categoryLabel = CATEGORIES.find((c) => c.value === category);
  const hasPriceFilter = price !== null;
  const activeFilterCount = [
    category !== "all",
    district !== "all",
    !!guests,
    !!from || !!to,
    hasPriceFilter,
    availableOnly,
  ].filter(Boolean).length;

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <div className="p-4 sm:p-5 lg:p-6">
          <div className="flex flex-col gap-3 lg:flex-row">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="업체명, 상품명 또는 계약명을 검색하세요"
                className="h-12 rounded-xl border-border bg-background pl-12 pr-4"
              />
            </div>
            <Button className="h-12 w-full gap-2 rounded-xl px-7 whitespace-nowrap lg:w-auto" style={{ background: "var(--navy)" }}>
              <Search className="size-4" />
              계약 검색
            </Button>
          </div>

          <div className="mt-5 border-t border-border pt-5">
            <div className="flex items-center gap-3 overflow-x-auto pb-1">
              <span className="mr-1 flex shrink-0 items-center gap-2 whitespace-nowrap" style={{ color: "var(--navy)", fontSize: "13px", fontWeight: 700 }}>
                분야
              </span>
              {CATEGORIES.map((c) => {
                const active = category === c.value;
                return (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => setCategory(c.value)}
                    className="h-9 shrink-0 rounded-full border px-4 transition-all whitespace-nowrap"
                    style={{
                      fontSize: "13px",
                      fontWeight: active ? 700 : 500,
                      borderColor: active ? "var(--navy)" : "var(--border)",
                      background: active ? "var(--navy)" : "var(--background)",
                      color: active ? "#fff" : "var(--foreground)",
                    }}
                  >
                    {t(c.labelKey)}
                  </button>
                );
              })}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
              <Select value={district} onValueChange={setDistrict}>
                <SelectTrigger className="h-10 w-full gap-2 rounded-lg whitespace-nowrap sm:w-[170px]">
                  <MapPin className="size-4 shrink-0 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">전체 지역</SelectItem>
                  {DISTRICTS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                </SelectContent>
              </Select>

              <div className="relative w-full sm:w-[150px]">
                <Users className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="number"
                  min={0}
                  value={guests}
                  onChange={(e) => setGuests(e.target.value)}
                  placeholder="이용 인원"
                  className="h-10 rounded-lg pl-9"
                />
              </div>

              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="h-10 w-full gap-2 rounded-lg whitespace-nowrap sm:w-auto">
                    <CalendarRange className="size-4 text-muted-foreground" />
                    {from || to ? `${from || "시작일"} ~ ${to || "종료일"}` : "이용 기간"}
                    <ChevronDown className="size-3.5 opacity-60" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="start" className="w-[calc(100vw-2rem)] max-w-[340px]">
                  <div className="space-y-3">
                    <div>
                      <div style={{ fontWeight: 700, color: "var(--navy)" }}>이용 기간</div>
                      <p className="mt-1 text-muted-foreground" style={{ fontSize: "12px" }}>계약 상품을 이용할 시작일과 종료일을 선택하세요.</p>
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div className="space-y-1.5"><Label>시작일</Label><Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
                      <div className="space-y-1.5"><Label>종료일</Label><Input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></div>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>

              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="h-10 w-full gap-2 rounded-lg whitespace-nowrap sm:w-auto">
                    <Banknote className="size-4 text-muted-foreground" />
                    {price ? `${formatKRW(price[0])} ~ ${formatKRW(price[1])}` : "금액대"}
                    <ChevronDown className="size-3.5 opacity-60" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="start" className="w-[calc(100vw-2rem)] max-w-[320px]">
                  <div className="space-y-4">
                    <div>
                      <div style={{ fontWeight: 700, color: "var(--navy)" }}>기준 단가 범위</div>
                      <p className="mt-1 text-muted-foreground" style={{ fontSize: "12px" }}>상품별 객실 또는 1인 기준 단가입니다.</p>
                    </div>
                    <Slider min={0} max={PRICE_MAX} step={5000} value={price ?? [0, PRICE_MAX]} onValueChange={(v) => setPrice([v[0], v[1]] as [number, number])} />
                    <div className="flex justify-between whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px" }}>
                      <span>{formatKRW(price?.[0] ?? 0)}</span>
                      <span>{formatKRW(price?.[1] ?? PRICE_MAX)}{(price?.[1] ?? PRICE_MAX) === PRICE_MAX ? "+" : ""}</span>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>

              <label className="flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-border bg-background px-3 whitespace-nowrap">
                <Checkbox checked={availableOnly} onCheckedChange={(v) => setAvailableOnly(!!v)} />
                <span style={{ fontSize: "13px" }}>계약 가능만</span>
              </label>

              <Button variant="ghost" className="h-10 gap-1.5 whitespace-nowrap sm:ml-auto" onClick={reset} disabled={activeFilterCount === 0 && !search}>
                <RotateCcw className="size-3.5" />
                전체 초기화
              </Button>
            </div>

            {activeFilterCount > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
                <span className="flex items-center gap-1.5 whitespace-nowrap text-muted-foreground" style={{ fontSize: "12px", fontWeight: 600 }}>
                  <SlidersHorizontal className="size-3.5" /> 적용된 필터 {activeFilterCount}
                </span>
                {category !== "all" && categoryLabel && <FilterChip label={t(categoryLabel.labelKey)} onRemove={() => setCategory("all")} />}
                {district !== "all" && <FilterChip label={district} onRemove={() => setDistrict("all")} />}
                {!!guests && <FilterChip label={`${guests}명`} onRemove={() => setGuests("")} />}
                {(from || to) && <FilterChip label={`${from || "시작일"} ~ ${to || "종료일"}`} onRemove={() => { setFrom(""); setTo(""); }} />}
                {price && <FilterChip label={`${formatKRW(price[0])} ~ ${formatKRW(price[1])}`} onRemove={() => setPrice(null)} />}
                {availableOnly && <FilterChip label="계약 가능" onRemove={() => setAvailableOnly(false)} />}
              </div>
            )}
          </div>
        </div>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-baseline gap-2">
              <h2 style={{ color: "var(--navy)", fontSize: "20px", fontWeight: 750 }}>계약 가능한 상품</h2>
              <span style={{ color: "var(--ocean)", fontWeight: 700 }}>{results.length}건</span>
            </div>
            <p className="mt-1 text-muted-foreground" style={{ fontSize: "13px" }}>조건을 비교하고 AI가 요약한 핵심 계약 내용을 확인하세요.</p>
          </div>
          <Select value={sort} onValueChange={(v) => setSort(v as Sort)}>
            <SelectTrigger className="h-10 w-full rounded-lg whitespace-nowrap sm:w-[165px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="recommended">{t("sort.recommended")}</SelectItem>
              <SelectItem value="latest">{t("sort.latest")}</SelectItem>
              <SelectItem value="popular">{t("sort.popular")}</SelectItem>
              <SelectItem value="priceLow">{t("sort.priceLow")}</SelectItem>
              <SelectItem value="priceHigh">{t("sort.priceHigh")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {loadError && (
          <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <div className="font-semibold">공고를 불러오지 못했습니다</div>
            <p className="mt-1">{loadError}</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => window.location.reload()}>
              다시 시도
            </Button>
          </div>
        )}
        {loading ? (
          <div className="rounded-2xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">공고를 불러오는 중입니다…</div>
        ) : results.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-card p-16 text-center text-muted-foreground">{t("explore.empty")}</div>
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {results.map((c) => <ContractCard key={c.id} contract={c} base={base} guests={guests} from={from} to={to} />)}
          </div>
        )}
      </section>
    </div>
  );
}
