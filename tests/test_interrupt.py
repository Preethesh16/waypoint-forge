"""Real ROS client startup interruption on an isolated domain, no mock nodes."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

MISSION = Path(__file__).resolve().parents[1] / 'scripts' / 'mission.py'


class MissingStackInterruption(unittest.TestCase):
    def test_interrupt_while_waiting_for_absent_amcl(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            report = directory / 'report.json'
            log = directory / 'mission.log'
            env = dict(os.environ, ROS_DOMAIN_ID='97', PYTHONUNBUFFERED='1')
            with log.open('w') as stream:
                process = subprocess.Popen(
                    [sys.executable, str(MISSION), '--output', str(report)],
                    stdout=stream, stderr=subprocess.STDOUT, env=env)
                try:
                    deadline = time.monotonic() + 12
                    while time.monotonic() < deadline:
                        content = log.read_text()
                        if 'get_state' in content and 'not available' in content:
                            break
                        if process.poll() is not None:
                            self.fail('Client exited before readiness wait:\n' + content)
                        time.sleep(0.1)
                    else:
                        self.fail('Client never reached absent-service wait:\n' + log.read_text())
                    process.send_signal(signal.SIGINT)
                    process.wait(timeout=8)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            self.assertEqual(process.returncode, 1, log.read_text())
            self.assertNotIn('Traceback', log.read_text())
            result = json.loads(report.read_text())
            self.assertFalse(result['all_succeeded'])
            self.assertTrue(result['interrupted'])
            self.assertEqual(result['goals'], [])
            self.assertFalse(result['cancellation']['requested'])


if __name__ == '__main__':
    unittest.main()
