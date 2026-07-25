/** The one glass treatment for AI-generated surfaces. Variants are
 * semantic (what the surface is), not per-screen: tint and header/body
 * ink come from the variant's CSS custom properties in globals.css —
 * use .glass-header / .glass-body inside instead of hardcoding colors.
 * No component may carry its own glass gradient. */
const VARIANTS = ["brief", "insight", "ask"] as const;
export type GlassVariant = (typeof VARIANTS)[number];

export function Glass({
  variant,
  className = "",
  children,
}: {
  variant: GlassVariant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`glass glass-${variant} ${className}`}>{children}</div>
  );
}
