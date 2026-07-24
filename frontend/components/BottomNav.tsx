"use client";

import { Activity, BarChart3, Home, MessageCircle } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/runs", label: "Runs", icon: Activity },
  { href: "/trends", label: "Trends", icon: BarChart3 },
  { href: "/ask", label: "Coach", icon: MessageCircle },
] as const;

export function BottomNav() {
  const pathname = usePathname();

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
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
            className={`tap-target flex flex-col items-center gap-0.5 ${
              isActive(href) ? "text-leaf" : "text-nav-idle"
            }`}
          >
            <Icon size={21} strokeWidth={1.75} />
            <span className="text-[10px] leading-none">{label}</span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
