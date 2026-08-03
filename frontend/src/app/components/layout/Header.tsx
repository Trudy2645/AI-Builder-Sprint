import { Bell, CalendarDays, HelpCircle, Globe, ChevronDown, LogOut, ArrowLeftRight, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useNavigate } from "react-router";
import { Logo } from "../brand/Logo";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Avatar, AvatarFallback } from "../ui/avatar";
import { Separator } from "../ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "../ui/tooltip";
import { useApp } from "../../context/AppContext";
import { LANGUAGES, type Lang } from "../../i18n/translations";
import type { Role } from "../../context/AppContext";
import { useRequests } from "../../store/RequestsContext";
import { loginWithDemoRole } from "../../lib/api";

export function Header({
  role,
  sidebarOpen,
  onToggleSidebar,
}: {
  role: Role;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}) {
  const { lang, setLang, t, companyName, loginWithSession, logout } = useApp();
  const navigate = useNavigate();
  const otherRole: Role = role === "buyer" ? "seller" : "buyer";
  const roleLabel = t(role === "buyer" ? "role.buyer" : "role.seller");
  const homePath = role === "buyer" ? "/buyer/explore" : "/seller/dashboard";
  const { requests } = useRequests();
  const calendarItems = requests
    .filter((request) => request.status === "completed" || request.status === "signing")
    .map((request) => ({
      id: request.id,
      title: request.title,
      partner: role === "buyer" ? request.seller : request.buyer ?? "바이어",
      date: request.serviceStartDate ?? request.createdAt,
      status: request.status === "completed" ? "체결 완료" : "서명 대기",
      tone: request.status === "completed" ? "var(--success)" : "var(--warning)",
    }));
  const calendarPath = role === "buyer" ? "/buyer/contracts" : "/seller/contracts";
  const calendarDays = Array.from({ length: 35 }, (_, index) => {
    const day = index - 2;
    if (day < 1 || day > 31) return null;
    return day;
  });
  const itemDay = (date: string) => {
    const match = date.match(/2026[.-]0?7[.-](\d{1,2})/);
    return match ? Number(match[1]) : undefined;
  };
  const itemsByDay = calendarItems.reduce<Record<number, typeof calendarItems>>((acc, item) => {
    const day = itemDay(item.date);
    if (!day) return acc;
    acc[day] = [...(acc[day] ?? []), item];
    return acc;
  }, {});
  const calendarRoleLabel = role === "buyer" ? "바이어 일정" : "셀러 일정";
  // 셀러는 수정 요청과 조건 그대로 체결 완료 알림을 확인한다.
  const sellerNotif = role === "seller" && requests.some((request) => request.status === "reviewing" || request.status === "negotiating");
  const displayName = companyName || "계정 정보 없음";

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-border bg-card px-2 sm:h-16 sm:px-4 lg:px-6">
      <div className="flex min-w-0 items-center gap-1 sm:gap-2 lg:gap-4">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0"
              aria-label={sidebarOpen ? "사이드바 숨기기" : "사이드바 열기"}
              aria-expanded={sidebarOpen}
              onClick={onToggleSidebar}
            >
              {sidebarOpen ? <PanelLeftClose className="size-5" /> : <PanelLeftOpen className="size-5" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{sidebarOpen ? "사이드바 숨기기" : "사이드바 열기"}</TooltipContent>
        </Tooltip>
        <button
          type="button"
          className="shrink-0 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="첫 페이지로 이동"
          onClick={() => navigate(homePath)}
        >
          <Logo className="[&>span]:hidden sm:[&>span]:inline" />
        </button>
        <span className="hidden truncate text-muted-foreground xl:inline" style={{ fontSize: "13px" }}>
          {t("brand.tagline")}
        </span>
      </div>

      <div className="flex min-w-0 items-center gap-0.5 sm:gap-2">
        {/* Current role */}
        <Badge
          className="hidden gap-1 whitespace-nowrap border-transparent lg:inline-flex"
          style={{ background: "var(--info-soft)", color: "var(--ocean)" }}
        >
          {t("header.currentRole")}: {roleLabel}
        </Badge>

        <Separator orientation="vertical" className="mx-1 hidden h-6 sm:block" />

        {/* Language selector */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-1 whitespace-nowrap">
              <Globe className="size-4" />
              <span className="hidden xl:inline">{LANGUAGES.find((l) => l.code === lang)?.label}</span>
              <ChevronDown className="size-3.5 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{t("header.language")}</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={lang} onValueChange={(v) => setLang(v as Lang)}>
              {LANGUAGES.map((l) => (
                <DropdownMenuRadioItem key={l.code} value={l.code}>
                  {l.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Contract calendar */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="계약 일정">
              <CalendarDays className="size-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[calc(100vw-2rem)] max-w-[390px] overflow-hidden p-0">
            <DropdownMenuLabel className="p-0">
              <div className="flex items-center justify-between bg-muted/60 px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex size-10 items-center justify-center rounded-xl" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
                    <CalendarDays className="size-5" />
                  </div>
                  <div>
                    <div className="text-foreground" style={{ fontSize: "15px", fontWeight: 800 }}>계약 캘린더</div>
                    <div className="text-muted-foreground" style={{ fontSize: "12px", fontWeight: 500 }}>{calendarRoleLabel}</div>
                  </div>
                </div>
                <span className="rounded-full bg-background px-2.5 py-1 text-muted-foreground shadow-sm" style={{ fontSize: "12px", fontWeight: 700 }}>
                  2026.07
                </span>
              </div>
            </DropdownMenuLabel>
            {calendarItems.length ? (
              <>
                <div className="px-4 pb-3 pt-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-muted-foreground" style={{ fontSize: "12px", fontWeight: 700 }}>체결 및 서명 일정</span>
                    <span className="rounded-full px-2 py-0.5" style={{ background: "var(--success-soft)", color: "var(--success)", fontSize: "11px", fontWeight: 800 }}>
                      {calendarItems.length}건
                    </span>
                  </div>
                  <div className="grid grid-cols-7 rounded-lg bg-muted/50 px-1 py-1 text-center text-muted-foreground" style={{ fontSize: "10px", fontWeight: 800 }}>
                    {["일", "월", "화", "수", "목", "금", "토"].map((day) => <div key={day} className="py-1">{day}</div>)}
                  </div>
                  <div className="mt-2 grid grid-cols-7 gap-1.5">
                    {calendarDays.map((day, index) => {
                      const dayItems = day ? itemsByDay[day] ?? [] : [];
                      const hasSigned = dayItems.some((item) => item.status === "체결 완료");
                      return (
                        <button
                          key={`${day ?? "empty"}-${index}`}
                          type="button"
                          disabled={!day}
                          onClick={() => dayItems.length ? navigate(calendarPath) : undefined}
                          className="group relative flex aspect-square min-w-0 flex-col items-center justify-center rounded-xl text-center transition-colors disabled:opacity-0"
                          style={{
                            background: dayItems.length ? (hasSigned ? "var(--success-soft)" : "var(--warning-soft)") : "var(--muted)",
                            color: dayItems.length ? (hasSigned ? "var(--success)" : "var(--warning)") : "var(--foreground)",
                            fontSize: "12px",
                            fontWeight: dayItems.length ? 800 : 500,
                          }}
                          aria-label={day ? `${day}일 계약 일정 ${dayItems.length}건` : undefined}
                        >
                          <span>{day}</span>
                          {dayItems.length > 0 && (
                            <span
                              className="absolute bottom-1.5 left-1/2 flex size-1.5 -translate-x-1/2 rounded-full"
                              style={{ background: hasSigned ? "var(--success)" : "var(--warning)" }}
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <DropdownMenuSeparator />
                <div className="max-h-48 overflow-y-auto px-3 py-2">
                  {calendarItems.slice(0, 4).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="mb-2 flex w-full items-center gap-3 rounded-xl border border-border bg-background px-3 py-2.5 text-left shadow-sm transition-colors hover:bg-muted/60"
                      onClick={() => navigate(calendarPath)}
                    >
                      <div className="flex size-11 shrink-0 flex-col items-center justify-center rounded-lg" style={{ background: "var(--info-soft)", color: "var(--ocean)" }}>
                        <span style={{ fontSize: "10px", fontWeight: 700 }}>7월</span>
                        <span style={{ fontSize: "15px", fontWeight: 900 }}>{itemDay(item.date) ?? "-"}</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <span className="line-clamp-1 text-foreground" style={{ fontSize: "12px", fontWeight: 800 }}>{item.title}</span>
                          <span className="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5" style={{ background: item.status === "체결 완료" ? "var(--success-soft)" : "var(--warning-soft)", color: item.tone, fontSize: "10px", fontWeight: 800 }}>
                            {item.status}
                          </span>
                        </div>
                        <div className="mt-1 truncate text-muted-foreground" style={{ fontSize: "11px", fontWeight: 500 }}>{item.partner}</div>
                      </div>
                    </button>
                  ))}
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="mx-3 mb-3 mt-2 justify-center rounded-xl bg-primary py-2.5 text-primary-foreground focus:bg-primary/90 focus:text-primary-foreground" onClick={() => navigate(calendarPath)}>
                  전체 계약 일정 보기
                </DropdownMenuItem>
              </>
            ) : (
              <div className="px-4 py-8 text-center">
                <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
                  <CalendarDays className="size-5" />
                </div>
                <div className="text-muted-foreground" style={{ fontSize: "13px", fontWeight: 600 }}>
                  표시할 체결 계약 일정이 없습니다.
                </div>
              </div>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Notifications */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative" aria-label={t("header.notifications")}>
              <Bell className="size-5" />
              {sellerNotif && (
                <span
                  className="absolute right-1.5 top-1.5 size-2 rounded-full"
                  style={{ background: "var(--coral)" }}
                />
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[calc(100vw-2rem)] max-w-80">
            <DropdownMenuLabel>{t("notif.title")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {sellerNotif ? (
              requests.filter((request) => request.status === "reviewing" || request.status === "negotiating").slice(0, 3).map((request) => (
                <DropdownMenuItem key={request.id} className="flex flex-col items-start gap-1 whitespace-normal py-2.5" onClick={() => navigate("/seller/received")}>
                  <span style={{ fontSize: "13px", lineHeight: 1.5 }}>{request.buyer ?? "바이어"}의 계약 요청 · {request.title}</span>
                  <span className="whitespace-nowrap" style={{ color: "var(--ocean)", fontSize: "12px", fontWeight: 600 }}>요청 확인 →</span>
                </DropdownMenuItem>
              ))
            ) : (
              <div className="px-2 py-6 text-center text-muted-foreground" style={{ fontSize: "13px" }}>
                {t("notif.empty")}
              </div>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Help */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="hidden sm:inline-flex" aria-label={t("header.help")}>
              <HelpCircle className="size-5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("header.help")}</TooltipContent>
        </Tooltip>

        {/* Profile */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-1 px-1.5 sm:gap-2">
              <Avatar className="size-7">
                <AvatarFallback style={{ background: "var(--navy)", color: "#fff", fontSize: "12px" }}>
                  {displayName.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <span className="hidden max-w-[140px] truncate whitespace-nowrap md:inline">{displayName}</span>
              <ChevronDown className="hidden size-3.5 opacity-60 sm:block" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col">
              <span className="truncate">{displayName}</span>
              <span className="text-muted-foreground" style={{ fontSize: "12px", fontWeight: 400 }}>
                {roleLabel}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                void loginWithDemoRole(otherRole).then((session) => {
                  loginWithSession(session.role, session.email, session.accessToken, session.organizationId);
                  window.setTimeout(() => navigate(`/${session.role}`), 0);
                });
              }}
            >
              <ArrowLeftRight className="size-4" />
              데모 {t("header.switchRole")} → {t(otherRole === "buyer" ? "role.buyer" : "role.seller")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(`/${role}/mypage`)}>
              <HelpCircle className="size-4" />
              {t("header.profile")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                logout();
                // Let authentication state clear before leaving the protected shell.
                window.setTimeout(() => navigate("/login"), 0);
              }}
            >
              <LogOut className="size-4" />
              {t("header.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
