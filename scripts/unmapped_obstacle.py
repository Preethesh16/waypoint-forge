#!/usr/bin/env python3
"""Simulation-only crate creation or read-only evidence of Nav2 costmap marking."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

CRATE_NAME = 'waypoint_crate'
CENTER = (0.0, 1.65)
HALF_SIZE = 0.25
PROBE_HALF_SIZE = HALF_SIZE + 0.05  # One 5 cm cell margin for boundary quantization.
SERVICE = '/world/default/create'


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def seconds(stamp):
    return stamp.sec + stamp.nanosec / 1e9


def patch(grid):
    """Extract cell centers inside the crate region plus one 5 cm cell margin, including origin yaw."""
    info = grid.info
    if grid.header.frame_id != 'map':
        raise ValueError('Expected OccupancyGrid in map frame')
    if not math.isfinite(info.resolution) or info.resolution <= 0:
        raise ValueError('Invalid occupancy grid resolution')
    if info.width <= 0 or info.height <= 0 or len(grid.data) != info.width * info.height:
        raise ValueError('Invalid occupancy grid dimensions/data size')
    p, q = info.origin.position, info.origin.orientation
    if not all(math.isfinite(v) for v in (p.x, p.y, q.x, q.y, q.z, q.w)):
        raise ValueError('Nonfinite occupancy grid origin')
    if abs(q.x) > 1e-6 or abs(q.y) > 1e-6 or abs(q.z*q.z + q.w*q.w - 1) > 0.01:
        raise ValueError('Expected normalized planar occupancy grid origin')
    yaw = 2 * math.atan2(q.z, q.w)
    c, s = math.cos(yaw), math.sin(yaw)

    def local(x, y):
        return c * (x-p.x) + s * (y-p.y), -s * (x-p.x) + c * (y-p.y)

    corners = [local(CENTER[0]+dx, CENTER[1]+dy)
               for dx in (-PROBE_HALF_SIZE, PROBE_HALF_SIZE) for dy in (-PROBE_HALF_SIZE, PROBE_HALF_SIZE)]
    # Reject clipping: every corner of the requested footprint must be represented.
    covered = all(0 <= x <= info.width * info.resolution and
                  0 <= y <= info.height * info.resolution for x, y in corners)
    xmin = max(0, math.floor(min(x for x, y in corners)/info.resolution))
    xmax = min(info.width-1, math.floor(max(x for x, y in corners)/info.resolution))
    ymin = max(0, math.floor(min(y for x, y in corners)/info.resolution))
    ymax = min(info.height-1, math.floor(max(y for x, y in corners)/info.resolution))
    cells = []
    for gy in range(ymin, ymax+1):
        for gx in range(xmin, xmax+1):
            lx, ly = (gx+0.5)*info.resolution, (gy+0.5)*info.resolution
            x, y = p.x + c*lx - s*ly, p.y + s*lx + c*ly
            if abs(x-CENTER[0]) <= PROBE_HALF_SIZE + 1e-9 and abs(y-CENTER[1]) <= PROBE_HALF_SIZE + 1e-9:
                cells.append({'grid_xy': [gx, gy], 'world_xy': [round(x, 6), round(y, 6)],
                              'value': int(grid.data[gy*info.width+gx])})
    values = [cell['value'] for cell in cells]
    return {'frame': grid.header.frame_id, 'stamp_sim_seconds': seconds(grid.header.stamp),
            'resolution_m': info.resolution, 'grid_size': [info.width, info.height],
            'probe_region_fully_covered': covered, 'cell_count': len(values),
            'free_cells': values.count(0), 'lethal_cells': values.count(100),
            'unknown_cells': values.count(-1), 'cells': cells}


def spawn(partition):
    sdf = Path(__file__).resolve().parents[1] / 'config' / 'unmapped_crate.sdf'
    request = f'sdf_filename: {json.dumps(str(sdf))} name: "{CRATE_NAME}" allow_renaming: false'
    command = ['gz', 'service', '-s', SERVICE, '--reqtype', 'gz.msgs.EntityFactory',
               '--reptype', 'gz.msgs.Boolean', '--timeout', '5000', '--req', request]
    begin = time.monotonic()
    report = {'mode': 'spawn', 'started_at_utc': timestamp(), 'gz_partition': partition,
              'service': SERVICE, 'entity_name': CRATE_NAME, 'sdf': str(sdf),
              'center_xyz_m': [*CENTER, 0.3], 'size_xyz_m': [0.5, 0.5, 0.6],
              'creation_service_accepted': False}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
        report.update(returncode=result.returncode, stdout=result.stdout.strip(), stderr=result.stderr.strip())
        report['creation_service_accepted'] = result.returncode == 0 and bool(
            re.search(r'^\s*data:\s*true\s*$', result.stdout, flags=re.MULTILINE))
    except (subprocess.TimeoutExpired, OSError) as error:
        report['error'] = f'{type(error).__name__}: {error}'
    report['wall_seconds'] = round(time.monotonic()-begin, 3)
    report['note'] = 'Service acceptance is not proof of costmap detection or collision freedom. Use --observe and inspect Gazebo.'
    return report, report['creation_service_accepted']


def observe(partition, duration):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    from nav_msgs.msg import OccupancyGrid
    from rosgraph_msgs.msg import Clock

    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = Node('unmapped_obstacle_observer')
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)
    maps = {'static_map': None, 'live_costmap': None}
    received = {'static_map': None, 'live_costmap': None}
    counts = {'static_map': 0, 'live_costmap': 0}
    errors = {}
    clock = {'first': None, 'last': None, 'received': None, 'backward': False}
    first_costmap_stamp = None
    costmap_backward = False
    previous_costmap_stamp = None

    def map_callback(kind, msg):
        nonlocal first_costmap_stamp, costmap_backward, previous_costmap_stamp
        counts[kind] += 1
        received[kind] = time.monotonic()
        try:
            maps[kind] = patch(msg)
            errors.pop(kind, None)
            if kind == 'live_costmap':
                stamp = maps[kind]['stamp_sim_seconds']
                if first_costmap_stamp is None:
                    first_costmap_stamp = stamp
                if previous_costmap_stamp is not None and stamp < previous_costmap_stamp:
                    costmap_backward = True
                previous_costmap_stamp = stamp
        except ValueError as error:
            maps[kind] = None
            errors[kind] = str(error)

    def clock_callback(msg):
        now = seconds(msg.clock)
        if clock['first'] is None:
            clock['first'] = now
        if clock['last'] is not None and now < clock['last']:
            clock['backward'] = True
        clock.update(last=now, received=time.monotonic())

    subscriptions = [
        node.create_subscription(OccupancyGrid, '/map', lambda msg: map_callback('static_map', msg), qos),
        node.create_subscription(OccupancyGrid, '/global_costmap/costmap', lambda msg: map_callback('live_costmap', msg), qos),
        node.create_subscription(Clock, '/clock', clock_callback, qos_profile_sensor_data),
    ]
    begin = time.monotonic()
    report = {'mode': 'observe', 'started_at_utc': timestamp(), 'gz_partition': partition,
              'ros_domain_id': os.environ.get('ROS_DOMAIN_ID', '0'),
              'entity_name': CRATE_NAME, 'center_xy_m': list(CENTER), 'footprint_size_xy_m': [0.5, 0.5],
              'probe_region_size_xy_m': [2*PROBE_HALF_SIZE, 2*PROBE_HALF_SIZE],
              'passed': False, 'interrupted': False}

    def conditions():
        static, live = maps['static_map'], maps['live_costmap']
        now = time.monotonic()
        return {
            'static_map_region_free': bool(static and static['probe_region_fully_covered'] and
                static['cell_count'] > 0 and static['free_cells'] == static['cell_count']),
            'live_costmap_region_lethal': bool(live and live['probe_region_fully_covered'] and live['lethal_cells'] > 0),
            'live_costmap_advancing': bool(live and counts['live_costmap'] >= 2 and
                first_costmap_stamp is not None and live['stamp_sim_seconds'] > first_costmap_stamp and not costmap_backward),
            'live_costmap_fresh': bool(live and received['live_costmap'] is not None and
                now-received['live_costmap'] <= 2 and clock['last'] is not None and
                -0.1 <= clock['last']-live['stamp_sim_seconds'] <= 2),
            'simulation_clock_advancing': bool(clock['first'] is not None and clock['last'] > clock['first'] and
                not clock['backward'] and now-clock['received'] <= 2),
        }

    try:
        while time.monotonic()-begin < duration:
            rclpy.spin_once(node, timeout_sec=min(0.1, max(0, duration-(time.monotonic()-begin))))
            if all(conditions().values()):
                report['passed'] = True
                break
    except KeyboardInterrupt:
        report['interrupted'] = True
    finally:
        report.update(conditions=conditions(), patches=maps, received_samples=counts,
                      errors=errors, wall_seconds=round(time.monotonic()-begin, 3),
                      observed_at_utc=timestamp(), last_sim_clock_seconds=clock['last'],
                      last_costmap_receipt_age_wall_seconds=time.monotonic()-received['live_costmap']
                          if received['live_costmap'] is not None else None,
                      note='Shows free static-map cells and lethal live-costmap cells at the crate location. Does not establish obstacle identity, successful navigation, minimum clearance, or collision freedom.')
        node.destroy_node()
        rclpy.shutdown()
    return report, report['passed'] and not report['interrupted']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--spawn', action='store_true', help='Create the fixed crate in Gazebo world default')
    mode.add_argument('--observe', action='store_true', help='Read ROS maps/clock only; make no simulation changes')
    parser.add_argument('--duration', type=float, default=90.0, help='Maximum observation wall seconds')
    parser.add_argument('--output', help='JSON path; defaults to evidence/unmapped-spawn.json or unmapped-observation.json')
    args = parser.parse_args()
    partition = os.environ.get('GZ_PARTITION', '')
    if not partition.strip():
        parser.error('Set an explicit nonempty GZ_PARTITION matching the intended simulator')
    if not math.isfinite(args.duration) or args.duration < 1:
        parser.error('--duration must be finite and at least 1 second')
    report, passed = spawn(partition) if args.spawn else observe(partition, args.duration)
    output = Path(args.output or ('evidence/unmapped-spawn.json' if args.spawn else 'evidence/unmapped-observation.json'))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
