import {
  Compass,
  Send,
  MessagesSquare,
  PenLine,
  FileCheck2,
  UserRound,
  LayoutDashboard,
  Megaphone,
  Inbox,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "../context/AppContext";

export interface NavItem {
  labelKey: string;
  path: string;
  icon: LucideIcon;
}

export const buyerNav: NavItem[] = [
  { labelKey: "nav.buyer.explore", path: "/buyer/explore", icon: Compass },
  { labelKey: "nav.buyer.sent", path: "/buyer/sent", icon: Send },
  { labelKey: "nav.negotiating", path: "/buyer/negotiating", icon: MessagesSquare },
  { labelKey: "nav.signing", path: "/buyer/signing", icon: PenLine },
  { labelKey: "nav.contracts", path: "/buyer/contracts", icon: FileCheck2 },
  { labelKey: "nav.mypage", path: "/buyer/mypage", icon: UserRound },
];

export const sellerNav: NavItem[] = [
  { labelKey: "nav.seller.dashboard", path: "/seller/dashboard", icon: LayoutDashboard },
  { labelKey: "nav.seller.listings", path: "/seller/listings", icon: Megaphone },
  { labelKey: "nav.seller.received", path: "/seller/received", icon: Inbox },
  { labelKey: "nav.negotiating", path: "/seller/negotiating", icon: MessagesSquare },
  { labelKey: "nav.signing", path: "/seller/signing", icon: PenLine },
  { labelKey: "nav.contracts", path: "/seller/contracts", icon: FileCheck2 },
  { labelKey: "nav.mypage", path: "/seller/mypage", icon: UserRound },
];

export function navForRole(role: Role): NavItem[] {
  return role === "buyer" ? buyerNav : sellerNav;
}
