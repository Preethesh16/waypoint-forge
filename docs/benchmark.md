# Repeated simulation benchmark

**Executed: all six planned fresh-start trials passed, including all 13 navigation goals.**
Core source SHA-256 values were unchanged throughout the suite. Complete raw
evidence is in [`evidence/v1.1/benchmark/summary.json`](../evidence/v1.1/benchmark/summary.json)
and its per-trial subdirectories.

The benchmark starts a fresh Gazebo/Nav2 stack for each trial, sends real Nav2
missions, runs read-only health diagnostics, and stops only the processes it owns.
It does not replay a previous success or substitute mocked navigation.

The executed suite contains five repeats of the standard two-goal mission and
one alternative three-goal route through an interior gap and the lower stations:

- Standard: `(1.5, 1.5, π)`, then `(-1.5, 1.5, -π/2)`.
- Alternative: `(0.5, 0.5, 0)`, `(1.5, -1.5, -π/2)`, then `(-1.5, -1.5, π)`.

All trials start at `(-2.0, -0.5, 0)` in the same supplied obstacle world. The
alternative goals are chosen in free space between or beyond the cylinder rows;
the run itself must establish whether navigation succeeds.

## Observed results

| Scenario / trial | Goal time sum | Client time including initialization | Odometry distance | Largest fresh estimated goal error |
| --- | ---: | ---: | ---: | ---: |
| Standard 1 | 49.642 s | 59.924 s | 8.656 m | 0.1420 m |
| Standard 2 | 49.925 s | 59.025 s | 8.330 m | 0.0484 m |
| Standard 3 | 51.928 s | 60.974 s | 8.582 m | 0.0808 m |
| Standard 4 | 52.322 s | 61.327 s | 8.401 m | 0.0407 m |
| Standard 5 | 50.224 s | 59.275 s | 8.437 m | 0.0269 m |
| Interior/lower route | 54.281 s | 63.380 s | 9.650 m | 0.1411 m |

Standard missions succeeded in **5/5 observed trials**. Their summed goal times
had median **50.224 s**, range **49.642–52.322 s**. The alternative three-goal
route succeeded in its single trial, taking **54.281 s** of goal execution.

All six trials had a fresh advancing clock with one publisher, passed the actual
post-mission diagnostics, and left no live owned processes after cleanup. All
13 terminal pose estimates were fresh; Nav2 feedback reported zero recoveries.
The largest estimated goal error was **0.1420 m**, within the configured 0.15 m
position tolerance. This is a pose estimate, not simulator ground truth.

## Run

Inside the ROS 2 Jazzy environment, from the repository root:

```bash
source /opt/ros/jazzy/setup.bash
export DISPLAY=:99  # existing virtual desktop, or your working X display
python3 scripts/benchmark.py --runs 5 --output evidence/v1.1/benchmark
```

`gui:=false` is the default: it disables the Gazebo client and RViz, retaining
physics, laser simulation, bridges and Nav2. The simulated GPU lidar still needs
a rendering-capable X display. Do not close the virtual desktop during the suite.

The benchmark defaults to ROS domain 83 and creates a unique Gazebo transport
partition for each trial. It refuses to mix with an existing clock publisher on
that domain, and refuses to overwrite an existing output directory. Use a new
output path for a new attempt so failed evidence is preserved.

A shorter smoke run, with different output storage:

```bash
python3 scripts/benchmark.py --runs 1 --no-include-challenge --output evidence/v1.1/smoke
```

Do not run this concurrently with another benchmark on the same domain. GUI
inspection/recording is a separate acceptance check; headless runs do not replace
that evidence.

## What is checked and saved

Each trial records:

1. A fresh advancing clock, beginning below 15 simulation seconds, and exactly
   one clock publisher.
2. Mission process exit status, requested and completed goal counts, terminal
   success/timeout flags, timing, odometry distance and fresh feedback/AMCL goal error.
3. A three-second actual `doctor.py` health observation after the mission.
4. Bounded cleanup, including any escalation and remaining live owned processes.
5. Complete simulation, mission and diagnostic text logs plus JSON reports.

The suite summary records source-file SHA-256 values before and after execution.
A source change during the suite prevents an all-planned-passed result. Standard
and alternative scenarios are summarized separately. Failed trials remain in
the observed success denominator; timing summaries include only complete
successful trials. Missing measurements are not converted to zero.

The per-goal timeout defaults to 120 seconds, the mission wall timeout to 400
seconds including localization, and startup to 45 seconds. The existing mission
wrapper also provides its own 420-second bound. Ctrl-C cancels the current client
and performs bounded cleanup; it does not mark remaining trials as passed.

## Interpretation

Five repeat successes would mean five observed successes in this environment,
not a demonstrated 100% reliability probability. This small suite uses one host,
one map, one robot model, static obstacles and one configuration. AMCL and physics
may vary between runs; no claim of bitwise deterministic replay is made. Report
median and range with sample count, not statistical confidence unsupported by
these few runs. Feedback/AMCL position error is an estimate rather than simulator ground
truth, and laser range is not robot-footprint clearance.
