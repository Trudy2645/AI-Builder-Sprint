import { Globe, ChevronDown } from "lucide-react";
import { Link, Outlet, useNavigate } from "react-router";
import { Logo } from "../brand/Logo";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { useApp } from "../../context/AppContext";
import { LANGUAGES, type Lang } from "../../i18n/translations";

/** Public shell for guests browsing the explore flow — no role sidebar. */
export function GuestLayout() {
  const { lang, setLang, t } = useApp();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col" style={{ background: "var(--surface)" }}>
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card px-3 sm:h-16 sm:px-6">
        <Link to="/explore" className="flex items-center gap-3">
          <Logo />
          <span className="hidden text-muted-foreground lg:inline" style={{ fontSize: "13px" }}>
            {t("brand.tagline")}
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1 whitespace-nowrap">
                <Globe className="size-4" />
                <span className="hidden sm:inline">{LANGUAGES.find((l) => l.code === lang)?.label}</span>
                <ChevronDown className="size-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuRadioGroup value={lang} onValueChange={(v) => setLang(v as Lang)}>
                {LANGUAGES.map((l) => (
                  <DropdownMenuRadioItem key={l.code} value={l.code}>{l.label}</DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button variant="ghost" size="sm" className="whitespace-nowrap px-2 sm:px-3" onClick={() => navigate("/login")}>
            {t("common.login")}
          </Button>
          <Button size="sm" className="whitespace-nowrap px-2 sm:px-3" style={{ background: "var(--navy)" }} onClick={() => navigate("/signup")}>
            {t("common.signup")}
          </Button>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto w-full max-w-[1400px] px-4 py-5 sm:px-6 sm:py-7 lg:px-10 lg:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
