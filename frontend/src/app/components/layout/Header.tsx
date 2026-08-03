import { useState } from "react";
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
import { useListings } from "../../store/ListingsContext";
import { receivedRequests } from "../../data/receivedRequests";

type CalendarItem = {
  id: string;
  title: string;
  partner: string;
  date: string;
  endDate?: string;
  status: "completed" | "signing" | "supply";
  tone: string;
};

type DateParts = { year: number; month: number; day: number };

function extractDateParts(text: string): DateParts[] {
  const matches = text.matchAll(/(\d{4})[.-](\d{1,2})[.-](\d{1,2})/g);
  return Array.from(matches, (match) => ({
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
  }));
}

function toDate(parts: DateParts): Date {
  return new Date(parts.year, parts.month - 1, parts.day);
}

function formatMonth(year: number, month: number): string {
  return `${year}.${String(month).padStart(2, "0")}`;
}

export function Header({
  role,
  sidebarOpen,
  onToggleSidebar,
}: {
  role: Role;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}) {
  const { lang, setLang, t, companyName, login, logout } = useApp();
  const navigate = useNavigate();
  const otherRole: Role = role === "buyer" ? "seller" : "buyer";
  const roleLabel = t(role === "buyer" ? "role.buyer" : "role.seller");
  const homePath = role === "buyer" ? "/buyer/explore" : "/seller/dashboard";
  const { requests } = useRequests();
  const { listings } = useListings();
  const [calendarYear, setCalendarYear] = useState(2026);
  const [calendarMonth, setCalendarMonth] = useState(7);
  const [showMonthPicker, setShowMonthPicker] = useState(false);
  const directCompletion = requests.find((request) => request.type === "asis" && request.status === "completed");
  const contractItems: CalendarItem[] = role === "buyer"
    ? requests
        .filter((request) => request.status === "completed" || request.status === "signing")
        .map((request) => ({
          id: request.id,
          title: request.title,
          partner: request.seller,
          date: request.createdAt,
          status: request.status === "completed" ? "completed" : "signing",
          tone: request.status === "completed" ? "var(--success)" : "var(--warning)",
        }))
    : [
        ...receivedRequests
          .filter((request) => request.status === "signed" || request.status === "signing")
          .map((request) => ({
            id: request.id,
            title: request.contractTitle,
            partner: request.buyer,
            date: request.period,
            status: request.status === "signed" ? "completed" : "signing",
            tone: request.status === "signed" ? "var(--success)" : "var(--warning)",
          })),
        ...(directCompletion
          ? [{
              id: directCompletion.id,
              title: directCompletion.title,
              partner: "GlobalTrip Japan",
              date: directCompletion.createdAt,
              status: "completed",
              tone: "var(--success)",
            }]
          : []),
      ];
  const supplyItems: CalendarItem[] = role === "seller"
    ? listings
        .filter((listing) => listing.start && listing.end && listing.status !== "expired")
        .map((listing) => ({
          id: `supply-${listing.id}`,
          title: listing.productName,
          partner: "공고 공급 기간",
          date: listing.start,
          endDate: listing.end,
          status: "supply" as const,
          tone: "var(--ocean)",
        }))
    : [];
  const calendarItems: CalendarItem[] = [...contractItems, ...supplyItems];
  const calendarPath = role === "buyer" ? "/buyer/contracts" : "/seller/contracts";
  const firstWeekday = new Date(calendarYear, calendarMonth - 1, 1).getDay();
  const daysInMonth = new Date(calendarYear, calendarMonth, 0).getDate();
  const cellCount = Math.ceil((firstWeekday + daysInMonth) / 7) * 7;
  const calendarDays = Array.from({ length: cellCount }, (_, index) => {
    const day = index - firstWeekday + 1;
    if (day < 1 || day > daysInMonth) return null;
    return day;
  });
  const itemDays = (item: CalendarItem) => {
    const dates = extractDateParts(item.date);
    const startParts = dates[0];
    const endParts = item.endDate ? extractDateParts(item.endDate)[0] : dates[1] ?? startParts;
    if (!startParts) return [];
    const start = toDate(startParts);
    const end = toDate(endParts ?? startParts);
    const visibleStart = new Date(calendarYear, calendarMonth - 1, 1);
    const visibleEnd = new Date(calendarYear, calendarMonth - 1, daysInMonth);
    const rangeStart = start > visibleStart ? start : visibleStart;
    const rangeEnd = end < visibleEnd ? end : visibleEnd;
    if (rangeEnd < rangeStart) return [];
    const length = Math.floor((rangeEnd.getTime() - rangeStart.getTime()) / 86400000) + 1;
    return Array.from({ length }, (_, index) => rangeStart.getDate() + index);
  };
  const itemsByDay = calendarItems.reduce<Record<number, CalendarItem[]>>((acc, item) => {
    for (const day of itemDays(item)) acc[day] = [...(acc[day] ?? []), item];
    return acc;
  }, {});
  const calendarRoleLabel = t(role === "buyer" ? "header.calendarBuyer" : "header.calendarSeller");
  // 알림 UI는 유지하되, 실제 알림 API가 연결되기 전까지 목업 알림은 노출하지 않는다.
  const sellerNotif = false;
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
            <Button variant="ghost" size="icon" aria-label={t("header.calendar")}>
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
                    <div className="text-foreground" style={{ fontSize: "15px", fontWeight: 800 }}>{t("header.calendar")}</div>
                    <div className="text-muted-foreground" style={{ fontSize: "12px", fontWeight: 500 }}>{calendarRoleLabel}</div>
                  </div>
                </div>
                <button
                  type="button"
                  className="rounded-full bg-background px-2.5 py-1 text-muted-foreground shadow-sm transition-colors hover:bg-background/80"
                  style={{ fontSize: "12px", fontWeight: 700 }}
                  onClick={(event) => {
                    event.preventDefault();
                    setShowMonthPicker((value) => !value);
                  }}
                >
                  {formatMonth(calendarYear, calendarMonth)}
                </button>
              </div>
            </DropdownMenuLabel>
            <>
                <div className="px-4 pb-3 pt-3">
                  {showMonthPicker && (
                    <div className="mb-3 grid grid-cols-[1fr_1fr] gap-2">
                      <select
                        className="h-9 rounded-lg border border-border bg-background px-2 text-sm"
                        value={calendarYear}
                        onClick={(event) => event.preventDefault()}
                        onChange={(event) => setCalendarYear(Number(event.target.value))}
                      >
                        {[2025, 2026, 2027, 2028].map((year) => <option key={year} value={year}>{year}</option>)}
                      </select>
                      <select
                        className="h-9 rounded-lg border border-border bg-background px-2 text-sm"
                        value={calendarMonth}
                        onClick={(event) => event.preventDefault()}
                        onChange={(event) => setCalendarMonth(Number(event.target.value))}
                      >
                        {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
                          <option key={month} value={month}>{String(month).padStart(2, "0")}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-muted-foreground" style={{ fontSize: "12px", fontWeight: 700 }}>{t("header.calendarEvents")}</span>
                    <span className="rounded-full px-2 py-0.5" style={{ background: "var(--success-soft)", color: "var(--success)", fontSize: "11px", fontWeight: 800 }}>
                      {calendarItems.length}건
                    </span>
                  </div>
                  {role === "seller" && (
                    <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] font-semibold text-muted-foreground">
                      <span><i className="mr-1 inline-block size-2 rounded-full" style={{ background: "var(--success)" }} />{t("header.calendarCompleted")}</span>
                      <span><i className="mr-1 inline-block size-2 rounded-full" style={{ background: "var(--warning)" }} />{t("header.calendarSigning")}</span>
                      <span><i className="mr-1 inline-block size-2 rounded-full" style={{ background: "var(--ocean)" }} />{t("header.calendarSupply")}</span>
                    </div>
                  )}
                  <div className="grid grid-cols-7 rounded-lg bg-muted/50 px-1 py-1 text-center text-muted-foreground" style={{ fontSize: "10px", fontWeight: 800 }}>
                    {["sun", "mon", "tue", "wed", "thu", "fri", "sat"].map((day) => <div key={day} className="py-1">{t(`weekday.${day}`)}</div>)}
                  </div>
                  <div className="mt-2 grid grid-cols-7 gap-1.5">
                    {calendarDays.map((day, index) => {
                      const dayItems = day ? itemsByDay[day] ?? [] : [];
                      const hasSigned = dayItems.some((item) => item.status === "completed");
                      const hasSupply = dayItems.some((item) => item.status === "supply");
                      return (
                        <button
                          key={`${day ?? "empty"}-${index}`}
                          type="button"
                          disabled={!day}
                          onClick={() => dayItems.length ? navigate(calendarPath) : undefined}
                          className="group relative flex aspect-square min-w-0 flex-col items-center justify-center rounded-xl text-center transition-colors disabled:opacity-0"
                          style={{
                            background: dayItems.length ? (hasSigned ? "var(--success-soft)" : hasSupply ? "var(--info-soft)" : "var(--warning-soft)") : "var(--muted)",
                            color: dayItems.length ? (hasSigned ? "var(--success)" : hasSupply ? "var(--ocean)" : "var(--warning)") : "var(--foreground)",
                            fontSize: "12px",
                            fontWeight: dayItems.length ? 800 : 500,
                          }}
                          aria-label={day ? `${day}일 계약 일정 ${dayItems.length}건` : undefined}
                        >
                          <span>{day}</span>
                          {dayItems.length > 0 && (
                            <span
                              className="absolute bottom-1.5 left-1/2 flex size-1.5 -translate-x-1/2 rounded-full"
                              style={{ background: hasSigned ? "var(--success)" : hasSupply ? "var(--ocean)" : "var(--warning)" }}
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                  {!calendarItems.length && (
                    <p className="mt-3 text-center text-xs font-medium text-muted-foreground">
                      {t("header.calendarEmpty")}
                    </p>
                  )}
                </div>
                {calendarItems.length > 0 && (
                  <>
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
                            <span style={{ fontSize: "10px", fontWeight: 700 }}>{String(calendarMonth).padStart(2, "0")}</span>
                            <span style={{ fontSize: "15px", fontWeight: 900 }}>{itemDays(item)[0] ?? "-"}</span>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <span className="line-clamp-1 text-foreground" style={{ fontSize: "12px", fontWeight: 800 }}>{item.title}</span>
                              <span className="shrink-0 whitespace-nowrap rounded-full px-2 py-0.5" style={{ background: item.status === "completed" ? "var(--success-soft)" : item.status === "supply" ? "var(--info-soft)" : "var(--warning-soft)", color: item.tone, fontSize: "10px", fontWeight: 800 }}>
                                {t(item.status === "completed" ? "header.calendarCompleted" : item.status === "supply" ? "header.calendarSupply" : "header.calendarSigning")}
                              </span>
                            </div>
                            <div className="mt-1 truncate text-muted-foreground" style={{ fontSize: "11px", fontWeight: 500 }}>
                              {item.status === "supply" ? t("header.calendarSupply") : item.partner}
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="mx-3 mb-3 mt-2 justify-center rounded-xl bg-primary py-2.5 text-primary-foreground focus:bg-primary/90 focus:text-primary-foreground" onClick={() => navigate(calendarPath)}>
                      {t("header.calendarViewAll")}
                    </DropdownMenuItem>
                  </>
                )}
              </>
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
              <>
                {directCompletion && (
                  <>
                    <DropdownMenuItem
                      className="flex flex-col items-start gap-1 whitespace-normal py-2.5"
                      onClick={() => navigate("/seller/contracts")}
                    >
                      <span style={{ fontSize: "13px", lineHeight: 1.5 }}>
                        {t("notif.directCompleted")
                          .replace("{buyer}", "GlobalTrip Japan")
                          .replace("{title}", directCompletion.title)}
                      </span>
                      <span className="whitespace-nowrap" style={{ color: "var(--success)", fontSize: "12px", fontWeight: 600 }}>
                        {t("notif.viewCompleted")} →
                      </span>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuItem
                  className="flex flex-col items-start gap-1 whitespace-normal py-2.5"
                  onClick={() => navigate("/seller/received/rcv-coastline")}
                >
                  <span style={{ fontSize: "13px", lineHeight: 1.5 }}>
                    {t("notif.revision")
                      .replace("{buyer}", "GlobalTrip Japan")
                      .replace("{title}", "2026 해운대 단체 객실 공급 계약")
                      .replace("{count}", "3")}
                  </span>
                  <span className="whitespace-nowrap" style={{ color: "var(--ocean)", fontSize: "12px", fontWeight: 600 }}>
                    {t("notif.viewRevision")} →
                  </span>
                </DropdownMenuItem>
              </>
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
                login(
                  otherRole,
                  otherRole === "buyer" ? "GlobalTrip Japan" : "해운대 오션스테이",
                  true,
                );
                // Let the role context commit before the route guard evaluates.
                window.setTimeout(() => navigate(`/${otherRole}`), 0);
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
