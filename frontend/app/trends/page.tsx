"use client";

import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Eye, EyeOff, GripVertical, Plus } from "lucide-react";
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

/** The bar's visual chrome, shared by the in-list sortable item and the
 * lifted DragOverlay copy. */
function BarChrome({
  title,
  lifted,
  grip,
  trailing,
}: {
  title: string;
  lifted?: boolean;
  grip?: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  return (
    <div
      className={`flex items-center gap-2.5 bg-white rounded-2xl px-3 py-2.5 border-[0.5px] ${
        lifted
          ? "border-leaf-soft shadow-[0_10px_24px_rgba(31,168,144,0.22)] rotate-[-1.2deg] scale-[1.02]"
          : "border-line"
      }`}
    >
      {grip ?? (
        <GripVertical
          size={15}
          strokeWidth={1.75}
          className={lifted ? "text-leaf" : "text-sand"}
        />
      )}
      <span className="flex-1 text-[13px] text-ink">{title}</span>
      {trailing}
    </div>
  );
}

function SortableBar({
  id,
  title,
  onHide,
}: {
  id: string;
  title: string;
  onHide: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  if (isDragging) {
    // The vacated spot doubles as the drop indicator
    return (
      <div
        ref={setNodeRef}
        style={{ transform: CSS.Transform.toString(transform), transition }}
        className="h-[44px] rounded-2xl border-[1.5px] border-dashed border-leaf-soft bg-leaf-pale/25"
      />
    );
  }

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <BarChrome
        title={title}
        grip={
          // Drag starts ONLY here — whole-bar drag would fight scrolling
          <button
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
            aria-label={`Reorder ${title}`}
            className="tap-target p-1 -m-1 touch-none cursor-grab active:cursor-grabbing text-sand hover:text-clay"
          >
            <GripVertical size={15} strokeWidth={1.75} />
          </button>
        }
        trailing={
          // Open eye = visible; tapping hides it
          <button
            onClick={onHide}
            aria-label={`Hide ${title}`}
            className="tap-target flex items-center gap-1 px-2 py-1 rounded-full text-leaf-deep hover:bg-line/50"
          >
            <Eye size={15} strokeWidth={1.75} />
            <span className="text-[11px] font-medium">Visible</span>
          </button>
        }
      />
    </div>
  );
}

export default function TrendsPage() {
  const demoMode = useDemoMode();
  const [glucose, setGlucose] = useState<GlucoseTrendPoint[] | null>(null);
  const [config, setConfig] = useState<BlockConfig | null>(null);
  const [editing, setEditing] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    // Hold ~150ms (or slip 8px) before a touch becomes a drag, so taps
    // and scrolls never start one
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 8 },
    }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

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

  const handleDragStart = (event: DragStartEvent) =>
    setActiveId(String(event.active.id));

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setConfig((c) => {
      if (!c) return c;
      const from = c.order.indexOf(String(active.id));
      const to = c.order.indexOf(String(over.id));
      if (from < 0 || to < 0) return c;
      return { ...c, order: arrayMove(c.order, from, to) };
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
      <div className="px-1">
        <div className="flex items-center justify-between">
          <h1 className="text-[32px] font-medium text-ink leading-tight">Trends</h1>
          <button
            onClick={() => setEditing((e) => !e)}
            className={`tap-target text-[12px] font-medium px-3 py-1 rounded-full ${
              editing
                ? "bg-leaf-deep text-white"
                : "text-leaf-deep border-[0.5px] border-line hover:bg-line/40"
            }`}
          >
            {editing ? "Done" : "Customize"}
          </button>
        </div>
        {editing && (
          <p className="text-[11px] text-sand mt-1">
            Drag to reorder · tap the eye to hide
          </p>
        )}
      </div>

      {editing ? (
        <>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragCancel={() => setActiveId(null)}
          >
            <SortableContext
              items={config.order}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-1.5">
                {config.order.map((id) => (
                  <SortableBar
                    key={id}
                    id={id}
                    title={blockById.get(id)?.title ?? id}
                    onHide={() => hide(id)}
                  />
                ))}
              </div>
            </SortableContext>
            <DragOverlay>
              {activeId ? (
                <BarChrome
                  title={blockById.get(activeId)?.title ?? activeId}
                  lifted
                />
              ) : null}
            </DragOverlay>
          </DndContext>

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
                    <span className="flex items-center gap-2 text-[13px] text-clay">
                      {blockById.get(id)?.title ?? id}
                      <span className="flex items-center gap-1 text-[11px] text-sand">
                        <EyeOff size={13} strokeWidth={1.75} />
                        Hidden
                      </span>
                    </span>
                    <button
                      onClick={() => show(id)}
                      aria-label={`Add ${blockById.get(id)?.title}`}
                      className="tap-target p-1.5 rounded-full bg-leaf-deep text-white hover:bg-leaf"
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
