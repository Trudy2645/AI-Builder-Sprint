import { PenLine } from "lucide-react";
import { useLocation } from "react-router";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/ui/card";
import { useApp } from "../context/AppContext";

export function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useApp();
  const { pathname } = useLocation();
  const role = pathname.startsWith("/seller") ? "셀러" : "바이어";
  return <div><PageHeader title={t(titleKey)} description={`${role} 계정의 서버 데이터가 연결되면 이 화면에서 확인할 수 있습니다.`} /><Card className="flex flex-col items-center justify-center gap-3 border-dashed p-10 text-center sm:p-16"><PenLine className="size-7" style={{ color: "var(--ocean)" }} /><p className="text-muted-foreground">표시할 서버 데이터가 없습니다.</p></Card></div>;
}
