# Optional unmapped obstacle experiment

This simulation-only experiment checks an existing Nav2 capability: detecting an
obstacle that is absent from the static map. It adds no navigation algorithm and
does not modify Nav2 parameters, map files, the normal world, or the core mission.

The helper creates one orange **static** crate named `waypoint_crate`, size
`0.5 × 0.5 × 0.6 m`, centered at Gazebo `(0, 1.65, 0.3)`. The box bottom is at ground
level. A fresh simulation removes the experimental crate automatically; the
helper does not delete entities or modify physical hardware.

## Run after the normal mission has been verified

Start a fresh simulator with explicit, matching isolation values. Keep these
values identical for the simulator, mission, and helper processes:

```bash
export ROS_DOMAIN_ID=73
export GZ_PARTITION=antropi-unmapped-demo
bash scripts/run.sh
```

In another terminal with the same environment, localize and create the crate:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=73
export GZ_PARTITION=antropi-unmapped-demo
bash scripts/mission.sh --initialize-only --output evidence/unmapped-initialization.json
python3 scripts/unmapped_obstacle.py --spawn
```

The spawn mode uses only `/world/default/create`, request type
`gz.msgs.EntityFactory`, response type `gz.msgs.Boolean`, a 5-second Gazebo timeout
and an 8-second process timeout. `allow_renaming: false` prevents silently creating
a differently named duplicate. Exit 0 means the service replied `data: true`;
inspect Gazebo to verify the actual entity. A failed/uncertain result should be
investigated before retrying. Both modes refuse to run without a nonempty explicit
`GZ_PARTITION`.

Start the read-only observer, then run the normal two-goal mission in another
terminal. The moving robot brings the crate within its laser's observed region:

```bash
python3 scripts/unmapped_obstacle.py --observe --duration 90
```

```bash
bash scripts/mission.sh --skip-initial-pose --output evidence/unmapped-mission.json \
  --status-text evidence/unmapped-status.txt
```

No initial-pose reset is sent by the second command. Do not launch two mission
clients simultaneously. `--observe` subscribes only; it sends no goal, velocity,
initial pose, Gazebo request, or lifecycle transition.

## What the evidence establishes

The observer reads original `/map`, live `/global_costmap/costmap`, and `/clock`.
The maps use reliable/transient-local subscriptions so their retained snapshots
are available. This project's `always_send_full_costmap: true` setting supplies
full updated occupancy grids; the helper does not reconstruct incremental updates.

The JSON records exact cells and world coordinates in a `0.6 × 0.6 m` probe region
around the crate. The extra 5 cm on each side accounts for quantization of a laser
hit on a box boundary into the neighboring 5 cm grid cell. It requires:

1. The entire probe region is covered by the static map and **every** extracted
   static cell is free (`0`); unknown cells are not accepted as free.
2. The live costmap region contains at least one lethal cell (`100`); inflated
   obstacle costs alone do not satisfy this condition.
3. At least two costmap snapshots have advancing simulation timestamps, without
   a backward jump. The current costmap is fresh against both wall receipt time
   and `/clock` (two-second tolerance, 0.1-second future allowance).
4. The simulation clock is advancing and fresh.

Exit 0 means all conditions were observed together. Exit 1 preserves the latest
patches and failed conditions, including missing topics, no visible laser return,
timeout or interruption. Start the observer before the mission so it can capture
marking as the robot approaches; the crate need not be visible from the spawn.

The report deliberately does **not** prove obstacle identity, minimum clearance,
successful navigation, or collision freedom. The crate's visible location,
successful action results and Gazebo/RViz recording provide complementary
observations. A temporary moving obstacle or a changed map would require a
separate experiment.

## Files and status

- `config/unmapped_crate.sdf`: the isolated static box definition.
- `scripts/unmapped_obstacle.py`: explicit `--spawn` or read-only `--observe` modes.
- Default outputs: `evidence/unmapped-spawn.json` and
  `evidence/unmapped-observation.json`. Use `--output` to select another file.

## Actual experiment result (30 October 2026)

The fresh simulation used ROS domain `73` and Gazebo partition
`waypoint_v11_demo`. The [creation receipt](../evidence/v1.1/unmapped-spawn.json)
records `data: true` in 0.359 wall seconds. The
[observer evidence](../evidence/v1.1/unmapped-observation.json) passed all five
conditions after 11.301 wall seconds:

| Observation | Result |
| --- | --- |
| Static-map probe | 144/144 free cells; 0 lethal, 0 unknown |
| Live-costmap probe | 12 lethal cells among 144 cells; 0 unknown |
| Live costmap samples | 7 snapshots with advancing timestamps |
| Accepted costmap timestamp | 43.523 simulation seconds, matching observed clock |
| Observation errors | None |

The [recorded mission](../evidence/v1.1/mission-demo.json) then completed both
navigation goals with zero reported recoveries. The selected final pose estimates
were fresh for both goals, with positional errors 0.0337 m and 0.0241 m.
Navigation wall durations were 29.382 s and 22.357 s (51.739 s combined); the
whole client execution, including readiness, lasted 58.010 s.

### Estimated route comparison

A compact [machine-readable comparison](unmapped-comparison.json) records these
metrics, input SHA-256 hashes and caveats. The reference is the first ordinary benchmark run,
[standard-01](../evidence/v1.1/benchmark/standard-01/mission.json), with the same
nominal initial pose and goal locations but no added crate. The table compares
where consecutive recorded map-frame trajectory samples straddle `x=0`, using
linear interpolation between those samples. This is an estimated route summary,
not an exact crossing measurement or a footprint-clearance calculation.

| Metric | Standard-01 | Added crate |
| --- | ---: | ---: |
| Goal 1 estimated y at x=0 | 1.753 m | 0.483 m |
| Goal 2 estimated y at x=0 | 1.768 m | 2.151 m |
| Goal 1 odometry distance | 5.458 m | 4.880 m |
| Goal 2 odometry distance | 3.198 m | 3.406 m |
| Goal outcomes | 2/2 succeeded | 2/2 succeeded |
| Reported recoveries | 0 | 0 |

In the crate run, the first leg used an interior passage. The return leg's
estimated centerline crossed above the crate's upper y boundary of 1.9 m,
whereas the reference crossing passed through the region later occupied by the
crate. This route difference is consistent with the observed new lethal costs.
The comparison is one obstacle run against one reference run, with unseeded
localization and different rendering/load conditions. It does not establish
statistical performance improvement, an exact robot-to-box gap, or collision
freedom. Sampling can repeat the most recent localization estimate; it is not a
dense ground-truth trace.

Focused helper regression tests are retained in `tests/test_unmapped_obstacle.py`:
eight tests passed using real `OccupancyGrid` message types, covering free,
unknown, inflated and lethal cells; origin yaw; clipped/invalid grids; missing
partition; and the SDF geometry.

Official API reference:
[Gazebo Sim 8 entity creation](https://gazebosim.org/api/sim/8/entity_creation.html).
