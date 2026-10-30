# Pins match the successful local ROS/Gazebo run; see docs/reproducibility.md.
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/36b9c28fdda0a50288797399da4b5fa1ef0ff81a/ros.key \
       -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main' \
       > /etc/apt/sources.list.d/ros2.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       ros-jazzy-turtlebot3-gazebo=2.3.7-1noble.20261006.041329 ros-jazzy-turtlebot3-navigation2=2.3.6-1noble.20261006.044113 \
       ros-jazzy-nav2-simple-commander=1.3.13-1noble.20260921.030016 ros-jazzy-rviz2=14.1.24-1noble.20260915.204213 ros-jazzy-ros2launch=0.26.13-1noble.20261006.034901 \
       xvfb openbox x11-utils x11vnc novnc websockify ffmpeg \
    && rm -rf /var/lib/apt/lists/*
ENV TURTLEBOT3_MODEL=burger ROS_DOMAIN_ID=73 DISPLAY=:99
WORKDIR /demo
COPY . /demo
RUN mkdir -p /demo/evidence
CMD ["bash", "scripts/desktop.sh"]
