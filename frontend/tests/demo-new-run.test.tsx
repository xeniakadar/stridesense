import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import NewRunPage from "@/app/runs/new/page";

vi.mock("@/components/DemoProvider", () => ({
  useDemoMode: () => true,
  DemoProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, back: vi.fn() }),
}));

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  push.mockReset();
});

test("demo add-run: valid submit shows notice, stays put, no network", async () => {
  const { container } = render(<NewRunPage />);

  // Date and duration have valid defaults; distance is the only
  // remaining required field
  const distance = container.querySelector('input[name="distance_km"]')!;
  fireEvent.change(distance, { target: { value: "8.5" } });

  fireEvent.click(screen.getByRole("button", { name: /save run/i }));

  // The demo notice appears and the user stays on the form
  expect(
    await screen.findByText(/this is a demo — runs can't be saved here/i)
  ).toBeTruthy();
  expect(push).not.toHaveBeenCalled();
  expect(fetchMock).not.toHaveBeenCalled();

  // The form is still fully present and interactive
  expect(screen.getByRole("button", { name: /save run/i })).toBeTruthy();
});
