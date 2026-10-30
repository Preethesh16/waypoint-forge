# Mission evidence and live recording status

The default mission behavior remains unchanged: publish the matching Gazebo spawn
pose `(-2.0, -0.5, 0)`, wait for Nav2, and request the two documented goals. No
velocity commands are published by this script.

## Separate initialization from the recording

On a newly started simulator:

```bash
bash scripts/mission.sh --initialize-only --output evidence/initialization.json \
  --status-json evidence/live-status.json --status-text evidence/live-status.txt
```

Exit 0 here means **localization/Nav2 readiness**, not successful goal navigation.
The report uses `initialization_succeeded: true`, `initialize_only: true`, zero
goal results and `all_succeeded: false`.

Then begin the recording and run the actual mission without resetting AMCL:

```bash
bash scripts/mission.sh --skip-initial-pose --output evidence/mission.json \
  --status-json evidence/live-status.json --status-text evidence/live-status.txt
```

Use `--skip-initial-pose` only when the current simulator is already localized.
It waits for AMCL's transient-local estimate and never publishes an initial pose.
This option does not move the robot back to the spawn point. If you need a fresh
repeatable run, restart the simulator and initialize again. The shell wrapper
retains its 420-second overall timeout and bounded interrupt/kill behavior.

## Overlay contract

Both status files are optional. They are created before ROS readiness can block.
Updates replace a complete temporary file atomically, so readers do not see
partially written JSON/text. The JSON includes phase, goal index/coordinates,
elapsed wall/simulation time and recent action feedback. The text is always two
lines and can be consumed by an FFmpeg `drawtext` filter with `reload=1`.

Periodic updates run at 2 Hz on a steady wall clock, plus immediate phase changes.
Readiness waits can delay callbacks; the initial waiting file remains valid.
Remaining distance comes from real `NavigateToPose` feedback and disappears from
the text when its receipt is more than two wall seconds old. Final success text
is emitted only after every required action has actually succeeded. Failed,
interrupted, or initialization-only states are labeled separately.

## Report schema 2

Existing result keys remain present. New evidence includes:

- Per-goal and whole-run wall/simulation durations, plus per-goal simulation start
  and end times. Total simulation duration starts at the first observed nonzero
  simulation clock; it is not an estimate of CPU execution time.
- Timestamped AMCL and action-feedback pose estimates. The final selected pose
  prefers a fresh map-frame estimate, then the latest simulation timestamp.
  Freshness requires receipt within two wall seconds and a simulation timestamp
  no more than two seconds old (or 0.1 seconds ahead for callback ordering).
- `estimated_goal_error_m` now uses that selected **fresh** estimate; it is `null`
  if every estimate is stale. `final_amcl_xy` remains for compatibility but must be
  interpreted alongside `final_amcl_estimate.fresh` and its age fields.
- Action-feedback sample count, maximum reported recovery count, and last
  remaining-distance/navigation-time feedback. These are observed Nav2 reports,
  not a separate recovery implementation.
- A map-frame estimated trajectory sampled at no more than 2 Hz, bounded to 2,000
  samples per goal. Each sample records its pose source and simulation timestamp.
  `trajectory_truncated` makes the cap explicit. An interrupted/error goal keeps
  partial measurements under `unfinished_goal`; it is never counted as success.

The trajectory and final error are localization estimates, not Gazebo ground
truth. Odometry distance remains independently integrated from `/odom`; invalid
nonfinite XY samples are counted and excluded. The laser minimum remains a
sensor range, not footprint clearance or proof of collision freedom.

## Checks

```bash
source /opt/ros/jazzy/setup.bash
python3 -m unittest discover -s tests -p 'test_mission_evidence.py' -v
```

Six checks passed against the real installed ROS Python APIs: fresh feedback vs.
stale AMCL selection, old simulation stamps despite fresh receipt, future/stale
samples, wrong-frame/nonfinite poses, removal of stale remaining distance from
the overlay, and an actual isolated-domain process that creates live files while
waiting for missing AMCL and preserves interruption evidence without a traceback.
The last check uses ROS domain 96 and sends no navigation action.

Full simulation behavior and positive recording results must be verified by the
integration run after these changes; the unit/isolated checks do not establish
navigation success.
