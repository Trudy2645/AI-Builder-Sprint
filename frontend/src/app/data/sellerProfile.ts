// Demo seller (공급사) profile. Business registration number is masked in the UI.
export interface SellerProfile {
  company: string;
  bizNo: string; // 사업자등록번호 (원본, UI에서는 마스킹 표시)
  ceoName: string; // 대표자
  contactName: string; // 담당자
  email: string;
  phone: string;
  address: string;
  supplyFields: string; // 공급 분야
  joinedAt: string;
}

export const sellerProfile: SellerProfile = {
  company: "해운대 오션스테이",
  bizNo: "617-81-20260",
  ceoName: "김민수",
  contactName: "이서연 (계약 담당)",
  email: "contract@oceanstay.co.kr",
  phone: "051-740-2026",
  address: "부산광역시 해운대구 해운대해변로 264",
  supplyFields: "숙박 · 패키지",
  joinedAt: "2025.11.02",
};

/** 사업자등록번호 마스킹: 617-81-20260 -> 617-81-2****0 */
export function maskBizNo(bizNo: string): string {
  const parts = bizNo.split("-");
  if (parts.length !== 3) return bizNo;
  const [a, b, c] = parts;
  if (c.length <= 2) return `${a}-${b}-${c}`;
  const visibleStart = c.slice(0, 1);
  const visibleEnd = c.slice(-1);
  const masked = "*".repeat(Math.max(c.length - 2, 0));
  return `${a}-${b}-${visibleStart}${masked}${visibleEnd}`;
}
