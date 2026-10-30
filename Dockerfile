FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
       -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main' \
       > /etc/apt/sources.list.d/ros2.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       ros-jazzy-turtlebot3-gazebo ros-jazzy-turtlebot3-navigation2 \
       ros-jazzy-nav2-simple-commander ros-jazzy-rviz2 ros-jazzy-ros2launch \
       xvfb openbox x11-utils x11vnc novnc websockify ffmpeg \
    && rm -rf /var/lib/apt/lists/*
ENV TURTLEBOT3_MODEL=burger ROS_DOMAIN_ID=73 DISPLAY=:99
WORKDIR /demo
COPY . /demo
CMD ["bash", "scripts/desktop.sh"]
