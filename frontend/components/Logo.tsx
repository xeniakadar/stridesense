import { outfit } from "@/lib/fonts";

/** The StrideSense lockup: stride mark + two-tone wordmark. `size` is
 * the wordmark font size in px; the mark scales with it. Weight steps up
 * to 700 at display sizes (≥24px), 600 below. The mark is decorative —
 * the wordmark text carries the name for assistive tech. */
export function Logo({
  size = 16,
  onDark = false,
}: {
  size?: number;
  onDark?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-[0.4em] ${outfit.className}`}
      style={{
        fontSize: size,
        fontWeight: size >= 24 ? 700 : 600,
        letterSpacing: "-0.01em",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- tiny static svg */}
      <img
        src="/brand/logo-mark.svg"
        alt=""
        style={{ height: size * 0.9, width: "auto" }}
      />
      <span className="leading-none">
        <span style={{ color: onDark ? "#F5EFE8" : "#38150A" }}>Stride</span>
        <span style={{ color: "#0FA98E" }}>Sense</span>
      </span>
    </span>
  );
}
