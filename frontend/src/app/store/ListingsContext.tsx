import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import type { Category } from "../data/contracts";
import { listSellerListings, type SellerListingSummary } from "../lib/sellerAi";

// 계약 공고 상태: 임시저장 / AI 검토 필요 / 공개 중 / 공개 중지 / 기간 만료
export type ListingStatus = "draft" | "needsReview" | "public" | "paused" | "expired";

// 공고 작성 방식
export type CreateMethod = "write" | "upload";

export interface Listing {
  id: string;
  productName: string;
  category: Category;
  district: string;
  start: string; // YYYY.MM.DD
  end: string;
  unitPrice: number; // KRW
  priceUnit: string; // 객실당 / 1인당 / 1동당
  quantityLabel: string;
  status: ListingStatus;
  method: CreateMethod;
  requests: number; // 받은 요청 수
  updatedAt: string; // YYYY.MM.DD
  riskCount: number; // AI가 감지한 확인 필요 조항 수
}

/**
 * 공고 작성 위저드에서 단계 간 공유하는 초안 데이터.
 * (숫자 입력은 폼 편의를 위해 문자열로 보관)
 */
export interface ListingDraft {
  method: CreateMethod;
  // 상품 정보
  productName: string;
  category: Category | "";
  district: string;
  // 공급 조건
  start: string;
  end: string;
  quantity: string; // 공급 수량 라벨 (예: 주말 객실 최대 30실)
  unitPrice: string;
  priceUnit: string;
  minQty: string;
  maxQty: string;
  // 계약 조건
  cancellation: string;
  noShow: string;
  settlement: string;
  liability: string; // 책임 조건
  termination: string; // 계약 해지
  special: string; // 특약
  // 바이어 공개 정보 설정
  headline: string; // 공개용 한 줄 소개
  available: boolean; // 계약 가능 여부 공개
  showRisk: boolean; // AI 위험 요약 공개
}

export function createEmptyDraft(method: CreateMethod): ListingDraft {
  return {
    method,
    productName: "",
    category: "",
    district: "",
    start: "",
    end: "",
    quantity: "",
    unitPrice: "",
    priceUnit: "객실당",
    minQty: "",
    maxQty: "",
    cancellation: "",
    noShow: "",
    settlement: "",
    liability: "",
    termination: "",
    special: "",
    headline: "",
    available: true,
    showRisk: true,
  };
}

interface ListingsContextValue {
  listings: Listing[];
  refreshListings: () => Promise<void>;
  publicCount: number;
}

const ListingsContext = createContext<ListingsContextValue | null>(null);

export function ListingsProvider({ children }: { children: ReactNode }) {
  const { currentRole, organizationId } = useApp();
  const [listings, setListings] = useState<Listing[]>([]);

  const fromApi = (listing: SellerListingSummary): Listing => ({
    id: listing.id,
    productName: listing.display_title || listing.title,
    category: listing.category,
    district: listing.district,
    start: listing.service_start_date?.replaceAll("-", ".") ?? "",
    end: listing.service_end_date?.replaceAll("-", ".") ?? "",
    unitPrice: listing.base_price?.amount_minor ?? 0,
    priceUnit: listing.base_price?.unit ?? "",
    quantityLabel: listing.supply_quantity_description ?? "미정",
    status: listing.status === "published"
      ? "public"
      : listing.status === "ready" || listing.status === "processing"
        ? "needsReview"
        : listing.status === "archived"
          ? "expired"
          : listing.status,
    method: listing.creation_method === "manual" ? "write" : "upload",
    requests: listing.contract_request_count,
    updatedAt: listing.updated_at.slice(0, 10).replaceAll("-", "."),
    riskCount: listing.attention_required_count,
  });

  const refreshListings = async () => {
    if (currentRole !== "seller" || !organizationId) {
      setListings([]);
      return;
    }
    const rows = await listSellerListings(organizationId);
    setListings(rows.map(fromApi));
  };

  useEffect(() => {
    void refreshListings().catch(() => setListings([]));
  }, [currentRole, organizationId]);

  const value = useMemo<ListingsContextValue>(
    () => ({
      listings,
      refreshListings,
      publicCount: listings.filter((l) => l.status === "public").length,
    }),
    [listings],
  );

  return <ListingsContext.Provider value={value}>{children}</ListingsContext.Provider>;
}

export function useListings() {
  const ctx = useContext(ListingsContext);
  if (!ctx) throw new Error("useListings must be used within ListingsProvider");
  return ctx;
}
