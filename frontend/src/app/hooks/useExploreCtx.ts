import { useLocation } from "react-router";

/**
 * Explore flow can be viewed by a logged-in buyer (under /buyer/*)
 * or by a guest (under /explore/*). This derives the link base + guest flag.
 */
export function useExploreCtx() {
  const { pathname } = useLocation();
  const isGuest = !pathname.startsWith("/buyer");
  const base = isGuest ? "/explore" : "/buyer/explore";
  return { isGuest, base };
}
