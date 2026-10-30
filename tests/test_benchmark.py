"""Guard against misleading benchmark aggregation and incomplete-result success."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'benchmark.py'
spec = importlib.util.spec_from_file_location('benchmark', PATH)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class BenchmarkEvidence(unittest.TestCase):
    def test_incomplete_or_failed_runs_cannot_count_as_success(self):
        good = {'all_succeeded': True, 'goals': [{'succeeded': True, 'timed_out': False}]}
        self.assertTrue(benchmark.mission_passed(good, 0, 1))
        self.assertFalse(benchmark.mission_passed(good, 1, 1))
        self.assertFalse(benchmark.mission_passed(good, 0, 2))
        self.assertFalse(benchmark.mission_passed({}, 0, 1))
        self.assertFalse(benchmark.mission_passed({'all_succeeded': True, 'goals': [None]}, 0, 1))
        timed_out = {'all_succeeded': True, 'goals': [{'succeeded': True, 'timed_out': True}]}
        self.assertFalse(benchmark.mission_passed(timed_out, 0, 1))

    def test_failed_attempt_is_in_success_denominator_not_timing_sample(self):
        rows = [{'scenario': 'standard', 'passed': True, 'mission_wall_seconds': 20,
                 'goal_wall_seconds': 18, 'distance_m': 3, 'worst_estimated_goal_error_m': .1},
                {'scenario': 'standard', 'passed': False, 'mission_wall_seconds': 400},
                {'scenario': 'challenge', 'passed': True, 'mission_wall_seconds': 30,
                 'goal_wall_seconds': 27, 'distance_m': 4, 'worst_estimated_goal_error_m': .05}]
        result = benchmark.summarize(rows)
        self.assertEqual(result['standard']['attempted'], 2)
        self.assertEqual(result['standard']['passed'], 1)
        self.assertEqual(result['standard']['observed_success_fraction'], .5)
        self.assertEqual(result['standard']['complete_successful_run_wall_seconds']['count'], 1)
        self.assertEqual(result['standard']['complete_successful_run_wall_seconds']['max'], 20)
        self.assertEqual(result['challenge']['attempted'], 1)

    def test_no_numeric_measurements_are_not_reported_as_zero(self):
        self.assertIsNone(benchmark.describe([None, float('nan'), float('inf')]))
        self.assertEqual(benchmark.summarize([]), {})


if __name__ == '__main__':
    unittest.main()
