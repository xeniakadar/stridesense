"use client";

import { Activity, BarChart3, Home, MessageCircle } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

// Trends and Ask are anchored sections on the dashboard, not routes —
// the bottom nav is a lens on existing pages, not new navigation.
const TABS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/runs", label: "Runs", icon: Activity },
  { href: "/#trends", label: "Trends", icon: BarChart3 },
  { href: "/#ask", label: "Ask", icon: MessageCircle },
] as const;

export function BottomNav() {
  const pathname = usePathname();
  const [hash, setHash] = useState("");

  useEffect(() => {
    const update = () => setHash(window.location.hash);
    update();
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, [pathname]);

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/" && !hash;
    if (href.startsWith("/#")) return pathname === "/" && hash === href.slice(1);
    return pathname.startsWith(href);
  }

  return (
    <nav
      aria-label="Primary"
      className="fixed bottom-0 inset-x-0 z-20 border-t-[0.5px] border-line bg-white/90 backdrop-blur-sm"
    >
      <div className="max-w-md mx-auto flex justify-around px-2 pt-2.5 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        {TABS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            aria-label={label}
            onClick={() => setHash(href.startsWith("/#") ? href.slice(1) : "")}
            className={isActive(href) ? "text-leaf" : "text-nav-idle"}
          >
            <Icon size={21} strokeWidth={1.75} />
          </Link>
        ))}
      </div>
    </nav>
  );
}
