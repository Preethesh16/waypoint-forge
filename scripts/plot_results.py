#!/usr/bin/env python3
"""Plot recorded evidence only; never interpolate missing runs into successes."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--benchmark', default='evidence/v1.1/benchmark')
    parser.add_argument('--map', default='/opt/ros/jazzy/share/turtlebot3_navigation2/map/map.yaml')
    parser.add_argument('--output', default='evidence/v1.1/benchmark-summary.png')
    args = parser.parse_args()
    root = Path(args.benchmark)
    report = json.loads((root / 'summary.json').read_text())
    if not report.get('finished_utc') or report.get('interrupted'):
        raise SystemExit('Benchmark must finish before generating the final figure')
    if report.get('source_unchanged') is not True:
        raise SystemExit('Benchmark must confirm unchanged source hashes before plotting a fixed configuration')
    map_yaml = Path(args.map)
    metadata = yaml.safe_load(map_yaml.read_text())
    if abs(metadata['origin'][2]) > 1e-9:
        raise SystemExit('This plot requires an axis-aligned occupancy map')
    pixels = np.asarray(Image.open(map_yaml.parent / metadata['image']))
    x, y, _ = metadata['origin']
    resolution = metadata['resolution']
    extent = (x, x + pixels.shape[1] * resolution, y, y + pixels.shape[0] * resolution)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig = plt.figure(figsize=(13, 7.5), layout='constrained')
    grid = fig.add_gridspec(2, 2, width_ratios=[1.15, 1])
    path_ax = fig.add_subplot(grid[:, 0])
    time_ax = fig.add_subplot(grid[0, 1])
    error_ax = fig.add_subplot(grid[1, 1])
    path_ax.imshow(pixels, cmap='gray', vmin=0, vmax=255, extent=extent, origin='upper')
    labels, durations, errors, colors = [], [], [], []
    seen = set()
    for row in report['runs']:
        standard = row['scenario'] == 'standard'
        color = '#1768ac' if standard else '#d36b14'
        label = f"S{row['trial']}" if standard else 'Alternative'
        labels.append(label + ('' if row.get('passed') else ' FAIL'))
        durations.append(row.get('goal_wall_seconds', np.nan))
        error = row.get('worst_estimated_goal_error_m')
        errors.append(100 * error if error is not None else np.nan)
        colors.append(color if row.get('passed') else '#b42b35')
        mission_path = root / f"{row['scenario']}-{row['trial']:02d}" / 'mission.json'
        if not mission_path.exists():
            continue
        mission = json.loads(mission_path.read_text())
        category = 'Standard-route estimates' if standard else 'Alternative-route estimates'
        for goal in mission.get('goals', []):
            points = np.asarray([p['xy'] for p in goal.get('trajectory', [])])
            if len(points):
                path_ax.plot(points[:, 0], points[:, 1], color=color, alpha=0.6,
                             lw=1.5, label=category if category not in seen else None)
                seen.add(category)
            target = goal['goal']
            path_ax.scatter(target[0], target[1], marker='x', s=48, color=color, zorder=4)
    path_ax.scatter(-2, -.5, marker='o', s=40, color='#17212b', label='Spawn')
    path_ax.set(xlim=(-3.3, 3.3), ylim=(-3.3, 3.3), xlabel='Map x (m)', ylabel='Map y (m)',
                title='Observed map-frame trajectories')
    path_ax.set_aspect('equal')
    path_ax.legend(loc='lower left', fontsize=8, framealpha=.95)
    for ax, values, title, unit in ((time_ax, durations, 'Navigation time per trial', 'Summed goal wall time (s)'),
                                  (error_ax, errors, 'Worst goal position estimate per trial', 'Estimated error (cm)')):
        ax.bar(labels, values, color=colors, width=.6)
        ax.set(title=title, ylabel=unit)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        for index, value in enumerate(values):
            if np.isfinite(value):
                ax.annotate(f'{value:.1f}', (index, value), xytext=(0, 4),
                            textcoords='offset points', ha='center', fontsize=9)
        ax.margins(y=.2)
    error_ax.axhline(15, ls='--', color='#555', lw=1, label='Configured goal tolerance: 15 cm')
    error_ax.legend(fontsize=8, loc='upper right')
    passed = sum(bool(r.get('passed')) for r in report['runs'])
    fig.suptitle(f'Waypoint Forge | {passed}/{len(report["runs"])} observed trials passed',
                 fontsize=18, fontweight='bold')
    fig.supxlabel('One host, fixed map/configuration. Pose estimates are not ground truth. '
                  'Alternative route has three goals; standard route has two.', fontsize=9)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    fig.savefig(output.with_suffix('.pdf'))
    plt.close(fig)
    print(output)


if __name__ == '__main__':
    main()
