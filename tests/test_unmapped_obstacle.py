"""Real OccupancyGrid extraction and simulation helper input contracts; no navigation mocks."""
import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

from nav_msgs.msg import OccupancyGrid

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts' / 'unmapped_obstacle.py'
spec = importlib.util.spec_from_file_location('unmapped_obstacle', HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def grid(yaw=0.0):
    message = OccupancyGrid()
    message.header.frame_id = 'map'
    message.header.stamp.sec = 10
    message.info.width = message.info.height = 80
    message.info.resolution = 0.05
    message.info.origin.position.x = -2.0 if yaw == 0 else 2.0
    message.info.origin.position.y = -2.0
    message.info.origin.orientation.z = math.sin(yaw / 2)
    message.info.origin.orientation.w = math.cos(yaw / 2)
    message.data = [0] * 6400
    return message


class RegionExtraction(unittest.TestCase):
    def test_complete_free_region_preserves_cells_and_coordinates(self):
        result = helper.patch(grid())
        self.assertTrue(result['probe_region_fully_covered'])
        self.assertEqual(result['cell_count'], 144)
        self.assertEqual(result['free_cells'], 144)
        self.assertEqual(result['unknown_cells'], 0)
        self.assertEqual(result['lethal_cells'], 0)
        self.assertEqual(result['stamp_sim_seconds'], 10.0)
        for cell in result['cells']:
            self.assertLessEqual(abs(cell['world_xy'][0]), 0.3)
            self.assertLessEqual(abs(cell['world_xy'][1] - 1.65), 0.3)

    def test_unknown_and_inflated_cells_are_not_lethal_or_free(self):
        message = grid()
        x, y = helper.patch(message)['cells'][0]['grid_xy']
        for value, free, lethal, unknown in [(100, 143, 1, 0), (99, 143, 0, 0), (-1, 143, 0, 1)]:
            with self.subTest(value=value):
                message.data[y * message.info.width + x] = value
                result = helper.patch(message)
                self.assertEqual(result['free_cells'], free)
                self.assertEqual(result['lethal_cells'], lethal)
                self.assertEqual(result['unknown_cells'], unknown)

    def test_rotated_origin_still_selects_same_world_region(self):
        result = helper.patch(grid(math.pi / 2))
        self.assertTrue(result['probe_region_fully_covered'])
        self.assertEqual(result['free_cells'], 144)
        self.assertEqual(result['cell_count'], 144)

    def test_clipped_region_is_not_treated_as_complete(self):
        message = grid()
        message.info.origin.position.y = 10.0
        result = helper.patch(message)
        self.assertFalse(result['probe_region_fully_covered'])
        self.assertEqual(result['cell_count'], 0)

    def test_invalid_grid_contracts_are_rejected(self):
        mutations = [lambda m: setattr(m.header, 'frame_id', 'odom'),
                     lambda m: setattr(m.info, 'resolution', 0.0),
                     lambda m: setattr(m, 'data', [0]),
                     lambda m: setattr(m.info.origin.orientation, 'w', 0.0),
                     lambda m: setattr(m.info.origin.position, 'x', math.nan)]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                message = grid()
                mutate(message)
                with self.assertRaises(ValueError):
                    helper.patch(message)


class HelperContracts(unittest.TestCase):
    def test_missing_partition_rejected_before_spawn(self):
        env = dict(os.environ)
        env.pop('GZ_PARTITION', None)
        result = subprocess.run([sys.executable, str(HELPER), '--spawn'], env=env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('explicit nonempty GZ_PARTITION', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_blank_partition_rejected_before_observer_initialization(self):
        env = dict(os.environ, GZ_PARTITION='   ', ROS_DOMAIN_ID='95')
        result = subprocess.run([sys.executable, str(HELPER), '--observe'], env=env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('explicit nonempty GZ_PARTITION', result.stderr)

    def test_sdf_is_fixed_static_crate_with_matching_collision_and_visual(self):
        tree = ET.parse(ROOT / 'config' / 'unmapped_crate.sdf')
        model = tree.find('./model')
        self.assertEqual(model.attrib['name'], helper.CRATE_NAME)
        self.assertEqual(model.findtext('static').strip(), 'true')
        self.assertEqual([float(v) for v in model.findtext('pose').split()], [0., 1.65, .3, 0., 0., 0.])
        for kind in ('collision', 'visual'):
            size = model.findtext(f'link/{kind}/geometry/box/size')
            self.assertEqual([float(v) for v in size.split()], [.5, .5, .6])
        self.assertEqual(tree.findall('.//plugin'), [])


if __name__ == '__main__':
    unittest.main()
