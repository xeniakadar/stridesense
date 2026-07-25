import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import SettingsPage from "@/app/settings/page";

// Demo mode on, without a round-trip to /config
vi.mock("@/components/DemoProvider", () => ({
  useDemoMode: () => true,
  DemoProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState({}, "", "/settings");
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

test("demo settings: actions disabled with captions, no jobs, no network", () => {
  render(<SettingsPage />);

  // Every integration action renders disabled
  for (const name of [/connect/i, /sync now/i, /upload/i, /backfill weather/i]) {
    const button = screen.getByRole("button", { name });
    expect(button).toHaveProperty("disabled", true);
  }

  // One muted caption per integration card
  expect(screen.getAllByText("Not available in demo")).toHaveLength(3);

  // The Import jobs section does not render at all
  expect(screen.queryByText("Import jobs")).toBeNull();
  expect(screen.queryByText(/loading jobs/i)).toBeNull();

  // Nothing hit the API
  expect(fetchMock).not.toHaveBeenCalled();
});
