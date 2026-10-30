#!/usr/bin/env bash
set -eo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-73}
cd "$ROOT"
# Includes a bounded wait for the Nav2 lifecycle and initial localization.
exec timeout --signal=INT --kill-after=10 420 python3 scripts/mission.py "$@"
