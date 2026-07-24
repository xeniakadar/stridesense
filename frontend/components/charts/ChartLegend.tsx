"use client";

export interface LegendItem {
  label: string;
  color: string;
  /** "line" (default) renders a short stroke, "dot" a filled circle,
   * "band" a translucent block matching a shaded ReferenceArea,
   * "square" a solid block for bar series. */
  shape?: "line" | "dot" | "band" | "square";
  dashed?: boolean;
}

/** Compact legend row for any multi-series or banded chart — those must
 * always carry one. Rendered below the plot, outside Recharts, so every
 * chart type gets the identical treatment. */
export function ChartLegend({ items }: { items: LegendItem[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 px-1">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          {item.shape === "dot" ? (
            <span
              className="w-[9px] h-[9px] rounded-full border-2 border-white shadow-[0_0_0_1px_rgba(0,0,0,0.06)]"
              style={{ background: item.color }}
            />
          ) : item.shape === "band" ? (
            <span
              className="w-[14px] h-[9px] rounded-[3px]"
              style={{ background: item.color, opacity: 0.25 }}
            />
          ) : item.shape === "square" ? (
            <span
              className="w-[11px] h-[11px] rounded-[3px]"
              style={{ background: item.color }}
            />
          ) : (
            <span
              className="w-[14px] border-t-2"
              style={{
                borderColor: item.color,
                borderTopStyle: item.dashed ? "dashed" : "solid",
              }}
            />
          )}
          <span className="text-[11px] text-sand">{item.label}</span>
        </span>
      ))}
    </div>
  );
}
