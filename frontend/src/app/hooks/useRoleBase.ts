import { useLocation } from "react-router";
import type { Role } from "../context/AppContext";

/**
 * 현재 URL이 /seller 로 시작하는지에 따라 역할과 기본 경로를 반환한다.
 * 바이어·셀러가 공용으로 쓰는 협상·서명·체결 화면에서 사용.
 */
export function useRoleBase(): { role: Role; base: string } {
  const { pathname } = useLocation();
  const role: Role = pathname.startsWith("/seller") ? "seller" : "buyer";
  return { role, base: `/${role}` };
}
