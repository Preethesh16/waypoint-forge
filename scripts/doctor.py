#!/usr/bin/env python3
"""Observe a localized TurtleBot3/Nav2 stack without changing robot state."""
import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformException, TransformListener


def seconds(stamp):
    return stamp.sec + stamp.nanosec / 1e9


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=10.0,
                        help='Observation window in wall seconds (default: 10)')
    parser.add_argument('--max-age', type=float, default=2.0,
                        help='Maximum sensor age in wall and simulation seconds')
    parser.add_argument('--output', help='Optional JSON evidence path')
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration < 1:
        parser.error('--duration must be finite and at least 1 second')
    if not math.isfinite(args.max_age) or args.max_age <= 0:
        parser.error('--max-age must be positive and finite')

    # Keep the context alive through Python KeyboardInterrupt so JSON and node
    # cleanup remain available. No robot action is active in this tool.
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = Node('antropi_navigation_doctor', parameter_overrides=[
        Parameter('use_sim_time', value=True)])
    buffers = {key: {'count': 0, 'first_stamp': None, 'last_stamp': None,
                     'last_wall': None, 'backward_jumps': 0, 'message': None}
               for key in ('clock', 'scan', 'odom')}

    def receive(key, msg):
        stamp = seconds(msg.clock if key == 'clock' else msg.header.stamp)
        item = buffers[key]
        if item['first_stamp'] is None:
            item['first_stamp'] = stamp
        if item['last_stamp'] is not None and stamp < item['last_stamp']:
            item['backward_jumps'] += 1
        item.update(count=item['count'] + 1, last_stamp=stamp,
                    last_wall=time.monotonic(), message=msg)

    subscriptions = [
        node.create_subscription(Clock, '/clock', lambda m: receive('clock', m), qos_profile_sensor_data),
        node.create_subscription(LaserScan, '/scan', lambda m: receive('scan', m), qos_profile_sensor_data),
        node.create_subscription(Odometry, '/odom', lambda m: receive('odom', m), qos_profile_sensor_data),
    ]
    tf_buffer = Buffer(node=node)
    listener = TransformListener(tf_buffer, node, spin_thread=False)
    action = ActionClient(node, NavigateToPose, '/navigate_to_pose')
    lifecycle_names = ('amcl', 'controller_server', 'planner_server', 'bt_navigator', 'behavior_server')
    clients = {name: node.create_client(GetState, f'/{name}/get_state') for name in lifecycle_names}
    pending, states, next_query = {}, {}, {}
    start = time.monotonic()
    interrupted = False
    try:
        while time.monotonic() - start < args.duration:
            rclpy.spin_once(node, timeout_sec=min(0.1, max(0.0, args.duration - (time.monotonic() - start))))
            now = time.monotonic()
            for name, client in clients.items():
                future = pending.get(name)
                if future is not None and future.done():
                    try:
                        state = future.result().current_state
                        states[name] = {'id': state.id, 'label': state.label, 'received_wall': now}
                    except Exception as exc:
                        states[name] = {'error': str(exc), 'received_wall': now}
                    pending.pop(name)
                    next_query[name] = now + 0.5
                if name not in pending and now >= next_query.get(name, 0) and client.service_is_ready():
                    pending[name] = client.call_async(GetState.Request())
    except KeyboardInterrupt:
        interrupted = True

    now = time.monotonic()
    clock_time = buffers['clock']['last_stamp']
    checks = {}

    def check(name, passed, **details):
        checks[name] = {'passed': bool(passed), **details}

    for key, item in buffers.items():
        age_wall = now - item['last_wall'] if item['last_wall'] is not None else None
        age_sim = clock_time - item['last_stamp'] if clock_time is not None and item['last_stamp'] is not None else None
        advancing = item['count'] >= 2 and item['last_stamp'] > item['first_stamp']
        fresh = age_wall is not None and age_wall <= args.max_age
        aligned = key == 'clock' or (age_sim is not None and -args.max_age <= age_sim <= args.max_age)
        check(key + '_stream', advancing and fresh and aligned and item['backward_jumps'] == 0,
              topic='/' + key, samples=item['count'], advancing=advancing,
              age_wall_seconds=age_wall, age_sim_seconds=age_sim,
              backward_jumps=item['backward_jumps'])

    scan = buffers['scan']['message']
    if scan is not None:
        valid_limits = math.isfinite(scan.range_min) and math.isfinite(scan.range_max) and 0 <= scan.range_min < scan.range_max
        valid_ranges = [v for v in scan.ranges if math.isfinite(v) and scan.range_min <= v <= scan.range_max]
        check('scan_values', valid_limits and bool(valid_ranges) and bool(scan.header.frame_id),
              frame=scan.header.frame_id, total_beams=len(scan.ranges), valid_beams=len(valid_ranges),
              nearest_return_m=min(valid_ranges) if valid_ranges else None)
    else:
        check('scan_values', False, reason='No laser scan received')

    odom = buffers['odom']['message']
    if odom is not None:
        p, q = odom.pose.pose.position, odom.pose.pose.orientation
        v, w = odom.twist.twist.linear, odom.twist.twist.angular
        finite = all(math.isfinite(x) for x in (p.x, p.y, p.z, q.x, q.y, q.z, q.w,
                                               v.x, v.y, v.z, w.x, w.y, w.z))
        norm = math.sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w)
        check('odom_values', finite and abs(norm - 1) < 0.01 and odom.header.frame_id == 'odom' and bool(odom.child_frame_id),
              frame=odom.header.frame_id, child_frame=odom.child_frame_id, quaternion_norm=norm if math.isfinite(norm) else None)
    else:
        check('odom_values', False, reason='No odometry received')

    pairs = [('map', 'odom', True), ('odom', 'base_footprint', True),
             ('base_footprint', 'base_link', False)]
    if scan is not None and scan.header.frame_id:
        pairs.append(('base_link', scan.header.frame_id, False))
    for target, source, dynamic in pairs:
        try:
            transform = tf_buffer.lookup_transform(target, source, rclpy.time.Time())
            stamp = seconds(transform.header.stamp)
            age = clock_time - stamp if clock_time is not None else None
            # Static robot transforms may legitimately have stamp zero. AMCL can
            # future-date map->odom by its transform_tolerance (0.5 s here).
            fresh = not dynamic or (age is not None and -args.max_age <= age <= args.max_age)
            t, q = transform.transform.translation, transform.transform.rotation
            finite = all(math.isfinite(v) for v in (t.x, t.y, t.z, q.x, q.y, q.z, q.w))
            check(f'tf:{target}<-{source}', fresh and finite, stamp_seconds=stamp,
                  age_sim_seconds=age, dynamic=dynamic)
        except TransformException as exc:
            check(f'tf:{target}<-{source}', False, reason=str(exc))

    for name in lifecycle_names:
        state = states.get(name)
        check('lifecycle:' + name,
              state is not None and state.get('id') == State.PRIMARY_STATE_ACTIVE
              and now - state['received_wall'] <= args.max_age,
              state={k: v for k, v in state.items() if k != 'received_wall'} if state else None,
              response_age_wall_seconds=now - state['received_wall'] if state else None)
    check('navigate_to_pose_action', action.server_is_ready(), action='/navigate_to_pose')
    report = {'passed': not interrupted and all(c['passed'] for c in checks.values()),
              'interrupted': interrupted, 'observation_wall_seconds': round(now - start, 3),
              'checks': checks,
              'scope': 'Read-only snapshot after localization; does not prove navigation success or collision freedom.'}
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2, allow_nan=False))
    action.destroy()
    listener.unregister()
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
