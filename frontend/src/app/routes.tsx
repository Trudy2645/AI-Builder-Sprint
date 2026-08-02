import type { ReactNode } from "react";
import { createBrowserRouter, Navigate, useLocation } from "react-router";
import { AppShell } from "./components/layout/AppShell";
import { LoginPage } from "./pages/auth/LoginPage";
import { RoleSelectPage } from "./pages/auth/RoleSelectPage";
import { BuyerSignupPage } from "./pages/auth/BuyerSignupPage";
import { SellerSignupPage } from "./pages/auth/SellerSignupPage";
import { SignupCompletePage } from "./pages/auth/SignupCompletePage";
import { GuestLayout } from "./components/layout/GuestLayout";
import { ExplorePage } from "./pages/explore/ExplorePage";
import { ContractSummaryPage } from "./pages/explore/ContractSummaryPage";
import { ContractDocumentPage } from "./pages/explore/ContractDocumentPage";
import { RequestAsIsPage } from "./pages/requests/RequestAsIsPage";
import { RevisionRequestPage } from "./pages/requests/RevisionRequestPage";
import { SentRequestsPage } from "./pages/requests/SentRequestsPage";
import { BuyerMyPage } from "./pages/BuyerMyPage";
import { SellerDashboardPage } from "./pages/seller/SellerDashboardPage";
import { ListingsManagePage } from "./pages/seller/ListingsManagePage";
import { CreateMethodPage } from "./pages/seller/CreateMethodPage";
import { UploadOcrPage } from "./pages/seller/UploadOcrPage";
import { WriteContractPage } from "./pages/seller/WriteContractPage";
import { ReceivedRequestsPage } from "./pages/seller/ReceivedRequestsPage";
import { RevisionReviewPage } from "./pages/seller/RevisionReviewPage";
import { VersionComparePage } from "./pages/negotiation/VersionComparePage";
import { FinalApprovePage } from "./pages/negotiation/FinalApprovePage";
import { ESignaturePage } from "./pages/negotiation/ESignaturePage";
import { CompletionPage } from "./pages/negotiation/CompletionPage";
import { NegotiatingPage } from "./pages/negotiation/NegotiatingPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { buyerNav, sellerNav } from "./config/nav";
import { useApp, type Role } from "./context/AppContext";

function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { currentRole } = useApp();
  const location = useLocation();

  if (!currentRole) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (currentRole !== role) {
    return <Navigate to={`/${currentRole}`} replace />;
  }
  return <>{children}</>;
}

// Buyer explore + request flow routes (logged-in buyer only).
const buyerExploreRoutes = [
  { path: "explore", element: <ExplorePage /> },
  { path: "explore/:id", element: <ContractSummaryPage /> },
  { path: "explore/:id/document", element: <ContractDocumentPage /> },
  { path: "explore/:id/request", element: <RequestAsIsPage /> },
  { path: "explore/:id/revise", element: <RevisionRequestPage /> },
];

const buyerNegotiationRoutes = [
  { path: "negotiating", element: <NegotiatingPage /> },
];

// Shared final-negotiation → signing → completion flow (buyer & seller).
// Mounted under both /buyer and /seller; pages detect the role from the URL.
const signingRoutes = [
  { path: "signing", element: <FinalApprovePage /> },
  { path: "signing/compare", element: <VersionComparePage /> },
  { path: "signing/sign", element: <ESignaturePage /> },
  { path: "signing/complete", element: <CompletionPage /> },
];

// Buyer nav items that now have dedicated pages instead of placeholders.
const buyerRealPages: Record<string, ReactNode> = {
  "/buyer/sent": <SentRequestsPage />,
  "/buyer/mypage": <BuyerMyPage />,
};

// Build child routes from the nav config so sidebar and routing stay in sync.
// The "계약 탐색" item is handled by the dedicated explore routes above.
const buyerChildren = buyerNav
  .filter(
    (item) =>
      item.path !== "/buyer/explore" &&
      item.path !== "/buyer/negotiating" &&
      item.path !== "/buyer/signing",
  )
  .map((item) => ({
    path: item.path.replace("/buyer/", ""),
    element: buyerRealPages[item.path] ?? <PlaceholderPage titleKey={item.labelKey} />,
  }));

// Seller listing creation flow (dashboard + listings + create wizards).
const sellerListingRoutes = [
  { path: "listings", element: <ListingsManagePage /> },
  { path: "listings/new", element: <CreateMethodPage /> },
  { path: "listings/new/upload", element: <UploadOcrPage /> },
  { path: "listings/new/write", element: <WriteContractPage /> },
  { path: "received", element: <ReceivedRequestsPage /> },
  { path: "received/:id", element: <RevisionReviewPage /> },
];

// Seller nav items that now have dedicated pages instead of placeholders.
const sellerRealPages: Record<string, ReactNode> = {
  "/seller/dashboard": <SellerDashboardPage />,
};

const sellerChildren = sellerNav
  .filter(
    (item) =>
      item.path !== "/seller/listings" &&
      item.path !== "/seller/listings/new" &&
      item.path !== "/seller/received" &&
      item.path !== "/seller/signing",
  )
  .map((item) => ({
    path: item.path.replace("/seller/", ""),
    element: sellerRealPages[item.path] ?? <PlaceholderPage titleKey={item.labelKey} />,
  }));

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/explore" replace /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <RoleSelectPage /> },
  { path: "/signup/buyer", element: <BuyerSignupPage /> },
  { path: "/signup/seller", element: <SellerSignupPage /> },
  { path: "/signup/complete", element: <SignupCompletePage /> },
  {
    // Public guest explore flow — no role sidebar.
    path: "/explore",
    element: <GuestLayout />,
    children: [
      { index: true, element: <ExplorePage /> },
      { path: ":id", element: <ContractSummaryPage /> },
      { path: ":id/document", element: <ContractDocumentPage /> },
    ],
  },
  {
    path: "/buyer",
    element: <RequireRole role="buyer"><AppShell role="buyer" /></RequireRole>,
    children: [
      { index: true, element: <Navigate to="/buyer/explore" replace /> },
      ...buyerExploreRoutes,
      ...buyerNegotiationRoutes,
      ...signingRoutes,
      ...buyerChildren,
    ],
  },
  {
    path: "/seller",
    element: <RequireRole role="seller"><AppShell role="seller" /></RequireRole>,
    children: [
      { index: true, element: <Navigate to="/seller/dashboard" replace /> },
      ...sellerListingRoutes,
      ...signingRoutes,
      ...sellerChildren,
    ],
  },
  { path: "*", element: <Navigate to="/explore" replace /> },
]);
