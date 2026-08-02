import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApp } from "../context/AppContext";
import { archiveSellerListing, getSellerListings, pauseSellerListing, publishSellerListing, type SellerListingSummary } from "../lib/api";
import type { Category } from "../lib/catalog";

export type ListingStatus = "draft" | "needsReview" | "public" | "paused" | "expired";
export type CreateMethod = "write" | "upload";

export interface Listing {
  id: string;
  productName: string;
  category: Category;
  district: string;
  start: string;
  end: string;
  unitPrice: number;
  priceUnit: string;
  quantityLabel: string;
  status: ListingStatus;
  method: CreateMethod;
  requests: number;
  updatedAt: string;
  riskCount: number;
}

export interface ListingDraft {
  method: CreateMethod;
  productName: string;
  category: Category | "";
  district: string;
  availabilityStart: string;
  availabilityEnd: string;
  start: string;
  end: string;
  quantity: string;
  unitPrice: string;
  priceUnit: string;
  minQty: string;
  maxQty: string;
  cancellation: string;
  noShow: string;
  settlement: string;
  liability: string;
  termination: string;
  special: string;
  headline: string;
  imageUrl: string;
  available: boolean;
  showRisk: boolean;
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

export function draftToListing(
  draft: ListingDraft,
  status: ListingStatus,
  riskCount: number,
): Omit<Listing, "id" | "updatedAt"> {
  return {
    productName: draft.productName || "제목 없는 공고",
    category: (draft.category || "accommodation") as Category,
    district: draft.district || "부산",
    start: draft.availabilityStart,
    end: draft.availabilityEnd,
    unitPrice: Number.parseInt(draft.unitPrice, 10) || 0,
    priceUnit: draft.priceUnit,
    quantityLabel: draft.quantity || "미정",
    status,
    method: draft.method,
    requests: 0,
    riskCount,
  };
}

function listingStatus(status: SellerListingSummary["status"]): ListingStatus {
  if (status === "published") return "public";
  if (status === "ready" || status === "processing") return "needsReview";
  return status === "paused" ? "paused" : status === "expired" ? "expired" : "draft";
}

function dateLabel(value: string | null): string {
  return value ? value.replace(/-/g, ".").slice(0, 10) : "";
}

function fromServerListing(item: SellerListingSummary): Listing {
  return {
    id: item.id,
    productName: item.display_title ?? item.title,
    category: item.category,
    district: item.district,
    start: dateLabel(item.service_start_date),
    end: dateLabel(item.service_end_date),
    unitPrice: item.base_price?.amount_minor ?? 0,
    priceUnit: item.base_price?.unit ?? "기준 단가",
    quantityLabel: item.supply_quantity_description ?? "미정",
    status: listingStatus(item.status),
    method: item.creation_method,
    requests: item.contract_request_count,
    updatedAt: dateLabel(item.updated_at),
    riskCount: item.attention_required_count,
  };
}

interface ListingsContextValue {
  listings: Listing[];
  refreshListings: () => Promise<void>;
  addListing: (_listing: Omit<Listing, "id" | "updatedAt">) => void;
  updateListingStatus: (id: string, status: ListingStatus) => Promise<void>;
  deleteListing: (id: string) => Promise<void>;
  publicCount: number;
}

const ListingsContext = createContext<ListingsContextValue | null>(null);

export function ListingsProvider({ children }: { children: ReactNode }) {
  const { currentRole } = useApp();
  const [listings, setListings] = useState<Listing[]>([]);

  const refreshListings = useCallback(async () => {
    if (currentRole !== "seller") {
      setListings([]);
      return;
    }
    const items = await getSellerListings();
    setListings(items.map(fromServerListing));
  }, [currentRole]);

  useEffect(() => {
    let active = true;
    if (currentRole !== "seller") {
      setListings([]);
      return () => { active = false; };
    }
    getSellerListings()
      .then((items) => { if (active) setListings(items.map(fromServerListing)); })
      .catch(() => { if (active) setListings([]); });
    return () => { active = false; };
  }, [currentRole]);

  const addListing = useCallback(() => {
    void refreshListings();
  }, [refreshListings]);

  const updateListingStatus = useCallback(async (id: string, status: ListingStatus) => {
    if (status === "public") await publishSellerListing(id);
    else if (status === "paused") await pauseSellerListing(id);
    else return;
    await refreshListings();
  }, [refreshListings]);

  const deleteListing = useCallback(async (id: string) => {
    await archiveSellerListing(id);
    await refreshListings();
  }, [refreshListings]);

  const value = useMemo<ListingsContextValue>(() => ({
    listings,
    refreshListings,
    addListing,
    updateListingStatus,
    deleteListing,
    publicCount: listings.filter((listing) => listing.status === "public").length,
  }), [listings, refreshListings, addListing, updateListingStatus, deleteListing]);

  return <ListingsContext.Provider value={value}>{children}</ListingsContext.Provider>;
}

export function useListings() {
  const context = useContext(ListingsContext);
  if (!context) throw new Error("useListings must be used within ListingsProvider");
  return context;
}
