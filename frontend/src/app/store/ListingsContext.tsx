import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import type { Category } from "../data/contracts";
import { changeSellerListingStatus, friendlyApiError, getSellerListings, type SellerListingSummary } from "../lib/api";

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
  availabilityStart: string;
  availabilityEnd: string;
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
    availabilityStart: "",
    availabilityEnd: "",
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

interface ListingsContextValue {
  listings: Listing[];
  updateListingStatus: (id: string, status: ListingStatus) => Promise<void>;
  deleteListing: (id: string) => Promise<void>;
  publicCount: number;
  refreshListings: () => Promise<void>;
  loadError: string | null;
}

const ListingsContext = createContext<ListingsContextValue | null>(null);

function fromServer(item: SellerListingSummary): Listing {
  const status: ListingStatus = item.status === "published" ? "public" : item.status === "processing" || item.status === "ready" ? "needsReview" : item.status === "paused" ? "paused" : item.status === "expired" ? "expired" : "draft";
  return {
    id: item.id, productName: item.title, category: item.category, district: item.district,
    start: item.service_start_date ?? "", end: item.service_end_date ?? "",
    unitPrice: item.base_price?.amount_minor ?? 0, priceUnit: item.base_price?.unit ?? "기준 단가",
    quantityLabel: item.supply_quantity_description ?? "미정", status,
    method: item.creation_method === "manual" ? "write" : "upload",
    requests: item.contract_request_count, riskCount: item.attention_required_count,
    updatedAt: item.updated_at.slice(0, 10).replaceAll("-", "."),
  };
}

export function ListingsProvider({ children }: { children: ReactNode }) {
  const { currentRole } = useApp();
  const [listings, setListings] = useState<Listing[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refreshListings = async () => {
    const items = await getSellerListings();
    // 삭제는 계약 이력 보존을 위해 서버에서 archived 상태로 처리한다.
    // 보관된 공고를 임시저장으로 다시 보여 주지 않도록 관리 목록에서는 제외한다.
    setListings(items.filter((item) => item.status !== "archived").map(fromServer));
    setLoadError(null);
  };

  useEffect(() => {
    if (currentRole !== "seller") { setListings([]); return; }
    void refreshListings().catch((error: unknown) => setLoadError(friendlyApiError(error)));
  }, [currentRole]);

  const updateListingStatus: ListingsContextValue["updateListingStatus"] = async (id, status) => {
    await changeSellerListingStatus(id, status === "public" ? "publish" : "pause");
    await refreshListings();
  };

  const deleteListing: ListingsContextValue["deleteListing"] = async (id) => {
    await changeSellerListingStatus(id, "archive");
    await refreshListings();
  };

  const value = useMemo<ListingsContextValue>(
    () => ({
      listings,
      updateListingStatus,
      deleteListing,
      publicCount: listings.filter((l) => l.status === "public").length,
      refreshListings,
      loadError,
    }),
    [listings, loadError],
  );

  return <ListingsContext.Provider value={value}>{children}</ListingsContext.Provider>;
}

export function useListings() {
  const ctx = useContext(ListingsContext);
  if (!ctx) throw new Error("useListings must be used within ListingsProvider");
  return ctx;
}
