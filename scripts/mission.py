#!/usr/bin/env python3
"""Send real Nav2 actions and save measured results; never commands robot velocity."""
import argparse
import json
import math
import os
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rclpy.clock import Clock, ClockType
from rclpy.qos import (qos_profile_sensor_data, QoSProfile,
                      DurabilityPolicy, ReliabilityPolicy)
from rclpy.parameter import Parameter
from rclpy.signals import SignalHandlerOptions

MAX_TRAJECTORY_SAMPLES = 2000
POSE_MAX_AGE = 2.0


def atomic_write(path, text):
    """Readers see either the previous complete document or the new one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    try:
        temporary.write_text(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def stamp_seconds(stamp):
    return stamp.sec + stamp.nanosec / 1e9


def pose_sample(msg, source, received_wall):
    """Return a finite map-frame pose; other coordinate frames are not comparable."""
    p = msg.pose.position
    if msg.header.frame_id != 'map' or not all(math.isfinite(v) for v in (p.x, p.y)):
        return None
    return {'source': source, 'frame': 'map', 'xy': [p.x, p.y],
            'stamp_sim_seconds': stamp_seconds(msg.header.stamp),
            'received_wall': received_wall}


def assess_pose(sample, now_sim, now_wall, max_age=POSE_MAX_AGE):
    if sample is None:
        return None
    age_sim = now_sim - sample['stamp_sim_seconds']
    age_wall = now_wall - sample['received_wall']
    return {key: value for key, value in sample.items() if key != 'received_wall'} | {
        'age_sim_seconds': age_sim, 'age_wall_seconds': age_wall,
        'fresh': -0.1 <= age_sim <= max_age and 0 <= age_wall <= max_age}


def freshest_pose(samples, now_sim, now_wall):
    assessed = [assess_pose(s, now_sim, now_wall) for s in samples if s is not None]
    if not assessed:
        return None
    # Prefer a demonstrably fresh estimate; preserve stale evidence but label it.
    return max(assessed, key=lambda s: (s['fresh'], s['stamp_sim_seconds']))


def status_text(status):
    phase = status['phase']
    if phase == 'navigating':
        goal = status['goal']
        first = f"GOAL {status['goal_index']}/{status['goal_count']} | ({goal[0]:.2f}, {goal[1]:.2f}) m"
    else:
        first = phase.replace('_', ' ').upper()
    second = f"Elapsed {status['wall_seconds']:.1f}s wall | {status['sim_seconds']:.1f}s sim"
    feedback = status.get('feedback')
    if feedback and feedback.get('fresh') and feedback.get('distance_remaining_m') is not None:
        second += f" | Remaining {feedback['distance_remaining_m']:.2f} m"
    elif phase == 'navigating':
        second += ' | Waiting for fresh feedback'
    return first + '\n' + second + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='evidence/mission.json')
    parser.add_argument('--timeout', type=float, default=150.0, help='Wall seconds per goal')
    parser.add_argument('--goals', default='[[1.5, 1.5, 3.14159], [-1.5, 1.5, -1.5708]]')
    parser.add_argument('--status-json', help='Atomic live status JSON: 2 Hz periodic updates plus phase changes')
    parser.add_argument('--status-text', help='Atomic two-line live text for video overlays')
    parser.add_argument('--initialize-only', action='store_true', help='Localize and wait for Nav2; send no goals')
    parser.add_argument('--skip-initial-pose', action='store_true', help='Use existing AMCL localization; never publish initialpose')
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
    paths = [str(Path(p).resolve()) for p in (args.output, args.status_json, args.status_text) if p]
    if len(paths) != len(set(paths)):
        parser.error('output, status-json and status-text must use different paths')

    mission_begin = time.monotonic()
    status = {'phase': 'waiting_for_localization', 'goal_index': None,
              'goal_count': len(goals), 'goal': None, 'wall_seconds': 0.0,
              'sim_seconds': 0.0, 'feedback': None}

    def write_status():
        if args.status_json:
            atomic_write(args.status_json, json.dumps(status, indent=2, allow_nan=False) + '\n')
        if args.status_text:
            atomic_write(args.status_text, status_text(status))

    # Create overlay inputs before ROS discovery/readiness can block.
    write_status()
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    nav = BasicNavigator()
    nav.set_parameters([Parameter('use_sim_time', value=True)])
    measurements = {'distance_m': 0.0, 'nearest_scan_return_m': None,
                    'amcl_pose': None, 'feedback_pose': None, 'invalid_odom_samples': 0}
    last_odom = None
    current = None
    last_feedback_message = None
    first_clock = None

    def sim_now():
        return nav.get_clock().now().nanoseconds / 1e9

    def odom_cb(msg):
        nonlocal last_odom
        p = msg.pose.pose.position
        if not all(math.isfinite(v) for v in (p.x, p.y)):
            measurements['invalid_odom_samples'] += 1
            last_odom = None
            return
        if last_odom is not None:
            measurements['distance_m'] += math.hypot(p.x - last_odom[0], p.y - last_odom[1])
        last_odom = (p.x, p.y)

    def scan_cb(msg):
        valid = [r for r in msg.ranges if math.isfinite(r) and msg.range_min <= r <= msg.range_max]
        if valid:
            old = measurements['nearest_scan_return_m']
            measurements['nearest_scan_return_m'] = min(min(valid), old if old is not None else math.inf)

    def pose_cb(msg):
        sample = PoseStamped(header=msg.header, pose=msg.pose.pose)
        measurements['amcl_pose'] = pose_sample(sample, 'amcl', time.monotonic())

    nav.create_subscription(Odometry, '/odom', odom_cb, qos_profile_sensor_data)
    nav.create_subscription(LaserScan, '/scan', scan_cb, qos_profile_sensor_data)
    nav.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', pose_cb,
                            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                                       reliability=ReliabilityPolicy.RELIABLE))

    def collect_feedback():
        nonlocal last_feedback_message
        feedback = nav.getFeedback()
        if current is None or feedback is None or feedback is last_feedback_message:
            return
        last_feedback_message = feedback
        now = time.monotonic()
        sample = pose_sample(feedback.current_pose, 'nav2_feedback', now)
        if sample:
            measurements['feedback_pose'] = sample
        remaining = float(feedback.distance_remaining)
        current['feedback'] = {'distance_remaining_m': remaining if math.isfinite(remaining) else None,
                               'number_of_recoveries': int(feedback.number_of_recoveries),
                               'navigation_time_seconds': stamp_seconds(feedback.navigation_time),
                               'received_wall': now}
        current['feedback_samples'] += 1
        current['max_recoveries'] = max(current['max_recoveries'], int(feedback.number_of_recoveries))

    def update_status():
        nonlocal first_clock
        # Feedback receipt timestamps are recorded during collection. Take the
        # snapshot clock afterwards so a newly received sample cannot have a
        # negative age merely because of callback ordering.
        collect_feedback()
        now, sim = time.monotonic(), sim_now()
        if first_clock is None and sim > 0:
            first_clock = sim
        status.update(wall_seconds=round(now - mission_begin, 3),
                      sim_seconds=round(sim - first_clock, 3) if first_clock is not None else 0.0)
        if current is not None:
            feedback = current['feedback']
            if feedback:
                status['feedback'] = {k: v for k, v in feedback.items() if k != 'received_wall'} | {
                    'age_wall_seconds': now - feedback['received_wall'],
                    'fresh': now - feedback['received_wall'] <= POSE_MAX_AGE}
            chosen = freshest_pose([measurements['amcl_pose'], measurements['feedback_pose']], sim, now)
            if chosen and chosen['fresh'] and now - current['last_sample_wall'] >= 0.5:
                if len(current['trajectory']) < MAX_TRAJECTORY_SAMPLES:
                    current['trajectory'].append({'source': chosen['source'], 'xy': chosen['xy'],
                        'stamp_sim_seconds': chosen['stamp_sim_seconds'],
                        'wall_seconds': round(now - current['begin_wall'], 3)})
                else:
                    current['trajectory_truncated'] = True
                current['last_sample_wall'] = now
        write_status()

    timer = nav.create_timer(0.5, update_status, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def pose(x, y, yaw):
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = nav.get_clock().now().to_msg()
        msg.pose.position.x, msg.pose.position.y = float(x), float(y)
        msg.pose.orientation.z = math.sin(yaw / 2)
        msg.pose.orientation.w = math.cos(yaw / 2)
        return msg

    report = {'schema_version': 2, 'initial_pose': [-2.0, -0.5, 0.0],
              'initial_pose_published': not args.skip_initial_pose,
              'initialize_only': args.initialize_only, 'initialization_succeeded': False,
              'goals': [], 'all_succeeded': False,
              'note': 'Distance is odometry-derived. Final goal error uses a fresh map-frame feedback/AMCL estimate, not ground truth. Scan minimum is sensor range, not footprint clearance or a collision guarantee.'}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def save_report():
        atomic_write(output, json.dumps(report, indent=2, allow_nan=False) + '\n')

    def cancel_bounded():
        if not nav.goal_handle or not nav.result_future or nav.result_future.done():
            return {'requested': False}
        future = nav.goal_handle.cancel_goal_async()
        rclpy.spin_until_future_complete(nav, future, timeout_sec=3.0)
        acknowledged = future.done() and future.exception() is None
        rclpy.spin_until_future_complete(nav, nav.result_future, timeout_sec=3.0)
        complete = nav.result_future.done()
        if complete:
            nav.isTaskComplete()
        return {'requested': True, 'response_received': acknowledged,
                'terminal_result_received': complete}

    try:
        if args.skip_initial_pose:
            # BasicNavigator otherwise republishes its default pose while waiting.
            # Wait for AMCL's transient-local estimate first, without resetting it.
            while not nav.initial_pose_received:
                rclpy.spin_once(nav, timeout_sec=0.1)
        else:
            nav.setInitialPose(pose(-2.0, -0.5, 0.0))
        nav.waitUntilNav2Active()
        report['initialization_succeeded'] = True
        status['phase'] = 'initialized_no_goals' if args.initialize_only else 'ready'
        update_status()
        for index, (x, y, yaw) in enumerate([] if args.initialize_only else goals, 1):
            begin, begin_sim = time.monotonic(), sim_now()
            distance_start = measurements['distance_m']
            measurements['nearest_scan_return_m'] = None
            measurements['feedback_pose'] = None
            nav.feedback = None
            last_feedback_message = None
            current = {'begin_wall': begin, 'feedback': None, 'feedback_samples': 0,
                       'max_recoveries': 0, 'trajectory': [], 'trajectory_truncated': False,
                       'last_sample_wall': -math.inf}
            status.update(phase='navigating', goal_index=index, goal=[x, y, yaw], feedback=None)
            update_status()
            print(f'MISSION {index}/{len(goals)}: goal ({x}, {y})', flush=True)
            accepted = nav.goToPose(pose(x, y, yaw))
            timed_out = False
            cancellation = None
            if accepted:
                while not nav.isTaskComplete():
                    collect_feedback()
                    if time.monotonic() - begin > args.timeout:
                        timed_out = True
                        cancellation = cancel_bounded()
                        break
                result = nav.getResult() if nav.result_future.done() else TaskResult.UNKNOWN
            else:
                result = TaskResult.FAILED
            collect_feedback()
            now, now_sim = time.monotonic(), sim_now()
            final_pose = freshest_pose([measurements['amcl_pose'], measurements['feedback_pose']], now_sim, now)
            amcl = assess_pose(measurements['amcl_pose'], now_sim, now)
            feedback = current['feedback']
            row = {'goal': [x, y, yaw], 'result': str(result),
                   'succeeded': result == TaskResult.SUCCEEDED and not timed_out,
                   'timed_out': timed_out, 'wall_seconds': round(now - begin, 3),
                   'sim_seconds': round(now_sim - begin_sim, 3),
                   'sim_start_seconds': begin_sim, 'sim_end_seconds': now_sim,
                   'cancellation': cancellation,
                   'distance_m': round(measurements['distance_m'] - distance_start, 3),
                   'nearest_scan_return_m': measurements['nearest_scan_return_m'],
                   'final_amcl_xy': amcl['xy'] if amcl else None,
                   'final_amcl_estimate': amcl, 'final_pose_estimate': final_pose,
                   'estimated_goal_error_m': math.hypot(final_pose['xy'][0]-x, final_pose['xy'][1]-y)
                       if final_pose and final_pose['fresh'] else None,
                   'feedback_samples': current['feedback_samples'],
                   'max_recoveries': current['max_recoveries'],
                   'last_feedback': {k: v for k, v in feedback.items() if k != 'received_wall'} | {
                       'age_wall_seconds': now-feedback['received_wall']} if feedback else None,
                   'trajectory': current['trajectory'],
                   'trajectory_truncated': current['trajectory_truncated']}
            report['goals'].append(row)
            save_report()
            print(json.dumps({k: v for k, v in row.items() if k != 'trajectory'}), flush=True)
            current = None
            if not row['succeeded']:
                break
        report['all_succeeded'] = len(report['goals']) == len(goals) and all(g['succeeded'] for g in report['goals'])
        if not args.initialize_only:
            status['phase'] = 'mission_succeeded' if report['all_succeeded'] else 'mission_failed'
    except KeyboardInterrupt:
        report['interrupted'] = True
        report['cancellation'] = cancel_bounded()
        status['phase'] = 'interrupted'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['cancellation'] = cancel_bounded()
        status['phase'] = 'error'
        print(report['error'], flush=True)
    finally:
        timer.cancel()
        update_status()
        if current is not None and (report.get('interrupted') or report.get('error')):
            report['unfinished_goal'] = {
                'goal': status['goal'], 'wall_seconds': round(time.monotonic() - current['begin_wall'], 3),
                'feedback_samples': current['feedback_samples'], 'max_recoveries': current['max_recoveries'],
                'trajectory': current['trajectory'], 'trajectory_truncated': current['trajectory_truncated']}
        report['wall_seconds'] = round(time.monotonic() - mission_begin, 3)
        report['sim_seconds'] = status['sim_seconds']
        report['invalid_odom_samples'] = measurements['invalid_odom_samples']
        save_report()
        nav.destroy_node()
        rclpy.shutdown()
    return 0 if report['all_succeeded'] or (args.initialize_only and report['initialization_succeeded']
                                           and not report.get('interrupted') and not report.get('error')) else 1


if __name__ == '__main__':
    raise SystemExit(main())
