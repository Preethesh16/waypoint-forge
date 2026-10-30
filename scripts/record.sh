#!/usr/bin/env bash
set -eo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$ROOT/evidence/v1.1"
cd "$ROOT"
duration=${2:-90}
if [[ ! "$duration" =~ ^[0-9]+$ ]] || (( duration < 60 || duration > 120 )); then
    echo 'Recording duration must be an integer from 60 to 120 seconds.' >&2
    exit 2
fi
status_file=evidence/v1.1/live-status.txt
if [ ! -s "$status_file" ]; then
    echo "Initialize the mission with --status-text $status_file before recording." >&2
    exit 1
fi
# Record the actual desktop continuously. The footer reads the mission client's
# atomic status file every frame; results are never synthesized by the recorder.
exec ffmpeg -nostdin -n -f x11grab -video_size 1600x900 -framerate 20 \
    -i "${DISPLAY:-:99}" -t "$duration" \
    -vf "drawbox=x=0:y=0:w=1600:h=76:color=0x101826:t=fill,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='WAYPOINT FORGE  /  GAZEBO':x=24:y=12:fontsize=24:fontcolor=white,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='TurtleBot3 Burger  |  Physics and lidar':x=24:y=46:fontsize=17:fontcolor=0xaec6d5,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='RVIZ  /  NAVIGATION2':x=824:y=12:fontsize=24:fontcolor=white,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Blue = global path   Green = local plan   Shading = obstacle costs':x=824:y=46:fontsize=17:fontcolor=0xaec6d5,drawbox=x=0:y=810:w=1600:h=90:color=0x101826:t=fill,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:textfile=$status_file:reload=1:expansion=none:x=24:y=827:fontsize=21:line_spacing=9:fontcolor=white,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='LIVE ACTION FEEDBACK':x=1200:y=829:fontsize=18:fontcolor=0xaec6d5,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Normal speed | No teleoperation':x=1200:y=860:fontsize=16:fontcolor=white" \
    -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p -threads 2 \
    -movflags +faststart "${1:-$ROOT/evidence/v1.1/demo.mp4}"
