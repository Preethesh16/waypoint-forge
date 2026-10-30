# Independent review

Review scope: assignment brief, launch integration, mission client, Nav2 parameters,
Docker environment and documentation. This document distinguishes code review
from runtime evidence; consult `verification.md` for independently executed checks.

## Compatibility research

- Ubuntu 24.04 and ROS 2 Jazzy are a supported TurtleBot3 combination in the
  [ROBOTIS quick-start guide](https://emanual.robotis.com/docs/en/platform/turtlebot3/quick-start/).
- Jazzy should use Gazebo Harmonic / the corresponding ROS Gazebo vendor packages,
  rather than Gazebo Classic. See the
  [Gazebo ROS installation matrix](https://gazebosim.org/docs/harmonic/ros_installation/).
- The selected Jazzy branch launches the Gazebo Sim world, robot state publisher
  and ROS/Gazebo bridge. The Navigation2 launch supplies the TurtleBot3 map and
  includes Nav2 bringup. The project sets `use_sim_time=true` and a matching
  initial robot pose.
- The stamped velocity parameters align with the
  [ROBOTIS TwistStamped migration](https://github.com/ROBOTIS-GIT/turtlebot3/issues/1038).
  Actual `/cmd_vel` publisher/subscriber types still need a runtime check.
- The [Jazzy Simple Commander API](https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/)
  supports this application structure. Its documentation requires polling task
  completion before reading results and warns that server failures can throw
  exceptions or return `None`.

## Initial findings sent to integration owner

1. **Bounded cancellation and interruption.** The upstream `cancelTask()` waits
   for an asynchronous cancellation response without a timeout. The initial
   implementation called it on goal timeout and SIGINT, and the shell timeout
   lacked a kill-after bound. Default rclpy signal handling can also shut the
   context before application cancellation runs. Use a deliberate signal policy,
   bounded cancel acknowledgement/result waits, and an outer kill-after bound.
2. **Result freshness after cancellation.** `getResult()` should follow a
   terminal `isTaskComplete()` result. Calling it immediately after cancel
   acknowledgement can report a stale status. The timeout flag prevents false
   success, but the diagnostic status must also remain accurate.
3. **Input shape checks.** Non-list JSON, scalar goal entries, malformed JSON,
   and boolean coordinates should yield a concise argument error rather than
   a traceback. Validate shape before calling `len()` and iterating coordinates.
4. **Documentation link.** The old `/commander_api/index.html` path returns 404;
   use the Jazzy-specific link above.
5. **Desktop process supervision.** The initial desktop script continued after
   its X-server readiness loop exhausted, and plain `wait` did not fail early
   when an essential child died. A startup failure should be visible and cause
   a nonzero container exit rather than an apparently healthy unusable desktop.

Re-review of the subsequent mission revision confirms code fixes for findings
1–4: input validation checks JSON and shape, rclpy leaves the context alive for
application interruption handling, cancellation and terminal-result waits are
bounded, and the shell has a kill-after limit. These code findings still require
the runtime checks described below. Desktop finding 5 is also resolved in code: readiness failure exits nonzero,
and `wait -n` causes cleanup when an essential desktop child exits.

## Final integrated review

The revised launch explicitly starts the installed TurtleBot3 world and model,
loads the package-provided map into Nav2, and supplies local Gazebo/RViz view
configurations. `run.sh` assigns a per-run Gazebo transport partition and launches
the stack in its own process group. Its exit cleanup sends interrupt, then
bounded TERM/KILL escalation to the whole group. This addresses the observed
orphaned Gazebo processes and competing clocks; the independent tester owns the
shutdown/restart runtime check.

Evidence inspected directly:

| Artifact | Observed result |
| --- | --- |
| `evidence/mission-clean.json` | Both goals `TaskResult.SUCCEEDED`; 31.967 s and 20.179 s wall time; estimated AMCL positional errors 0.0127 m and 0.0404 m |
| `evidence/doctor-independent-clean.json` | All 15 diagnostics passed; advancing clock/scan/odom; zero backward time jumps; connected TF; active lifecycle nodes |
| `evidence/graph-independent-clean.json` | One `/clock` publisher; checked ROS nodes use simulation time; velocity topics use `TwistStamped`; scan source timeout is 0.5 s |
| `evidence/live-cancel.json` | Interrupted mission reports false success and received cancel response and terminal result |
| `evidence/timeout-test.json` | Timeout reports `TaskResult.CANCELED`, never success; old-process restart caveat is documented by the tester |
| `evidence/package-versions.tsv` | Actual installed ROS/Gazebo package versions recorded |

The 0.5-second scan source timeout is supported by the independently measured
5 Hz scan stream and observed normal jitter exceeding the original 0.2-second
threshold. The design document explains the additional stale-data travel budget
without presenting it as a physical safety guarantee.

No new core implementation blocker was found in this integrated review. The
remaining delivery checks below still matter; successful JSON outcomes alone
do not replace inspection of the required recording.

## Useful differentiators and tradeoffs

1. **Repeatable mission with measured results:** fixed start/goals and JSON action
   outcomes make a reviewer able to reproduce and inspect a run. The chosen
   goals are repeatable inputs, not a guarantee of bit-for-bit deterministic
   physics or AMCL behavior. Runtime cost and code complexity are small.
2. **Read-only runtime diagnostics with bounded failure reporting:** clock,
   sensors, transforms, lifecycle states and action availability can be checked
   without moving the robot. Invalid mission input and readiness/cancellation
   failures are explicit. Process termination alone does not establish that an
   independent Nav2 server stopped its action; terminal action state and observed
   motion are the meaningful evidence.

No additional navigation algorithm is needed. An extra planner, dynamic-obstacle
showcase or custom world would increase verification effort without satisfying a
missing core requirement.

## Delivery checks still outstanding at this review

- Confirm the independent tester's final process-group shutdown/restart check.
- Check the final recording is 60–120 seconds and displays both Gazebo and RViz.
- Refresh README/checklist status to reflect actual passing evidence and remaining
  publication status; earlier “no successful navigation run” text is now stale.
- The equivalent package installation in a blank Ubuntu container was exercised,
  but a clean build of the final Dockerfile was not run because of limited disk
  space. State this limit explicitly. The package snapshot records versions;
  the Dockerfile itself does not lock upstream repositories against future changes.
- Confirm publication/submission are approved before external writes.

This review did not operate physical hardware. It does not certify collision
freedom, deterministic replay or behavior in untested worlds.

## Delivery status

The user approved publication and submission, with a company-independent name.
The project is published as Waypoint Forge. The public repository returned HTTP
200 without authentication. Final form receipt is kept outside source control.
