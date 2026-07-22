// Design-token hex values for places Tailwind classes can't reach
// (Recharts props). Keep in sync with @theme in app/globals.css.
export const LEAF = "#3B9C7A";
// Brighter accent of leaf — reserved for singling one mark out of a series
export const LEAF_BRIGHT = "#2FC08D";
export const LEAF_MID = "#8FD4B4";
export const LEAF_SOFT = "#B7E3CF";
export const LEAF_PALE = "#D7EFE3";
export const SAND = "#B0866A";
export const LINE = "#EFE9E0";
export const INK = "#4A2E1C";

// Shared Recharts tooltip styling
export const TOOLTIP_STYLE = {
  contentStyle: {
    background: "#FFFFFF",
    border: `0.5px solid ${LINE}`,
    borderRadius: 12,
    fontSize: 12,
    color: INK,
  },
  labelStyle: { color: SAND },
} as const;
