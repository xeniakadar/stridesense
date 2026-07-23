"use client";

import { ChevronDown, ChevronUp, EyeOff, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useDemoMode } from "@/components/DemoProvider";
import { buildRegistry, DEFAULT_ORDER } from "@/components/trends/blocks";
import { api } from "@/lib/api";
import type { GlucoseTrendPoint } from "@/lib/types";

// Schema-versioned: bump when the shape changes and stale configs reset
const STORAGE_KEY = "stridesense.trends.blocks.v1";

interface BlockConfig {
  order: string[]; // visible blocks, in render order
  hidden: string[];
}

function defaultConfig(registryIds: string[]): BlockConfig {
  const curated = DEFAULT_ORDER.filter((id) => registryIds.includes(id));
  const rest = registryIds.filter((id) => !curated.includes(id));
  return { order: [...curated, ...rest], hidden: [] };
}

/** Stored config against the current registry: drop ids the registry no
 * longer has, and append registry ids the config has never seen at the
 * end, visible — future blocks appear rather than vanish. */
function reconcile(stored: BlockConfig, registryIds: string[]): BlockConfig {
  const known = new Set(registryIds);
  const order = stored.order.filter((id) => known.has(id));
  const hidden = stored.hidden.filter(
    (id) => known.has(id) && !order.includes(id)
  );
  const seen = new Set([...order, ...hidden]);
  const unseen = registryIds.filter((id) => !seen.has(id));
  return { order: [...order, ...unseen], hidden };
}

function readStored(): BlockConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.order) || !Array.isArray(parsed.hidden)) {
      return null;
    }
    return { order: parsed.order, hidden: parsed.hidden };
  } catch {
    return null;
  }
}

export default function TrendsPage() {
  const demoMode = useDemoMode();
  const [glucose, setGlucose] = useState<GlucoseTrendPoint[] | null>(null);
  const [config, setConfig] = useState<BlockConfig | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    api
      .getGlucoseTrend()
      .then(setGlucose)
      .catch(() => setGlucose([]));
  }, []);

  const registry = useMemo(
    () => (glucose === null ? [] : buildRegistry(glucose)),
    [glucose]
  );
  const registryIds = useMemo(() => registry.map((b) => b.id), [registry]);

  // Demo mode: React state only — refresh restores the curated default.
  // Otherwise: hydrate from localStorage, reconciled against the registry.
  useEffect(() => {
    if (glucose === null) return;
    if (demoMode) {
      setConfig(defaultConfig(registryIds));
      return;
    }
    const stored = readStored();
    setConfig(stored ? reconcile(stored, registryIds) : defaultConfig(registryIds));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoMode, glucose === null]);

  useEffect(() => {
    if (config && !demoMode) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    }
  }, [config, demoMode]);

  if (glucose === null || config === null) {
    return <p className="text-sm text-sand">Loading…</p>;
  }

  const blockById = new Map(registry.map((b) => [b.id, b]));

  const move = (id: string, delta: -1 | 1) => {
    setConfig((c) => {
      if (!c) return c;
      const order = [...c.order];
      const i = order.indexOf(id);
      const j = i + delta;
      if (i < 0 || j < 0 || j >= order.length) return c;
      [order[i], order[j]] = [order[j], order[i]];
      return { ...c, order };
    });
  };

  const hide = (id: string) =>
    setConfig((c) =>
      c
        ? {
            order: c.order.filter((x) => x !== id),
            hidden: [...c.hidden, id],
          }
        : c
    );

  const show = (id: string) =>
    setConfig((c) =>
      c
        ? {
            order: [...c.order, id],
            hidden: c.hidden.filter((x) => x !== id),
          }
        : c
    );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h1 className="text-xl font-medium text-ink">Trends</h1>
        <button
          onClick={() => setEditing((e) => !e)}
          className={`text-[12px] font-medium px-3 py-1 rounded-full ${
            editing
              ? "bg-leaf text-white"
              : "text-leaf border-[0.5px] border-line hover:bg-line/40"
          }`}
        >
          {editing ? "Done" : "Customize"}
        </button>
      </div>

      {editing ? (
        <>
          <div className="space-y-1.5">
            {config.order.map((id, i) => (
              <div
                key={id}
                className="flex items-center justify-between bg-white border-[0.5px] border-line rounded-2xl px-3.5 py-2.5"
              >
                <span className="text-[13px] text-ink">
                  {blockById.get(id)?.title ?? id}
                </span>
                <span className="flex items-center gap-1">
                  <button
                    onClick={() => move(id, -1)}
                    disabled={i === 0}
                    aria-label={`Move ${blockById.get(id)?.title} up`}
                    className="p-1.5 rounded-full text-clay hover:bg-line/50 disabled:opacity-30"
                  >
                    <ChevronUp size={15} strokeWidth={1.75} />
                  </button>
                  <button
                    onClick={() => move(id, 1)}
                    disabled={i === config.order.length - 1}
                    aria-label={`Move ${blockById.get(id)?.title} down`}
                    className="p-1.5 rounded-full text-clay hover:bg-line/50 disabled:opacity-30"
                  >
                    <ChevronDown size={15} strokeWidth={1.75} />
                  </button>
                  <button
                    onClick={() => hide(id)}
                    aria-label={`Hide ${blockById.get(id)?.title}`}
                    className="p-1.5 rounded-full text-clay hover:bg-line/50"
                  >
                    <EyeOff size={15} strokeWidth={1.75} />
                  </button>
                </span>
              </div>
            ))}
          </div>

          {config.hidden.length > 0 && (
            <div>
              <p className="text-[13px] font-medium text-ink mb-2 mt-4 px-1">
                Add blocks
              </p>
              <div className="space-y-1.5">
                {config.hidden.map((id) => (
                  <div
                    key={id}
                    className="flex items-center justify-between bg-white/60 border-[0.5px] border-dashed border-line rounded-2xl px-3.5 py-2.5"
                  >
                    <span className="text-[13px] text-clay">
                      {blockById.get(id)?.title ?? id}
                    </span>
                    <button
                      onClick={() => show(id)}
                      aria-label={`Add ${blockById.get(id)?.title}`}
                      className="p-1.5 rounded-full bg-leaf-pale text-leaf-deep hover:bg-leaf-soft"
                    >
                      <Plus size={15} strokeWidth={2} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        config.order.map((id) => {
          const block = blockById.get(id);
          if (!block) return null;
          const Block = block.component;
          return <Block key={id} />;
        })
      )}
    </div>
  );
}
