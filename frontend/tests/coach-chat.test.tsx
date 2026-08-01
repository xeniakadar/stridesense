import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { CoachChat } from "@/components/CoachChat";

vi.mock("@/components/DemoProvider", () => ({
  useDemoMode: () => true,
  DemoProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const ask = vi.fn();
const getDemoQuestions = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    ask: (...args: unknown[]) => ask(...args),
    getDemoQuestions: (...args: unknown[]) => getDemoQuestions(...args),
  },
  ApiError: class ApiError extends Error {},
}));

const CANNED = {
  answer: "Your marathon went well.",
  model: "demo",
  cited_runs: [],
};

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  getDemoQuestions.mockResolvedValue(["Tell me about my marathon"]);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  ask.mockReset();
  getDemoQuestions.mockReset();
  fetchMock.mockReset();
});

test("demo mode: disabled input submits nothing and fires no network", async () => {
  const { container } = render(<CoachChat />);
  await screen.findByRole("button", { name: /marathon/i }); // chips loaded

  const input = container.querySelector("input")!;
  expect(input.disabled).toBe(true);
  fireEvent.submit(container.querySelector("form")!);

  expect(ask).not.toHaveBeenCalled();
  expect(fetchMock).not.toHaveBeenCalled();
});

test("chip tap renders question and canned answer into the transcript", async () => {
  ask.mockResolvedValue(CANNED);
  render(<CoachChat />);

  fireEvent.click(await screen.findByRole("button", { name: /marathon/i }));

  // User bubble immediately, coach answer on arrival
  expect(screen.getByText("Tell me about my marathon")).toBeTruthy();
  expect(await screen.findByText("Your marathon went well.")).toBeTruthy();
  expect(ask).toHaveBeenCalledWith("Tell me about my marathon");
});

test("an asked chip gains the asked state but stays tappable", async () => {
  ask.mockResolvedValue(CANNED);
  render(<CoachChat />);

  const chip = await screen.findByRole("button", { name: /marathon/i });
  expect(chip.textContent).not.toContain("✓");
  fireEvent.click(chip);
  await screen.findByText("Your marathon went well.");
  expect(chip.textContent).toContain("✓");

  // Re-tap: re-renders the stored answer as a fresh exchange
  fireEvent.click(chip);
  await waitFor(() =>
    expect(screen.getAllByText("Your marathon went well.")).toHaveLength(2)
  );
  expect(ask).toHaveBeenCalledTimes(2);
});

test("error shows a retry action that re-asks the same question", async () => {
  ask
    .mockRejectedValueOnce(new Error("boom"))
    .mockResolvedValueOnce(CANNED);
  render(<CoachChat />);

  fireEvent.click(await screen.findByRole("button", { name: /marathon/i }));
  const retryButton = await screen.findByRole("button", { name: /retry/i });
  expect(screen.getByText(/something went wrong/i)).toBeTruthy();

  fireEvent.click(retryButton);
  expect(await screen.findByText("Your marathon went well.")).toBeTruthy();
  expect(ask).toHaveBeenCalledTimes(2);
  expect(ask).toHaveBeenLastCalledWith("Tell me about my marathon");
});
