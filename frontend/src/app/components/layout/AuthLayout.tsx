import { Globe, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
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

export function AuthLayout({ children }: { children: ReactNode }) {
  const { lang, setLang, t } = useApp();

  return (
    <div className="flex min-h-screen" style={{ background: "var(--surface)" }}>
      {/* Left brand panel */}
      <div
        className="relative hidden w-[45%] flex-col justify-between overflow-hidden p-12 lg:flex"
        style={{ background: "linear-gradient(160deg, var(--navy) 0%, var(--ocean) 100%)" }}
      >
        <Link to="/explore" aria-label={t("auth.exploreHome")} className="w-fit rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
          <Logo />
        </Link>
        <div className="text-white">
          <div style={{ fontSize: "30px", fontWeight: 700, lineHeight: 1.35 }}>
            {t("auth.heroTitle").split("\n")[0]}
            <br />
            {t("auth.heroTitle").split("\n")[1]}
          </div>
          <p className="mt-4 max-w-md" style={{ color: "rgba(255,255,255,0.85)" }}>
            {t("auth.heroDescription")}
          </p>
        </div>
        <div style={{ color: "rgba(255,255,255,0.7)", fontSize: "12px" }}>
          {t("brand.tagline")}
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between px-4 py-3 sm:px-6 sm:py-4">
          <div className="lg:hidden">
            <Link to="/explore" aria-label={t("auth.exploreHome")} className="rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <Logo />
            </Link>
          </div>
          <div className="ml-auto">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="gap-1 whitespace-nowrap">
                  <Globe className="size-4" />
                  <span>{LANGUAGES.find((l) => l.code === lang)?.label}</span>
                  <ChevronDown className="size-3.5 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuRadioGroup value={lang} onValueChange={(v) => setLang(v as Lang)}>
                  {LANGUAGES.map((l) => (
                    <DropdownMenuRadioItem key={l.code} value={l.code}>
                      {l.label}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="flex flex-1 items-start justify-center px-4 pb-8 pt-4 sm:items-center sm:px-6 sm:pb-16 sm:pt-0">
          <div className="w-full max-w-[400px]">{children}</div>
        </div>
      </div>
    </div>
  );
}
