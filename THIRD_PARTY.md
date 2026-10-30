# Upstream components

- TurtleBot3 simulation, model and map: ROBOTIS, Apache-2.0.
  https://github.com/ROBOTIS-GIT/turtlebot3_simulations/tree/jazzy
  https://github.com/ROBOTIS-GIT/turtlebot3/tree/jazzy
- `config/nav2.yaml` is based on ROBOTIS' Jazzy Burger navigation parameters:
  https://github.com/ROBOTIS-GIT/turtlebot3/blob/jazzy/turtlebot3_navigation2/param/burger.yaml
- `config/navigation.rviz` adapts the ROBOTIS navigation view for a compact demo:
  https://github.com/ROBOTIS-GIT/turtlebot3/blob/jazzy/turtlebot3_navigation2/rviz/tb3_navigation2.rviz
- ROS 2 Navigation2 and Simple Commander: upstream Navigation2.
  https://github.com/ros-navigation/navigation2/tree/jazzy
- `config/gazebo.config` adapts the installed Gazebo Sim 8 default GUI
  configuration (Apache-2.0), keeping the scene/control plugins and setting a
  compact overhead view: https://github.com/gazebosim/gz-sim/tree/gz-sim8

The robot, world, map, RViz configuration and navigation algorithms are provided
by their installed upstream packages. This repository supplies the launch
integration, repeatable mission, evidence collection and setup documentation.

Official setup references:
https://emanual.robotis.com/docs/en/platform/turtlebot3/simulation/
https://emanual.robotis.com/docs/en/platform/turtlebot3/nav_simulation/
https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/

AI assistance was used for setup, implementation, debugging and documentation.
Recorded runs and measurements must come from the actual ROS/Gazebo execution.
