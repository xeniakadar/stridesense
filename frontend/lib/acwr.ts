// Mirrors SWEET_SPOT_LOW/HIGH in the backend (app/services/training_load.py)
// — the chart band, its caption, and the explainer all read from here
export const ACWR_OPTIMAL_LOW = 0.8;
export const ACWR_OPTIMAL_HIGH = 1.3;

export const ACWR_EXPLAINER =
  "ACWR (acute:chronic workload ratio) compares your last 7 days of " +
  "training with your last 28. Around 1.0 means you're training at a " +
  `load your body is used to. Well above ${ACWR_OPTIMAL_HIGH} raises ` +
  `injury risk; well below ${ACWR_OPTIMAL_LOW} means you're losing fitness.`;
