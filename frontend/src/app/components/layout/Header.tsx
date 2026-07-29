import { Bell, HelpCircle, Globe, ChevronDown, LogOut, ArrowLeftRight, PanelLeftClose, PanelLeftOpen } from "lucide-react";
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
  const directCompletion = requests.find((request) => request.type === "asis" && request.status === "completed");
  // 셀러는 수정 요청과 조건 그대로 체결 완료 알림을 확인한다.
  const sellerNotif = role === "seller";

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
                  onClick={() => navigate("/seller/received/rcv-summer")}
                >
                  <span style={{ fontSize: "13px", lineHeight: 1.5 }}>
                    {t("notif.revision")
                      .replace("{buyer}", "GlobalTrip Japan")
                      .replace("{title}", "2026 부산 여름 패키지 객실 공급 계약")
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
                  {companyName.slice(0, 2).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <span className="hidden max-w-[140px] truncate whitespace-nowrap md:inline">{companyName}</span>
              <ChevronDown className="hidden size-3.5 opacity-60 sm:block" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col">
              <span className="truncate">{companyName}</span>
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
