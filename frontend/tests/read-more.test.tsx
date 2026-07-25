import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ReadMore } from "@/components/ReadMore";

// jsdom does no layout — scrollHeight is always 0 — so overflow is
// simulated by stubbing the measured content height per test.
function stubScrollHeight(px: number) {
  vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockReturnValue(px);
}

afterEach(() => {
  // RTL auto-cleanup needs vitest globals, which are off — do it manually
  cleanup();
  vi.restoreAllMocks();
});

const LONG_INSIGHT = (
  <div>
    <p>This run sat right in your usual easy range, and it showed.</p>
    <p>Training load is in the optimal zone, so nothing was dragging.</p>
    <p>The warmth added a little cost, visible in the heart rate drift.</p>
    <p>Glucose held steady across the whole session.</p>
    <p>Comparables from June tell the same story at similar paces.</p>
  </div>
);

const SHORT_INSIGHT = (
  <div>
    <p>An easy run that felt easy. Nothing pushed back today.</p>
  </div>
);

test("long multi-paragraph insight renders collapsed with a toggle", async () => {
  // Well past 5 lines at any plausible line-height
  stubScrollHeight(400);
  const { container } = render(<ReadMore>{LONG_INSIGHT}</ReadMore>);

  const toggle = await screen.findByRole("button", { name: /read more/i });
  expect(toggle).toBeTruthy();

  // Collapsed: the content wrapper carries the max-height clamp
  const clamped = container.querySelector('div[style*="max-height"]');
  expect(clamped).not.toBeNull();

  // Expand: clamp lifts, toggle flips
  fireEvent.click(toggle);
  expect(screen.getByRole("button", { name: /show less/i })).toBeTruthy();
  expect(container.querySelector('div[style*="max-height"]')).toBeNull();
});

test("short insight renders uncollapsed with no toggle", async () => {
  // Comfortably under the ~5-line threshold
  stubScrollHeight(60);
  const { container } = render(<ReadMore>{SHORT_INSIGHT}</ReadMore>);

  // Effects have run once the content is queryable; no button ever appears
  expect(await screen.findByText(/felt easy/i)).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
  expect(container.querySelector('div[style*="max-height"]')).toBeNull();
});
