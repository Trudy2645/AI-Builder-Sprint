import { NavLink } from "react-router";
import { navForRole } from "../../config/nav";
import { useApp, type Role } from "../../context/AppContext";

export function Sidebar({ role, open, onNavigate }: { role: Role; open: boolean; onNavigate?: () => void }) {
  const { t } = useApp();
  const items = navForRole(role);
  const roleLabel = t(role === "buyer" ? "role.buyer" : "role.seller");
  const roleDesc = t(role === "buyer" ? "role.buyer.desc" : "role.seller.desc");

  return (
    <aside
      aria-hidden={!open}
      className="fixed bottom-0 left-0 top-14 z-40 shrink-0 overflow-hidden border-border bg-card shadow-xl transition-[width] duration-200 sm:top-16 lg:static lg:z-auto lg:shadow-none"
      style={{ width: open ? "230px" : "0px", borderRightWidth: open ? "1px" : "0px" }}
    >
      <div className="flex h-full w-[230px] flex-col">
        <div className="border-b border-border px-5 py-4">
          <div className="whitespace-nowrap" style={{ fontWeight: 700, color: "var(--navy)" }}>
            {roleLabel}
          </div>
          <div className="mt-0.5 text-muted-foreground" style={{ fontSize: "12px" }}>
            {roleDesc}
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto p-3">
          <ul className="flex flex-col gap-1">
            {items.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    onClick={onNavigate}
                    tabIndex={open ? 0 : -1}
                    className={({ isActive }) =>
                      [
                        "flex items-center gap-3 rounded-md px-3 py-2 whitespace-nowrap transition-colors",
                        isActive
                          ? "text-ocean-foreground"
                          : "text-foreground hover:bg-secondary",
                      ].join(" ")
                    }
                    style={({ isActive }) =>
                      isActive ? { background: "var(--ocean)", color: "var(--ocean-foreground)" } : undefined
                    }
                  >
                    <Icon className="size-4 shrink-0" />
                    <span className="truncate" style={{ fontSize: "14px" }}>
                      {t(item.labelKey)}
                    </span>
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-border px-5 py-3 text-muted-foreground" style={{ fontSize: "11px" }}>
          © 2026 Busan Link
        </div>
      </div>
    </aside>
  );
}
