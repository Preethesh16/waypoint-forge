# Independent verification

**Local acceptance passed. Public publication/submission await user approval.**
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
| Public repository and submission | Pending explicit publication approval | Not yet claimed complete |

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

- The Dockerfile itself was **not clean-built as a fresh image**. Actual packages,
  launch scripts, ROS tests and simulation were exercised in an isolated Ubuntu
  container; low host disk space required relocating runtime libraries. Native
  Ubuntu installation on a separate machine remains untested.
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
