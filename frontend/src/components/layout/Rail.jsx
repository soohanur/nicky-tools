"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import Icon from "@/components/ui/Icon";
import { RAIL_NAV } from "@/data/nav";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

// Left icon rail: theme toggle, page navigation, help + logout.
export default function Rail() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { logout } = useAuth();

  const isActive = (href) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <aside className="rail">
      <div className="rail-theme">
        <button
          type="button"
          className={theme === "light" ? "on" : ""}
          title="Light mode"
          aria-label="Light mode"
          onClick={() => setTheme("light")}
        >
          <Icon name="sun" />
        </button>
        <button
          type="button"
          className={theme === "dark" ? "on" : ""}
          title="Dark mode"
          aria-label="Dark mode"
          onClick={() => setTheme("dark")}
        >
          <Icon name="moon" />
        </button>
      </div>

      <nav className="rail-nav" aria-label="Main">
        {RAIL_NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={isActive(item.href) ? "active" : ""}
            aria-label={item.label}
            aria-current={isActive(item.href) ? "page" : undefined}
            style={{ display: "grid" }}
          >
            <Icon name={item.icon} />
            <i className="tip">{item.label}</i>
          </Link>
        ))}
      </nav>

      <div className="rail-bottom">
        <a href="https://company.info" target="_blank" rel="noreferrer" title="company.info">
          <Icon name="globe" />
        </a>
        <a
          href="/login/"
          title="Logout"
          onClick={(e) => {
            e.preventDefault();
            logout();
            router.replace("/login/");
          }}
        >
          <Icon name="logout" />
        </a>
      </div>
    </aside>
  );
}
