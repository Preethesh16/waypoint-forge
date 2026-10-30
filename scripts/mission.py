#!/usr/bin/env python3
"""Send real Nav2 actions and save measured results; never commands robot velocity."""
import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
from rclpy.parameter import Parameter
from rclpy.signals import SignalHandlerOptions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='evidence/mission.json')
    parser.add_argument('--timeout', type=float, default=150.0, help='Wall seconds per goal')
    parser.add_argument('--goals', default='[[1.5, 1.5, 3.14159], [-1.5, 1.5, -1.5708]]')
    args = parser.parse_args()
    try:
        goals = json.loads(args.goals)
    except json.JSONDecodeError as error:
        parser.error(f'--goals is not valid JSON: {error.msg}')
    if not isinstance(goals, list) or not goals or any(
        not isinstance(g, list) or len(g) != 3 or not all(
            type(v) in (int, float) and math.isfinite(v) for v in g
        ) for g in goals
    ):
        parser.error('--goals must be a nonempty list of finite [x, y, yaw] triples')
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be positive and finite')
    # Keep the ROS context alive while Ctrl-C requests bounded action cancellation.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    nav = BasicNavigator()
    nav.set_parameters([Parameter('use_sim_time', value=True)])
    measurements = {'distance_m': 0.0, 'nearest_scan_return_m': None, 'amcl_pose': None}
    last_odom = None

    def odom_cb(msg):
        nonlocal last_odom
        p = msg.pose.pose.position
        if last_odom is not None:
            measurements['distance_m'] += math.hypot(p.x - last_odom[0], p.y - last_odom[1])
        last_odom = (p.x, p.y)

    def scan_cb(msg):
        valid = [r for r in msg.ranges if math.isfinite(r) and msg.range_min <= r <= msg.range_max]
        if valid:
            old = measurements['nearest_scan_return_m']
            measurements['nearest_scan_return_m'] = min(min(valid), old if old is not None else math.inf)

    def pose_cb(msg):
        p = msg.pose.pose.position
        measurements['amcl_pose'] = [p.x, p.y]

    nav.create_subscription(Odometry, '/odom', odom_cb, qos_profile_sensor_data)
    nav.create_subscription(LaserScan, '/scan', scan_cb, qos_profile_sensor_data)
    nav.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', pose_cb, 10)

    def pose(x, y, yaw):
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = nav.get_clock().now().to_msg()
        msg.pose.position.x, msg.pose.position.y = float(x), float(y)
        msg.pose.orientation.z = math.sin(yaw / 2)
        msg.pose.orientation.w = math.cos(yaw / 2)
        return msg

    report = {'initial_pose': [-2.0, -0.5, 0.0], 'goals': [], 'all_succeeded': False,
              'note': 'Distance is odometry-derived. Scan minimum is sensor range, not footprint clearance or a collision guarantee.'}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def cancel_bounded():
        if not nav.goal_handle or not nav.result_future or nav.result_future.done():
            return {'requested': False}
        future = nav.goal_handle.cancel_goal_async()
        rclpy.spin_until_future_complete(nav, future, timeout_sec=3.0)
        acknowledged = future.done() and future.exception() is None
        rclpy.spin_until_future_complete(nav, nav.result_future, timeout_sec=3.0)
        complete = nav.result_future.done()
        if complete:
            nav.isTaskComplete()  # Refresh BasicNavigator.status from terminal result.
        return {'requested': True, 'response_received': acknowledged,
                'terminal_result_received': complete}

    try:
        nav.setInitialPose(pose(-2.0, -0.5, 0.0))
        nav.waitUntilNav2Active()
        for index, (x, y, yaw) in enumerate(goals, 1):
            begin = time.monotonic()
            distance_start = measurements['distance_m']
            measurements['nearest_scan_return_m'] = None
            print(f'MISSION {index}/{len(goals)}: goal ({x}, {y})', flush=True)
            accepted = nav.goToPose(pose(x, y, yaw))
            timed_out = False
            cancellation = None
            if accepted:
                while not nav.isTaskComplete():
                    if time.monotonic() - begin > args.timeout:
                        timed_out = True
                        cancellation = cancel_bounded()
                        break
                result = nav.getResult() if nav.result_future.done() else TaskResult.UNKNOWN
            else:
                result = TaskResult.FAILED
            estimated_pose = measurements['amcl_pose']
            row = {'goal': [x, y, yaw], 'result': str(result),
                   'succeeded': result == TaskResult.SUCCEEDED and not timed_out,
                   'timed_out': timed_out, 'wall_seconds': round(time.monotonic() - begin, 3),
                   'cancellation': cancellation,
                   'distance_m': round(measurements['distance_m'] - distance_start, 3),
                   'nearest_scan_return_m': measurements['nearest_scan_return_m'],
                   'final_amcl_xy': estimated_pose,
                   'estimated_goal_error_m': math.hypot(estimated_pose[0]-x, estimated_pose[1]-y) if estimated_pose else None}
            report['goals'].append(row)
            output.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(row), flush=True)
            if not row['succeeded']:
                break
        report['all_succeeded'] = len(report['goals']) == len(goals) and all(g['succeeded'] for g in report['goals'])
    except KeyboardInterrupt:
        report['interrupted'] = True
        report['cancellation'] = cancel_bounded()
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['cancellation'] = cancel_bounded()
        print(report['error'], flush=True)
    finally:
        output.write_text(json.dumps(report, indent=2) + '\n')
        nav.destroy_node()
        rclpy.shutdown()
    return 0 if report['all_succeeded'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
