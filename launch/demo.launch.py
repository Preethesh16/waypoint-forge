"""Launch the upstream TurtleBot3 world and Nav2 with explicit simulation time."""
from pathlib import Path
import shlex

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.actions import AppendEnvironmentVariable
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    root = Path(__file__).resolve().parents[1]

    def include(package, filename, condition=None, **arguments):
        path = Path(get_package_share_directory(package)) / 'launch' / filename
        return IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(path)),
            launch_arguments=arguments.items(),
            condition=condition,
        )

    gazebo_share = Path(get_package_share_directory('turtlebot3_gazebo'))
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true',
                              description='Show Gazebo and RViz; false retains physics and sensors'),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', str(gazebo_share / 'models')),
        include('ros_gz_sim', 'gz_sim.launch.py',
                gz_args=f'-r -s -v2 {shlex.quote(str(gazebo_share / "worlds" / "turtlebot3_world.world"))}',
                on_exit_shutdown='true'),
        include('ros_gz_sim', 'gz_sim.launch.py',
                condition=IfCondition(LaunchConfiguration('gui')),
                gz_args=f'-g -v2 --gui-config {shlex.quote(str(root / "config" / "gazebo.config"))}',
                on_exit_shutdown='true'),
        include('turtlebot3_gazebo', 'robot_state_publisher.launch.py', use_sim_time='true'),
        include('turtlebot3_gazebo', 'spawn_turtlebot3.launch.py', x_pose='-2.0', y_pose='-0.5'),
        include('nav2_bringup', 'bringup_launch.py',
                use_sim_time='true', params_file=str(root / 'config' / 'nav2.yaml'),
                map=str(Path(get_package_share_directory('turtlebot3_navigation2')) / 'map' / 'map.yaml')),
        Node(package='rviz2', executable='rviz2', name='rviz2',
             condition=IfCondition(LaunchConfiguration('gui')),
             arguments=['-d', str(root / 'config' / 'navigation.rviz')],
             parameters=[{'use_sim_time': True}], output='screen'),
    ])
