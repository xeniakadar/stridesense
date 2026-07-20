from app.models import Run
from app.models.enums import RunType
from scripts.classify_runs import MIN_SAMPLE_SIZE, _distribution, classify

# A synthetic "typical runner": 7:00/km average pace (+/- 30s), 8km average
# distance (+/- 2km), 145bpm average HR (+/- 10).
PACE_DIST = (420.0, 30.0)
DISTANCE_DIST = (8.0, 2.0)
HR_DIST = (145.0, 10.0)


def _run(distance_km: float, pace: float | None = 420.0, avg_hr: int | None = None) -> Run:
    return Run(distance_km=distance_km, avg_pace_seconds_per_km=pace, avg_hr=avg_hr)


def test_distribution_requires_minimum_sample_size() -> None:
    assert _distribution([1.0] * (MIN_SAMPLE_SIZE - 1)) is None
    assert _distribution([1.0] * MIN_SAMPLE_SIZE) is not None


def test_distribution_floors_stddev_to_avoid_divide_by_zero() -> None:
    # A perfectly constant history (every run the same distance) must not
    # produce a zero-stddev distribution — that would make every future
    # z-score a division by zero.
    mean, sd = _distribution([8.0] * MIN_SAMPLE_SIZE)
    assert mean == 8.0
    assert sd == 1.0


def test_marathon_distance_is_race_regardless_of_pace_or_missing_distributions() -> None:
    run = _run(distance_km=42.3, pace=600.0)  # slow marathon pace
    assert classify(run, pace_dist=None, distance_dist=None, hr_dist=None) == RunType.RACE


def test_half_marathon_distance_is_race() -> None:
    run = _run(distance_km=21.0)
    assert (
        classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) == RunType.RACE
    )


def test_distance_just_outside_race_tolerance_is_not_race() -> None:
    # 1.5km past the marathon tolerance (RACE_TOLERANCE_KM=1.0) — but it's
    # such a large distance outlier it should still read as LONG.
    run = _run(distance_km=43.7, pace=450.0)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) == RunType.LONG


def test_long_distance_outlier() -> None:
    # dist_z = (12.0 - 8.0) / 2.0 = 2.0 >= LONG_DISTANCE_Z (1.5)
    run = _run(distance_km=12.0, pace=450.0)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) == RunType.LONG


def test_distance_just_below_long_threshold_is_not_classified() -> None:
    # dist_z = (10.9 - 8.0) / 2.0 = 1.45, just under LONG_DISTANCE_Z (1.5)
    run = _run(distance_km=10.9, pace=420.0)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) is None


def test_recovery_slow_short_and_not_elevated_hr() -> None:
    # pace_z = (450-420)/30 = 1.0, dist_z = (6-8)/2 = -1.0, hr_z = (140-145)/10 = -0.5
    run = _run(distance_km=6.0, pace=450.0, avg_hr=140)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) == RunType.RECOVERY


def test_recovery_without_hr_data() -> None:
    run = _run(distance_km=6.0, pace=450.0, avg_hr=None)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) == RunType.RECOVERY


def test_slow_pace_with_elevated_hr_is_not_recovery() -> None:
    # Slow pace but HR is elevated (hr_z=1.0) — contradicts "easy effort",
    # so this is not a clear recovery signature.
    run = _run(distance_km=6.0, pace=450.0, avg_hr=155)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) is None


def test_tempo_fast_pace_with_elevated_hr() -> None:
    # pace_z = (390-420)/30 = -1.0, hr_z = (150-145)/10 = 0.5
    run = _run(distance_km=8.0, pace=390.0, avg_hr=150)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) == RunType.TEMPO


def test_fast_pace_without_elevated_hr_is_not_tempo() -> None:
    # Fast pace but HR barely above the mean (hr_z=0.2 < TEMPO_HR_Z 0.5) —
    # not a clear enough effort signature.
    run = _run(distance_km=8.0, pace=390.0, avg_hr=147)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) is None


def test_fast_long_run_is_long_not_tempo() -> None:
    # A fast pace over a distance that's also a clear LONG outlier: LONG
    # is checked first, so it wins over a TEMPO-shaped pace/HR signature.
    run = _run(distance_km=13.0, pace=390.0, avg_hr=160)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) == RunType.LONG


def test_typical_run_is_left_unclassified() -> None:
    # Squarely average pace, distance, and HR — the most common case in
    # any runner's history, and exactly the case a conservative classifier
    # must NOT guess at: "typical" isn't a clear signal, it's the absence
    # of one.
    run = _run(distance_km=8.0, pace=420.0, avg_hr=145)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) is None


def test_no_pace_data_is_left_unclassified() -> None:
    run = _run(distance_km=12.0, pace=None)
    assert classify(run, PACE_DIST, DISTANCE_DIST, HR_DIST) is None


def test_missing_distributions_prevent_classification() -> None:
    # Fewer than MIN_SAMPLE_SIZE runs in the user's history means no real
    # distribution exists — an extreme-looking run must still not be
    # classified without one (races are the sole distance-only exception).
    run = _run(distance_km=12.0, pace=390.0, avg_hr=160)
    assert classify(run, pace_dist=None, distance_dist=DISTANCE_DIST, hr_dist=HR_DIST) is None
    assert classify(run, pace_dist=PACE_DIST, distance_dist=None, hr_dist=HR_DIST) is None
