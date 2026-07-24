// Design-token hex values for places Tailwind classes can't reach
// (Recharts props, leaflet markers). Keep in sync with @theme in
// app/globals.css. Palette v2: data encoding is the teal family.
export const LEAF = "#1FA890";
// Brighter accent of the data teal — reserved for singling one mark out
// of a series
export const LEAF_BRIGHT = "#25C9A5";
// Slightly deepened LEAF for thin/subordinate strokes — 3.34:1 on white,
// where LEAF (2.97:1) falls just short of the 3:1 non-text minimum
export const LEAF_DARK = "#189E87";
export const LEAF_MID = "#5FD4BE";
export const LEAF_SOFT = "#A5E7D8";
export const LEAF_PALE = "#DDF5EE";
// Caption tier — keep ≥4.5:1 on cream/white (WCAG AA)
export const SAND = "#96633F";
// Axis tick ink — SAND was too low-contrast for chart labels
export const AXIS = "#7A3A22";
export const LINE = "#F2E7DA";
export const INK = "#4A2410";

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
