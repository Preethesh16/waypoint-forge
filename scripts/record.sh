#!/usr/bin/env bash
set -eo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$ROOT/evidence"
# Record the actual virtual desktop continuously, with a descriptive footer.
# No synthesized robot motion, speed-up or success claims are added.
exec ffmpeg -nostdin -n -f x11grab -video_size 1600x900 -framerate 20 \
    -i "${DISPLAY:-:99}" -t 75 \
    -vf "drawbox=x=0:y=860:w=1600:h=40:color=0x101826:t=fill,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='GAZEBO  |  TurtleBot3 Burger':x=22:y=871:fontsize=20:fontcolor=white,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='RVIZ  |  ROS 2 Jazzy + Nav2 autonomous mission':x=815:y=871:fontsize=20:fontcolor=white" \
    -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p -threads 2 \
    -movflags +faststart "${1:-$ROOT/evidence/demo.mp4}"
