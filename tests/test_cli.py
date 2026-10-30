"""Exercise the real CLI before it initializes ROS; run with ROS sourced."""
import subprocess
import sys
import unittest
from pathlib import Path

MISSION = Path(__file__).resolve().parents[1] / 'scripts' / 'mission.py'


class MissionCLI(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, str(MISSION), *args],
                              capture_output=True, text=True, timeout=10)

    def test_help_does_not_need_simulator(self):
        result = self.invoke('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--goals', result.stdout)

    def test_invalid_goals_fail_before_ros_startup(self):
        for value in ['[]', '[[1,2]]', '[[1,2,"bad"]]', '[[1,2,NaN]]',
                      'null', '3', '[3]', '{"x":1}', '[[true,2,3]]', 'not-json']:
            with self.subTest(value=value):
                result = self.invoke('--goals', value)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_invalid_timeout_fail_before_ros_startup(self):
        for value in ['0', '-1', 'nan', 'inf']:
            with self.subTest(value=value):
                result = self.invoke('--timeout', value)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
