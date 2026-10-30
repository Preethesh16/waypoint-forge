# Reproduce the live-status demonstration

Use the Ubuntu/ROS environment and virtual desktop described in the README.
The recording is a continuous desktop capture. Its footer reads the actual
mission client's atomic status file; it does not simulate motion or invent
success messages.

1. Start a fresh simulation: `bash scripts/run.sh`.
2. In another terminal, initialize localization without moving:

   ```bash
   bash scripts/mission.sh --initialize-only \
     --output evidence/v1.1/initialization.json \
     --status-json evidence/v1.1/live-status.json \
     --status-text evidence/v1.1/live-status.txt
   ```

3. Start recording in a third terminal:

   ```bash
   DISPLAY=:99 bash scripts/record.sh
   ```

4. Immediately run the two-goal mission in the second terminal:

   ```bash
   bash scripts/mission.sh --skip-initial-pose \
     --output evidence/v1.1/mission-demo.json \
     --status-json evidence/v1.1/live-status.json \
     --status-text evidence/v1.1/live-status.txt
   ```

The recorder stops after 90 seconds and refuses to overwrite an existing file.
Pass a different absolute filename as its first argument for another take, and
an optional second argument for a duration from 60 to 120 seconds.
Confirm both goals completed inside the recording before using it as evidence;
a recording's existence alone does not mean a mission succeeded.

## Reading the views

- Left: actual Gazebo physics, robot and obstacles.
- Right: RViz's map-frame view. Blue is the global path, green is the local plan
  and robot footprint, and shaded regions are obstacle costs. The lidar points
  supply current observations.
- Footer: phase, requested goal, elapsed wall/simulation time and fresh
  distance-remaining feedback from Nav2. The final success label is emitted only
  after all requested actions return success.

Both views use the same orientation. Pose and path displays are estimates;
visual inspection is not a formal contact or clearance proof.

`--skip-initial-pose` is only for an already-localized running simulation. The
normal mission command initializes to the known spawn pose, so restart the
simulation before repeating it. See [mission evidence](mission-evidence.md) for
timestamp/freshness rules and [unmapped-obstacle test](unmapped-obstacle.md) for
the optional sensor-driven obstacle scenario.
