import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Category } from "../data/contracts";

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
  imageUrl: string; // 바이어 카드 대표 이미지
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
    imageUrl: "",
    available: true,
    showRisk: true,
  };
}

/** 위저드 초안을 공고 목록 항목으로 변환한다. */
export function draftToListing(
  draft: ListingDraft,
  status: ListingStatus,
  riskCount: number,
): Omit<Listing, "id" | "updatedAt"> {
  return {
    productName: draft.productName || "제목 없는 공고",
    category: (draft.category || "accommodation") as Category,
    district: draft.district || "해운대구",
    start: draft.start,
    end: draft.end,
    unitPrice: parseInt(draft.unitPrice, 10) || 0,
    priceUnit: draft.priceUnit,
    quantityLabel: draft.quantity || "미정",
    status,
    method: draft.method,
    requests: 0,
    riskCount,
  };
}

interface ListingsContextValue {
  listings: Listing[];
  addListing: (l: Omit<Listing, "id" | "updatedAt">) => void;
  updateListingStatus: (id: string, status: ListingStatus) => void;
  deleteListing: (id: string) => void;
  publicCount: number;
}

const ListingsContext = createContext<ListingsContextValue | null>(null);

export function ListingsProvider({ children }: { children: ReactNode }) {
  const [listings, setListings] = useState<Listing[]>([]);

  const addListing: ListingsContextValue["addListing"] = (l) => {
    const now = new Date();
    const updatedAt = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}`;
    setListings((prev) => [{ ...l, id: `lst-${Date.now()}`, updatedAt }, ...prev]);
  };

  const updateListingStatus: ListingsContextValue["updateListingStatus"] = (id, status) => {
    const now = new Date();
    const updatedAt = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}`;
    setListings((prev) => prev.map((listing) => listing.id === id ? { ...listing, status, updatedAt } : listing));
  };

  const deleteListing: ListingsContextValue["deleteListing"] = (id) => {
    setListings((prev) => prev.filter((listing) => listing.id !== id));
  };

  const value = useMemo<ListingsContextValue>(
    () => ({
      listings,
      addListing,
      updateListingStatus,
      deleteListing,
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
