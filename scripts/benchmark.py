#!/usr/bin/env python3
"""Bounded repeated real Gazebo/Nav2 runs; no mocks and no result substitution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import time

STANDARD_GOALS = [[1.5, 1.5, math.pi], [-1.5, 1.5, -math.pi / 2]]
CHALLENGE_GOALS = [[0.5, 0.5, 0.0], [1.5, -1.5, -math.pi / 2], [-1.5, -1.5, math.pi]]
ROOT = Path(__file__).resolve().parents[1]


def process_table():
    """Linux process identity, parent and group, excluding unreadable exits."""
    rows = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            tail = path.read_text().rsplit(')', 1)[1].split()
            rows[int(path.parent.name)] = {'state': tail[0], 'ppid': int(tail[1]), 'pgid': int(tail[2])}
        except (OSError, ValueError, IndexError):
            pass
    return rows


def owned_groups(pid):
    rows = process_table()
    descendants = {pid}
    while True:
        found = {p for p, row in rows.items() if row['ppid'] in descendants}
        if found <= descendants:
            break
        descendants |= found
    # Every subprocess starts a new session; never target our orchestration group.
    return {rows[p]['pgid'] for p in descendants if p in rows} - {os.getpgrp()}


def stop_owned(process):
    if process is None:
        return {'live_owned_pids': [], 'escalated': False}
    started = time.monotonic()
    groups = owned_groups(process.pid)
    escalated = False
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            escalated = True
    live = lambda: [p for p, row in process_table().items()
                    if row['pgid'] in groups and row['state'] != 'Z']
    if live():
        escalated = True
        for sig, delay in [(signal.SIGTERM, 1.0), (signal.SIGKILL, 0.2)]:
            for group in groups:
                try:
                    os.killpg(group, sig)
                except ProcessLookupError:
                    pass
            time.sleep(delay)
            if not live():
                break
    if process.poll() is None:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    return {'wrapper_exit_code': process.returncode, 'live_owned_pids': live(),
            'escalated': escalated, 'wall_seconds': round(time.monotonic() - started, 3)}


def read_report(path):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def mission_passed(report, exit_code, expected_goals):
    goals = report.get('goals', [])
    return (exit_code == 0 and report.get('all_succeeded') is True
            and len(goals) == expected_goals
            and all(isinstance(g, dict) and g.get('succeeded') is True and not g.get('timed_out') for g in goals))


def describe(values):
    values = [v for v in values if isinstance(v, (float, int)) and math.isfinite(v)]
    return ({'count': len(values), 'min': min(values), 'median': statistics.median(values),
             'mean': statistics.mean(values), 'max': max(values)} if values else None)


def summarize(rows):
    summary = {}
    for scenario in sorted({r['scenario'] for r in rows}):
        subset = [r for r in rows if r['scenario'] == scenario]
        successful = [r for r in subset if r.get('passed')]
        summary[scenario] = {
            'attempted': len(subset), 'passed': len(successful),
            'observed_success_fraction': len(successful) / len(subset),
            'complete_successful_run_wall_seconds': describe([r.get('mission_wall_seconds') for r in successful]),
            'summed_goal_wall_seconds': describe([r.get('goal_wall_seconds') for r in successful]),
            'odometry_distance_m': describe([r.get('distance_m') for r in successful]),
            'worst_estimated_goal_error_m': describe([r.get('worst_estimated_goal_error_m') for r in successful]),
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, default=5, help='Standard-route repeats, 1–10')
    parser.add_argument('--include-challenge', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--domain-id', type=int, default=83)
    parser.add_argument('--output', default='evidence/v1.1/benchmark')
    parser.add_argument('--goal-timeout', type=float, default=120)
    parser.add_argument('--mission-timeout', type=float, default=400,
                        help='Wall limit including localization; mission.sh also limits at 420 s')
    parser.add_argument('--startup-timeout', type=float, default=45)
    parser.add_argument('--launch-arg', action='append', default=None,
                        help='Repeatable launch argument; default gui:=false')
    args = parser.parse_args()
    if not 1 <= args.runs <= 10 or not 0 <= args.domain_id <= 232:
        parser.error('--runs must be 1–10 and --domain-id must be 0–232')
    for name in ('goal_timeout', 'mission_timeout', 'startup_timeout'):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error('Timeouts must be positive finite numbers')
    output = Path(args.output).resolve()
    if output.exists():
        parser.error('Output directory already exists; choose a new path to preserve evidence')

    # Import only after argument validation so --help works outside ROS.
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    from rosgraph_msgs.msg import Clock
    rclpy.init(domain_id=args.domain_id, signal_handler_options=SignalHandlerOptions.NO)
    node = Node('independent_benchmark_probe')
    clock = {}

    def receive(msg):
        stamp = msg.clock.sec + msg.clock.nanosec / 1e9
        if clock.get('first') is None:
            clock['first'] = stamp
        clock['last'] = stamp
        clock['samples'] = clock.get('samples', 0) + 1

    node.create_subscription(Clock, '/clock', receive, qos_profile_sensor_data)

    def spin_for(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=min(0.1, max(0, end - time.monotonic())))

    output.mkdir(parents=True)
    plan = [('standard', i + 1, STANDARD_GOALS) for i in range(args.runs)]
    if args.include_challenge:
        plan.append(('interior-and-lower-stations', 1, CHALLENGE_GOALS))
    tracked_files = ['scripts/mission.py', 'scripts/run.sh', 'scripts/doctor.py',
                     'scripts/benchmark.py', 'launch/demo.launch.py', 'config/nav2.yaml']
    report = {
        'started_utc': datetime.now(timezone.utc).isoformat(), 'domain_id': args.domain_id,
        'planned_runs': len(plan), 'host_platform': platform.platform(), 'python': platform.python_version(),
        'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in tracked_files},
        'arguments': vars(args), 'runs': [], 'interrupted': False,
        'scope': 'Repeated simulation observations on one host/map/configuration. Not a reliability probability or hardware claim. Pose errors are estimates, not ground truth.',
    }

    def save():
        report['summary'] = summarize(report['runs'])
        report['all_planned_passed'] = (len(report['runs']) == len(plan)
                                       and all(r.get('passed') for r in report['runs'])
                                       and not report['interrupted'] and report.get('source_unchanged', True))
        (output / 'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')

    current_sim = current_mission = None
    try:
        for scenario, index, goals in plan:
            spin_for(2)
            if node.get_publishers_info_by_topic('/clock'):
                raise RuntimeError('Existing clock publisher on benchmark domain; refusing to mix simulations')
            clock.clear()
            directory = output / f'{scenario}-{index:02d}'
            directory.mkdir()
            row = {'scenario': scenario, 'trial': index, 'requested_goals': goals, 'passed': False}
            report['runs'].append(row)
            env = dict(os.environ, ROS_DOMAIN_ID=str(args.domain_id),
                       GZ_PARTITION=f'antropi_benchmark_{os.getpid()}_{scenario}_{index}',
                       PYTHONUNBUFFERED='1')
            sim_log = (directory / 'simulation.txt').open('w')
            mission_log = (directory / 'mission.txt').open('w')
            try:
                current_sim = subprocess.Popen(['bash', str(ROOT / 'scripts/run.sh'),
                                                *(args.launch_arg or ['gui:=false'])],
                                               cwd=ROOT, env=env, stdout=sim_log, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                deadline = time.monotonic() + args.startup_timeout
                while time.monotonic() < deadline:
                    spin_for(0.1)
                    pubs = node.get_publishers_info_by_topic('/clock')
                    if (clock.get('samples', 0) >= 2 and clock['last'] > clock['first'] and len(pubs) == 1):
                        break
                    if current_sim.poll() is not None:
                        raise RuntimeError('Simulation launcher exited during startup')
                row['clock_probe'] = dict(clock, publisher_count=len(node.get_publishers_info_by_topic('/clock')))
                row['clock_fresh'] = (clock.get('samples', 0) >= 2 and 0 <= clock.get('first', math.inf) < 15
                                      and clock['last'] > clock['first'] and row['clock_probe']['publisher_count'] == 1)
                if not row['clock_fresh']:
                    raise RuntimeError('No unique advancing fresh simulation clock before startup deadline')
                started = time.monotonic()
                current_mission = subprocess.Popen(
                    ['bash', str(ROOT / 'scripts/mission.sh'), '--goals', json.dumps(goals),
                     '--timeout', str(args.goal_timeout), '--output', str(directory / 'mission.json')],
                    cwd=ROOT, env=env, stdout=mission_log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    row['mission_exit_code'] = current_mission.wait(timeout=args.mission_timeout)
                except subprocess.TimeoutExpired:
                    row['orchestration_timeout'] = True
                    row['mission_cleanup'] = stop_owned(current_mission)
                    row['mission_exit_code'] = current_mission.returncode
                row['mission_wall_seconds'] = round(time.monotonic() - started, 3)
                current_mission = None
                mission = read_report(directory / 'mission.json')
                row['mission_succeeded'] = mission_passed(mission, row['mission_exit_code'], len(goals))
                goal_results = mission.get('goals', [])
                row['goal_wall_seconds'] = round(sum(g.get('wall_seconds', 0) for g in goal_results), 3)
                row['distance_m'] = round(sum(g.get('distance_m', 0) for g in goal_results), 3)
                errors = [g.get('estimated_goal_error_m') for g in goal_results]
                row['worst_estimated_goal_error_m'] = max(errors) if errors and all(isinstance(v, (int, float)) for v in errors) else None
                with (directory / 'doctor.txt').open('w') as doctor_log:
                    try:
                        result = subprocess.run(
                            ['python3', str(ROOT / 'scripts/doctor.py'), '--duration', '3',
                             '--output', str(directory / 'doctor.json')],
                            cwd=ROOT, env=env, stdout=doctor_log, stderr=subprocess.STDOUT, timeout=15)
                        row['doctor_exit_code'] = result.returncode
                    except subprocess.TimeoutExpired:
                        row['doctor_exit_code'] = None
                row['doctor_passed'] = row['doctor_exit_code'] == 0 and read_report(directory / 'doctor.json').get('passed') is True
                row['passed'] = row['mission_succeeded'] and row['doctor_passed'] and not row.get('orchestration_timeout')
            except Exception as error:
                row['error'] = f'{type(error).__name__}: {error}'
            finally:
                if current_mission is not None:
                    row['mission_cleanup'] = stop_owned(current_mission)
                    current_mission = None
                row['simulation_cleanup'] = stop_owned(current_sim)
                current_sim = None
                if row['simulation_cleanup']['live_owned_pids']:
                    row['passed'] = False
                sim_log.close()
                mission_log.close()
                save()
            print(json.dumps(row), flush=True)
            if row['simulation_cleanup']['live_owned_pids']:
                raise RuntimeError('Owned simulation processes survived cleanup; stopping suite')
    except KeyboardInterrupt:
        report['interrupted'] = True
    except Exception as error:
        report['suite_error'] = f'{type(error).__name__}: {error}'
    finally:
        if current_mission is not None:
            stop_owned(current_mission)
        if current_sim is not None:
            stop_owned(current_sim)
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        report['final_source_sha256'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in tracked_files}
        report['source_unchanged'] = report['source_sha256'] == report['final_source_sha256']
        save()
        node.destroy_node()
        rclpy.shutdown()
    print(json.dumps(report['summary'], indent=2), flush=True)
    return 0 if report['all_planned_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
