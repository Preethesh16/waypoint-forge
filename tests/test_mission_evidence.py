"""Evidence integrity and real isolated-ROS status/skip-localization regression checks."""
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from geometry_msgs.msg import PoseStamped

MISSION = Path(__file__).resolve().parents[1] / 'scripts' / 'mission.py'
spec = importlib.util.spec_from_file_location('mission_evidence', MISSION)
mission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mission)


class PoseEvidence(unittest.TestCase):
    def sample(self, stamp, received, source='amcl'):
        return {'source': source, 'frame': 'map', 'xy': [1.0, 2.0],
                'stamp_sim_seconds': stamp, 'received_wall': received}

    def test_fresh_feedback_supersedes_old_amcl(self):
        result = mission.freshest_pose([self.sample(8, 19), self.sample(10, 19.8, 'nav2_feedback')], 10.1, 20)
        self.assertEqual(result['source'], 'nav2_feedback')
        self.assertTrue(result['fresh'])
        self.assertAlmostEqual(result['age_sim_seconds'], 0.1)
        self.assertNotIn('received_wall', result)

    def test_receipt_alone_does_not_make_old_sim_pose_fresh(self):
        result = mission.assess_pose(self.sample(1, 20), 10, 20)
        self.assertFalse(result['fresh'])
        self.assertEqual(result['age_sim_seconds'], 9)

    def test_future_and_old_wall_samples_are_stale(self):
        for sample in [self.sample(11, 20), self.sample(10, 15)]:
            self.assertFalse(mission.assess_pose(sample, 10, 20)['fresh'])

    def test_snapshot_before_receipt_cannot_claim_fresh_pose(self):
        sample = self.sample(10, 20.00005)
        self.assertFalse(mission.assess_pose(sample, 10, 20)['fresh'])
        after_receipt = mission.assess_pose(sample, 10, 20.0001)
        self.assertTrue(after_receipt['fresh'])
        self.assertGreaterEqual(after_receipt['age_wall_seconds'], 0)

    def test_invalid_or_different_frame_pose_is_rejected(self):
        msg = PoseStamped()
        msg.header.frame_id = 'odom'
        self.assertIsNone(mission.pose_sample(msg, 'test', 0))
        msg.header.frame_id = 'map'
        msg.pose.position.x = math.nan
        self.assertIsNone(mission.pose_sample(msg, 'test', 0))

    def test_overlay_never_presents_stale_remaining_distance(self):
        status = {'phase': 'navigating', 'goal_index': 1, 'goal_count': 2,
                  'goal': [1., 2., 0.], 'wall_seconds': 2., 'sim_seconds': 1.,
                  'feedback': {'fresh': False, 'distance_remaining_m': 3.14}}
        text = mission.status_text(status)
        self.assertEqual(len(text.splitlines()), 2)
        self.assertNotIn('3.14', text)
        self.assertIn('Waiting for fresh feedback', text)


class LiveStatus(unittest.TestCase):
    def test_status_created_before_readiness_and_interrupt_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = dict(os.environ, ROS_DOMAIN_ID='96', PYTHONUNBUFFERED='1')
            args = [sys.executable, str(MISSION), '--skip-initial-pose', '--initialize-only',
                    '--output', str(root/'report.json'), '--status-json', str(root/'status.json'),
                    '--status-text', str(root/'status.txt')]
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, env=env)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if (root/'status.json').exists():
                        data = json.loads((root/'status.json').read_text())
                        if data['wall_seconds'] > 0.5:
                            break
                    if process.poll() is not None:
                        self.fail('Mission exited before readiness observation')
                    time.sleep(0.05)
                else:
                    self.fail('Live status was not produced while waiting for absent AMCL')
                self.assertEqual(data['phase'], 'waiting_for_localization')
                self.assertEqual(len((root/'status.txt').read_text().splitlines()), 2)
                process.send_signal(signal.SIGINT)
                out, err = process.communicate(timeout=8)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            self.assertEqual(process.returncode, 1, out + err)
            self.assertNotIn('Traceback', out + err)
            report = json.loads((root/'report.json').read_text())
            self.assertTrue(report['interrupted'])
            self.assertFalse(report['initial_pose_published'])
            self.assertFalse(report['initialization_succeeded'])
            self.assertFalse(report['all_succeeded'])
            self.assertEqual(report['goals'], [])
            self.assertEqual(json.loads((root/'status.json').read_text())['phase'], 'interrupted')
            self.assertFalse(list(root.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main()
