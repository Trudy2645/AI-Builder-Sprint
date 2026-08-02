import { ApiError, apiFetch } from "./api";

export type ListingCategory = "vehicle_rental" | "activity" | "tour" | "accommodation";
export type ListingStatus = "draft" | "processing" | "ready" | "published" | "paused" | "expired" | "archived";

function sellerHeaders(organizationId: string, idempotent = false): HeadersInit {
  return {
    "X-Organization-Id": organizationId,
    ...(idempotent ? { "Idempotency-Key": crypto.randomUUID() } : {}),
  };
}

export type SellerListingCreated = { listing_id: string; status: "draft"; version_no: number };

export type SellerListingSummary = {
  id: string;
  title: string;
  display_title: string | null;
  category: ListingCategory;
  district: string;
  status: ListingStatus;
  creation_method: "manual" | "upload";
  public_headline: string | null;
  service_start_date: string | null;
  service_end_date: string | null;
  supply_quantity_description: string | null;
  base_price: { amount_minor: number; currency: string; unit: string | null } | null;
  attention_required_count: number;
  current_version_no: number;
  contract_request_count: number;
  updated_at: string;
};

export type ListingTerms = {
  service_start_date?: string | null;
  service_end_date?: string | null;
  supply_quantity?: number | null;
  supply_quantity_description?: string | null;
  quantity_unit?: string | null;
  minimum_quantity?: number | null;
  maximum_quantity?: number | null;
  base_price_amount_minor?: number | null;
  currency?: string | null;
  price_unit?: string | null;
  minimum_people?: number | null;
  maximum_people?: number | null;
  cancellation_policy?: string | null;
  no_show_policy?: string | null;
  refund_policy?: string | null;
  settlement_policy?: string | null;
  safety_policy?: string | null;
  compensation_policy?: string | null;
  liability_policy?: string | null;
  termination_policy?: string | null;
  special_terms?: string | null;
};

export type GeneratedClause = {
  id: string;
  clause_order: number;
  clause_key: string;
  title: string;
  body: string;
};

export type ContractGeneration = {
  listing_id: string;
  job_id: string;
  listing_version_id: string;
  version_no: number;
  status: "ready";
  clauses: GeneratedClause[];
};

export type AIJob = {
  id: string;
  task_type: string;
  status: "queued" | "processing" | "succeeded" | "failed";
  progress: number;
  result_resource_type: string | null;
  result_resource_id: string | null;
  failure_code: string | null;
};

export type ReviewFinding = {
  id: string;
  clause_id: string | null;
  category: string;
  severity: "high" | "medium" | "low" | "none";
  importance: "high" | "medium" | "low";
  title: string;
  explanation: string;
  suggested_text: string | null;
  suggested_text_hash: string | null;
  grounding_status: "grounded" | "insufficient_evidence" | "not_required";
  disclaimer: string;
};

export type ReviewRun = {
  id: string;
  status: AIJob["status"];
  target_id: string;
  findings: ReviewFinding[];
};

export function listSellerListings(organizationId: string): Promise<SellerListingSummary[]> {
  return apiFetch<SellerListingSummary[]>("/seller/listings", { headers: sellerHeaders(organizationId) });
}

export function createSellerListing(
  organizationId: string,
  payload: { creation_method: "manual" | "upload"; title: string; category: ListingCategory; district: string; language: "ko-KR" },
): Promise<SellerListingCreated> {
  return apiFetch<SellerListingCreated>("/seller/listings", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...sellerHeaders(organizationId, true) },
    body: JSON.stringify(payload),
  });
}

export function saveSellerListingTerms(
  organizationId: string,
  listingId: string,
  baseVersionNo: number,
  terms: ListingTerms,
): Promise<{ current_version: { id: string; version_no: number } }> {
  return apiFetch<{ current_version: { id: string; version_no: number } }>(`/seller/listings/${listingId}/terms`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...sellerHeaders(organizationId) },
    body: JSON.stringify({ base_version_no: baseVersionNo, terms }),
  });
}

export function generateSellerContract(
  organizationId: string,
  listingId: string,
  baseVersionNo: number,
): Promise<ContractGeneration> {
  return apiFetch<ContractGeneration>(`/seller/listings/${listingId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...sellerHeaders(organizationId, true) },
    body: JSON.stringify({ base_version_no: baseVersionNo }),
  });
}

export function startSellerReview(
  organizationId: string,
  listingId: string,
  versionId: string,
  viewerRole: "seller" | "buyer" = "seller",
): Promise<{ job_id: string; status: AIJob["status"] }> {
  return apiFetch<{ job_id: string; status: AIJob["status"] }>(`/seller/listings/${listingId}/analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...sellerHeaders(organizationId, true) },
    body: JSON.stringify({ version_id: versionId, viewer_role: viewerRole, analysis_types: ["risk", "missing_terms"] }),
  });
}

export function getAIJob(organizationId: string, jobId: string): Promise<AIJob> {
  return apiFetch<AIJob>(`/ai-jobs/${jobId}`, { headers: sellerHeaders(organizationId) });
}

export async function waitForAIJob(organizationId: string, jobId: string): Promise<AIJob> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const job = await getAIJob(organizationId, jobId);
    if (job.status === "succeeded") return job;
    if (job.status === "failed") {
      throw new ApiError({ code: job.failure_code ?? "AI_PROCESSING_FAILED", message: "AI 작업을 완료하지 못했습니다." });
    }
    await new Promise((resolve) => window.setTimeout(resolve, 800));
  }
  throw new ApiError({ code: "AI_JOB_TIMEOUT", message: "AI 작업 대기 시간이 초과되었습니다." });
}

export function getReviewRun(organizationId: string, runId: string): Promise<ReviewRun> {
  return apiFetch<ReviewRun>(`/ai-analysis-runs/${runId}`, { headers: sellerHeaders(organizationId) });
}

export async function reviewSellerContract(
  organizationId: string,
  listingId: string,
  versionId: string,
): Promise<ReviewRun> {
  const [sellerAccepted, buyerAccepted] = await Promise.all([
    startSellerReview(organizationId, listingId, versionId, "seller"),
    startSellerReview(organizationId, listingId, versionId, "buyer"),
  ]);
  const [sellerJob] = await Promise.all([
    waitForAIJob(organizationId, sellerAccepted.job_id),
    waitForAIJob(organizationId, buyerAccepted.job_id),
  ]);
  if (!sellerJob.result_resource_id) {
    throw new ApiError({ code: "AI_RESULT_MISSING", message: "AI 분석 결과를 찾을 수 없습니다." });
  }
  return getReviewRun(organizationId, sellerJob.result_resource_id);
}

export function updateSellerPresentation(
  organizationId: string,
  listingId: string,
  publicHeadline: string,
): Promise<unknown> {
  return apiFetch(`/seller/listings/${listingId}/presentation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...sellerHeaders(organizationId) },
    body: JSON.stringify({ public_headline: publicHeadline || null }),
  });
}

export function completeSellerListing(organizationId: string, listingId: string): Promise<unknown> {
  return apiFetch(`/seller/listings/${listingId}/complete`, { method: "POST", headers: sellerHeaders(organizationId) });
}

export function publishSellerListing(organizationId: string, listingId: string): Promise<unknown> {
  return apiFetch(`/seller/listings/${listingId}/publish`, { method: "POST", headers: sellerHeaders(organizationId) });
}

export type DocumentProcessingResult = {
  document_id: string;
  status: "processing" | "ready" | "failed";
  listing_candidate: { terms?: ListingTerms } | null;
  confirmation_required: string[];
  validation_warnings: string[];
  failure_code: string | null;
};

export async function uploadAndProcessDocument(
  organizationId: string,
  listingId: string,
  file: File,
): Promise<DocumentProcessingResult> {
  const extension = file.name.split(".").pop()?.toLowerCase();
  const mimeType = file.type || ({
    pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
  } as Record<string, string>)[extension ?? ""] || "application/octet-stream";
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const contentSha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  const upload = await apiFetch<{ document: { id: string }; upload_url: string; method: string }>("/documents/upload-url", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...sellerHeaders(organizationId, true) },
    body: JSON.stringify({
      listing_id: listingId,
      purpose: "source_contract",
      original_filename: file.name,
      mime_type: mimeType,
      size_bytes: file.size,
      content_sha256: contentSha256,
    }),
  });
  const uploaded = await fetch(upload.upload_url, { method: upload.method, headers: { "Content-Type": mimeType }, body: file });
  if (!uploaded.ok) throw new ApiError({ code: "STORAGE_UPLOAD_FAILED", message: "계약서 파일 업로드에 실패했습니다." });
  await apiFetch(`/documents/${upload.document.id}/complete`, { method: "POST", headers: sellerHeaders(organizationId) });
  const accepted = await apiFetch<{ job_id: string }>(`/documents/${upload.document.id}/process`, {
    method: "POST",
    headers: sellerHeaders(organizationId, true),
  });
  await waitForAIJob(organizationId, accepted.job_id);
  const result = await apiFetch<DocumentProcessingResult>(`/documents/${upload.document.id}/processing-result`, {
    headers: sellerHeaders(organizationId),
  });
  if (result.status === "failed") {
    throw new ApiError({ code: result.failure_code ?? "AI_PROCESSING_FAILED", message: "계약서 분석에 실패했습니다." });
  }
  return result;
}
