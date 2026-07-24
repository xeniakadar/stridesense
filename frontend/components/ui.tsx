"use client";

import Link from "next/link";

/** The one chip style for tags ("Race", sources, statuses). Tags are
 * never bare colored text — always this shape. Tones cover the standard
 * cases; pass className for one-off palettes (e.g. import-job statuses)
 * on top of the shared shape. */
const CHIP_TONES = {
  neutral: "bg-line/70 text-clay",
  green: "bg-leaf-pale text-leaf-deep",
  accent: "bg-ember/10 text-ember",
  hero: "bg-white/55 text-clay-hero",
  custom: "", // shape only — colors supplied via className
} as const;

export function Chip({
  tone = "neutral",
  className = "",
  children,
}: {
  tone?: keyof typeof CHIP_TONES;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-medium ${CHIP_TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/** The one tertiary-link style: label + arrow in the brand deep green,
 * ≥44×44 hit area via .tap-target. Renders a Link with `href`, a button
 * with `onClick`, or a plain span with neither (for decorating a parent
 * that is itself the link, e.g. a whole-card Link). */
export function TertiaryLink({
  href,
  onClick,
  className = "",
  children,
}: {
  href?: string;
  onClick?: () => void;
  className?: string;
  children: React.ReactNode;
}) {
  const classes = `tap-target inline-flex items-center gap-1 text-[13px] font-medium text-leaf-deep ${className}`;
  const content = (
    <>
      {children}
      <span aria-hidden>→</span>
    </>
  );
  if (href) {
    return (
      <Link href={href} onClick={onClick} className={classes}>
        {content}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={classes}>
        {content}
      </button>
    );
  }
  return <span className={classes}>{content}</span>;
}
