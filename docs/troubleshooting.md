# Troubleshooting

## Initial pose and repeated runs

The mission assumes a fresh simulation with the robot at `(-2.0, -0.5, 0)`.
Restart the launch before repeating it. Reinitializing AMCL to the spawn position
while the robot is elsewhere is incorrect. Gazebo and Nav2 must both use the
same `/clock`, and both terminals must use the same `ROS_DOMAIN_ID` (default 73).

## Waiting for AMCL or the navigation action

Check the launch terminal for node failures. After localization, run the
read-only diagnostic script described in [diagnostics](diagnostics.md).
`map → odom` is not expected before AMCL receives an initial pose. The mission
provides that pose automatically. The shell wrapper bounds startup and task
waiting; nonzero exit status must not be treated as a successful run.

## Display or renderer problems

Use a working desktop display on native Ubuntu. In Docker, open the local noVNC
desktop before judging whether RViz or Gazebo is visible. Software rendering
uses CPU and may lower simulation real-time factor. If needed, set
`LIBGL_ALWAYS_SOFTWARE=1` when launching inside the virtual desktop.

## Disk space

The ROS/Gazebo dependency graph is large. Leave at least 5 GB available for the
container image and installation, plus room for recordings. Check both the
Docker storage filesystem and the project filesystem. The development host had
separate nearly-full root and home partitions; its isolated container used
workspace-backed runtime directories. Those local directories are not project
source and must not be committed.

## Failed or interrupted mission

Read `evidence/mission.json` and the launch logs. The client stops after the
first failed/timed-out goal. Cancellation requests have bounded response and
terminal-result waits. If the action server has disappeared, cancellation cannot
be guaranteed; stop the simulation and restart it before the next test.

The outer process deadline is a last-resort bound, not an emergency stop for a
physical robot. This project is for simulation only.

Use Docker's `--init` option as shown in the README, so an init process reaps
orphaned children after shutdown. The temporary development container used
`sleep` as PID 1; testing confirmed no live simulation processes remained, but
that bootstrap container could retain harmless zombie process entries.
