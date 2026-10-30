# Read-only runtime diagnostics

Once the robot has been localized (the mission sets the initial pose), run from
this repository in another terminal:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=73
python3 scripts/doctor.py --duration 10 --output evidence/doctor.json
```

The same command works via `docker exec` using the appropriate repository path.
A healthy observation exits 0. Any failed essential check exits 1 and is named in
the JSON report. No goal, velocity, initial pose or lifecycle transition is sent.

The observation window is bounded in wall time, so a paused or absent simulation
cannot cause an indefinite wait. Checks cover:

- Advancing `/clock`, `/scan` and `/odom` timestamps, with at least two samples.
- Sensor receipt freshness in wall time and timestamp alignment to simulation time.
- Finite valid laser returns and a valid odometry pose/twist/quaternion.
- `map → odom → base_footprint → base_link`, plus the laser frame actually reported
  by `/scan`. Dynamic transforms must be fresh; static transforms can use stamp zero.
- Active AMCL, controller, planner, behavior server and behavior-tree navigator.
- Availability of the `NavigateToPose` action server.

Best-effort sensor subscriptions can receive both best-effort and reliable sensor
publishers. The node uses simulation time, while its timeout uses the monotonic
wall clock. Lifecycle state queries are read-only and retried during the window.

The default freshness tolerance is two seconds. A deliberately paused simulator,
a simulation reset during observation, an unlocalized AMCL instance, a stale scan,
or a missing node should fail. Use `--max-age` only to accommodate an explicitly
understood slow host; do not use it to hide missing or stalled data.

This is a diagnostic snapshot, not a proof of successful motion or collision
avoidance. The actual Nav2 mission results and Gazebo/RViz recording supply the
end-to-end evidence. A completely empty laser scan is rejected for this enclosed
obstacle world; it could be valid in a different open-space scenario.

API references (Jazzy upstream):
- [tf2 Python Buffer](https://github.com/ros2/geometry2/blob/jazzy/tf2_ros_py/tf2_ros/buffer.py)
- [tf2 TransformListener](https://github.com/ros2/geometry2/blob/jazzy/tf2_ros_py/tf2_ros/transform_listener.py)

## Diagnostic self-checks performed

With the real ROS installation and an isolated empty ROS domain (74):

- `python3 scripts/doctor.py --duration 2 --output evidence/doctor-no-stack.json`
  exited **1** after a 2.000-second observation window. All 14 essential checks
  correctly failed because no simulator or Nav2 nodes were present. No stderr.
- Sending SIGINT during a 20-second observation exited **1**, wrote
  `evidence/doctor-interrupted.json` with `interrupted: true`, and produced no
  traceback. The interrupted observation window was 1.907 seconds.

These are expected-failure tests of the diagnostic tool, not navigation results.
The localized running-stack result is a separate acceptance check.
