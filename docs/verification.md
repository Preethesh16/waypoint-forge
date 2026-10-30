# Independent verification

**Local acceptance passed. Publication and submission approved by the user. Repository verified public.**
The independent tester inspected the requirements and source, exercised the real
ROS implementation, queried the live graph and inspected recorded output.

## Final results

| Check | Actual outcome | Evidence |
| --- | --- | --- |
| Dependency installation | ROS 2 Jazzy and TurtleBot3 packages installed in Ubuntu 24.04 container | `evidence/package-versions.tsv` |
| Python / shell syntax | Passed `py_compile` and `bash -n` | Commands below |
| Input handling | Help plus 10 invalid goal inputs and 4 invalid timeout inputs passed | `tests/test_cli.py` |
| Missing-stack interruption | Real client on domain 97 exits 1 cleanly on SIGINT; no false success | `tests/test_interrupt.py` |
| Launch resolution | `ros2 launch launch/demo.launch.py --show-args` exits 0 | Burger URDF, Gazebo Sim major 8 |
| Live ROS integration | All 15 read-only health checks passed | `evidence/doctor-independent-clean.json` |
| Clock / interfaces / parameters | One clock publisher; expected types; all eight queried nodes use simulation time | `evidence/graph-independent-clean.json` |
| Autonomous navigation | Both goals succeeded in two clean runs | `evidence/mission.json`, `evidence/mission-clean.json` |
| Active-goal SIGINT | Terminal CANCELED observed; robot settled with zero measured velocity | `evidence/live-cancel.json`, `evidence/first-run.json` |
| Goal timeout | Clean-stack 0.1 s timeout canceled after 0.127 s, exited 1, no false success | `evidence/timeout-test.json` |
| Shutdown / restart | All live owned processes removed; restart clock began at 0.002 s with one publisher | `evidence/restart-clock.json` |
| Required video | 75.000 s, H.264, 1600×900, 20 fps; entire file decodes without error | `evidence/demo.mp4` |
| Public repository | Unauthenticated HTTP access and GitHub visibility check | Passed: https://github.com/Preethesh16/waypoint-forge |
| Submission | Approved form answers; completion receipt kept outside source repository | Tracked separately |

The final bounded unittest pass ran four grouped tests in **7.726 seconds**, all
passing. These invoke actual subprocesses and the installed ROS client; the
missing-stack test does not mock ROS services.

### Recorded mission measurements

| Goal | Wall time | Odometry distance | Final AMCL position error |
| --- | --- | --- | --- |
| (1.5, 1.5) | 32.357 s | 5.299 m | 0.0464 m |
| (-1.5, 1.5) | 19.878 s | 3.098 m | 0.0201 m |

The video was fully decoded with FFmpeg. Independently inspected frames at
10, 35 and 60 seconds show the robot at different locations around the obstacle
field in Gazebo and corresponding evolving RViz localization/costmaps/path.
The video file is 7,765,636 bytes. These observations support the navigation demo;
they are not a formal contact-free-motion proof.

### Commands

Run from the repository inside the configured ROS 2 environment:

```bash
source /opt/ros/jazzy/setup.bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/mission.py scripts/doctor.py launch/demo.launch.py
bash -n scripts/run.sh scripts/mission.sh scripts/desktop.sh
```

After localization, in another terminal:

```bash
export ROS_DOMAIN_ID=73
python3 scripts/doctor.py --duration 10 --output evidence/doctor.json
```

Media verification:

```bash
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate -of json evidence/demo.mp4
ffmpeg -v error -i evidence/demo.mp4 -f null -
```

## Defects found and resolved

- Invalid JSON/goal shapes originally raised raw exceptions. The real CLI now
  rejects them with usage errors before ROS initialization.
- The minimal package set lacked the `ros2 launch` verb. `ros-jazzy-ros2launch`
  was added explicitly; launch-resolution retesting passed.
- Default signal handling could close the ROS context before cancellation. The
  mission now preserves it for bounded action cancellation. An independent
  status subscriber observed CANCELED approximately 0.238 s after active-goal
  SIGINT; the last 101 odometry samples had zero linear and angular speed.
- The initial 0.2 s scan timeout equaled the measured 5 Hz laser period. Valid
  scan ages around 0.235–0.251 s caused unwanted stops. The live 0.5 s setting was
  queried independently; the clean mission had no invalid-source/scan-age
  rejection warnings. See `evidence/sensor-rates-initial.json`.
- Launcher-only shutdown left Gazebo grandchildren running. A dedicated process
  group, bounded cleanup and a unique Gazebo transport partition resolved live
  process leakage. The final wrapper was interrupted twice, leaving no live
  owned simulator processes. Its expected interruption exit was 130. A fresh
  restart had one clock publisher and reset time to 0.002 s.

## Limits and remaining caveats

- **Historical v1.0 limitation, subsequently addressed for the pinned environment:**
  the original local work did not build a fresh Docker image and relocated
  runtime libraries under disk pressure. An actual uncached build and successful
  real simulation later passed in [CI run 41102204300](https://github.com/Preethesh16/waypoint-forge/actions/runs/41102204300)
  at commit `c05b6d5`; durable artifacts are in `evidence/v1.1/ci-initial/`.
  That initial run predates final telemetry improvements. Consult
  [reproducibility](reproducibility.md) for exact final-source CI; do not treat
  the initial run as proof for a newer commit. Native Ubuntu installation on
  a separate machine remains untested.
- Software-rendered RViz emitted an initial GLSL sampler-link warning, although
  map/costmap rendering is visibly present in the recorded frames. Initial TF
  synchronization warnings also occurred. Logs are not claimed error-free.
- An earlier simultaneous group shutdown caused a composable-node abort. The
  launcher-first cleanup refinement removed all live processes without that
  abort appearing in the final shutdown logs. Bounded cleanup can escalate to
  TERM/KILL. The bootstrap container's PID 1 does not reap zombies; Docker
  `--init` is recommended for ordinary runs.
- Localization errors are AMCL estimates, not Gazebo ground truth. Minimum scan
  return is sensor range, not footprint clearance. No physical robot or dynamic
  obstacle scenario was tested.

## v1.1 repeated-run verification

The new bounded benchmark independently launched six fresh simulations: five
standard two-goal missions and one distinct three-goal mission through an
interior gap and lower stations. All **6/6 trials and 13/13 goals succeeded**.
The standard-route summed goal-time median was **50.224 s**, range
**49.642–52.322 s**; the alternative route took **54.281 s**. All post-run health
checks passed, each initial clock was fresh and uniquely published, and cleanup
left no live owned simulator processes. Source-file hashes were unchanged.

Schema-2 evidence was checked directly: all 13 final pose estimates were fresh,
trajectory arrays were populated without truncation, and feedback reported zero
recoveries. The maximum fresh estimated goal error was 0.1420 m. This result is
not directly comparable to the v1.0 AMCL-only metric because the new report can
choose a fresher navigation-feedback pose. Neither is ground truth.

See [benchmark protocol and full measurements](benchmark.md) and
[`evidence/v1.1/benchmark/summary.json`](../evidence/v1.1/benchmark/summary.json).
Five observed repeat successes are not a demonstrated reliability probability;
all trials share one host, map and configuration. Enhanced video and crate results are recorded below.

The v1.1 independent regression pass completed **22/22 tests in 8.085 s**.
It includes real isolated-ROS interruption/status tests plus input, evidence
freshness, benchmark aggregation and occupancy-grid extraction checks. See
[`evidence/v1.1/regression-tests.txt`](../evidence/v1.1/regression-tests.txt).
The benchmark plot was independently reviewed against the raw values and map
geometry. Its source now refuses reports without confirmed unchanged hashes;
the displayed artifact has unchanged hashes and needs no regeneration.

## v1.1 enhanced local demo and unmapped obstacle

Independent FFprobe inspection confirms **90.000 seconds**, H.264, 1600×900,
20 fps and 8,512,503 bytes. Full decoding returned exit 0. Both supplied stills
were independently inspected: Gazebo visibly contains the orange crate; RViz
shows its sensed costmap region and the planned path, with readable live goal
feedback and a terminal MISSION SUCCEEDED status.

`evidence/v1.1/initialization.json` records initialization without goals. The
subsequent `mission-demo.json` confirms no initial-pose reset and both goals
succeeded (29.382 s and 22.357 s; summed 51.739 s, total client 58.010 s including
readiness). `demo-doctor.json` passed all 15 health checks. The observer report
shows 144/144 static-map probe cells free and 12 lethal live-costmap cells, with
all five observer conditions true. This establishes observed
unmapped-obstacle marking alongside successful navigation; it does not establish
object identity from grids alone, footprint clearance or contact-free motion.

The benchmark hashes identify the code used during those six runs. A subsequent
telemetry timestamp-ordering-only fix avoids tiny negative receipt ages; the
final 22-test suite passed after it. Final-source clean CI is tracked separately,
rather than retroactively relabeling older evidence.
