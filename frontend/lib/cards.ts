// Single source of truth for card display names: the Trends cards, the
// Customize list, and Home's chart title all read from here — the strings
// cannot drift. Ids are storage keys (localStorage block config); never
// rename them, only the display values.
export const CARD_TITLES = {
  cities: "Cities",
  "training-load": "Training load",
  "glucose-tir": "Time in range",
  "pace-trend": "Easy-run pace trend",
  "monthly-volume": "Monthly volume",
  records: "Records",
  "run-types": "Run types",
  "weekly-mileage": "Weekly distance",
} as const;

export type CardId = keyof typeof CARD_TITLES;
