#!/usr/bin/env bash
set -eo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source /opt/ros/jazzy/setup.bash
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-73}
# Isolate Gazebo transport as well as DDS, including from an older failed run.
export GZ_PARTITION=${GZ_PARTITION:-antropi_${ROS_DOMAIN_ID}_$$}
# The upstream Gazebo launcher uses shell/ruby children. Signal their entire
# process group so they cannot survive a restart and publish a second clock.
setsid ros2 launch "$ROOT/launch/demo.launch.py" &
launch_pid=$!
cleanup() {
    trap - EXIT INT TERM
    # Let ROS launch shut down its nodes in order before cleaning any wrappers
    # or grandchildren it failed to reap (notably the Gazebo ruby processes).
    kill -INT "$launch_pid" 2>/dev/null || true
    for _ in $(seq 1 50); do
        kill -0 -- "-$launch_pid" 2>/dev/null || break
        sleep 0.1
    done
    kill -TERM -- "-$launch_pid" 2>/dev/null || true
    sleep 0.2
    kill -KILL -- "-$launch_pid" 2>/dev/null || true
    wait "$launch_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
wait "$launch_pid"
