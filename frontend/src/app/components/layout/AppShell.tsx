import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import type { Role } from "../../context/AppContext";

export function AppShell({ role }: { role: Role }) {
  const { pathname } = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = window.localStorage.getItem("busan-link-sidebar-open");
    if (window.innerWidth < 1024) return false;
    if (saved !== null) return saved === "true";
    return true;
  });

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0, left: 0, behavior: "auto" });
    if (window.innerWidth < 1024) setSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    window.localStorage.setItem("busan-link-sidebar-open", String(sidebarOpen));
  }, [sidebarOpen]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-surface" style={{ background: "var(--surface)" }}>
      <Header
        role={role}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
      />
      <div className="flex min-h-0 flex-1">
        {sidebarOpen && (
          <button
            type="button"
            aria-label="사이드바 닫기"
            className="fixed inset-x-0 bottom-0 top-14 z-30 bg-black/30 sm:top-16 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <Sidebar role={role} open={sidebarOpen} onNavigate={() => {
          if (window.innerWidth < 1024) setSidebarOpen(false);
        }} />
        <main ref={mainRef} className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1320px] px-4 py-5 sm:px-5 md:px-6 md:py-6 lg:px-8 lg:py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
