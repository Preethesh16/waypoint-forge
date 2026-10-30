# Acceptance checklist

The actual assignment/email were inspected on 30 October 2026. No ROS distribution
was specified, so the project uses ROS 2 Jazzy on Ubuntu 24.04, matching TurtleBot3
packages and Gazebo Sim 8. The host is Arch Linux; Docker supplies Ubuntu runtime
isolation. No physical hardware has been operated.

## Required assignment deliverables

| Requirement | Implementation | Observable acceptance | Evidence/status |
| --- | --- | --- | --- |
| TurtleBot3 in Gazebo | Official Burger model and obstacle world | Robot spawns; physics, clock and sensors advance | Passed: live diagnostics and actual recording |
| Autonomous navigation | AMCL, Nav2, configured costmaps/planner/controller | Real NavigateToPose actions succeed | Passed: v1.0 recorded mission and v1.1 13/13 benchmark goals |
| Obstacle avoidance | Laser-driven costmaps, NavFn and DWB | Robot follows paths around obstacles in Gazebo/RViz | Passed in existing recording; no formal collision-free claim |
| 1–2 minute recording | Dedicated simulation desktop | 60–120 s recording visibly shows both applications | Passed: enhanced v1.1 video 90 s, 1600×900, 20 fps; full decode and stills inspected |
| Public GitHub repository | Source, configuration, documentation and attribution | Public URL works | Verified public: https://github.com/Preethesh16/waypoint-forge; release assets are linked from the README |
| Brief setup instructions | Exact native Jazzy/Docker/runtime commands | Exercise documented runtime | Passed: final uncached Docker build, 22 tests, two real goals and 15 diagnostics at ecaf83a |
| Submission form answers | Confirmed experience and factual account of debugging | Correct links and truthful answers | Prior ROS 2 experience:Yes; submission receipt tracked separately |
| Permitted assistance | Attribution and disclosure | AI use disclosed; upstream work credited | Included in THIRD_PARTY.md |

## v1.1 supporting checks

- [x] Preserve existing v1.0 evidence instead of replacing its historical results.
- [x] Run five actual fresh-start standard missions and one alternative route.
- [x] Verify all six clocks start fresh with one publisher, all post-mission
  diagnostics pass, and no live owned simulator processes survive cleanup.
- [x] Record **6/6 trial successes and 13/13 goal successes**, with unchanged core
  source hashes and raw per-trial evidence.
- [x] Verify fresh feedback/AMCL pose selection and populated bounded trajectories.
- [x] Run **22/22 independent regression tests** successfully (8.085 s).
- [x] Check plot calculations, units, map orientation, and estimate/sample-size caveats.
- [x] Reject mixed-source benchmark reports when plotting a fixed configuration.
- [x] Verify enhanced video duration, complete decode and selected actual frames.
- [x] Verify optional unmapped-crate experiment: 144 static-map cells free, 12
  live-costmap cells lethal, all freshness checks passing, two mission goals successful.

The final executable-source clean build passed [Actions run 41104171580](https://github.com/Preethesh16/waypoint-forge/actions/runs/41104171580).
See [reproducibility](reproducibility.md) for the tested commit and archived artifacts.

Detailed results: [independent verification](verification.md),
[benchmark protocol/results](benchmark.md), and
[evidence/v1.1/regression-tests.txt](../evidence/v1.1/regression-tests.txt).

## Practical differentiators and boundaries

1. Repeatable action missions with fresh measured evidence, live status and a
   small repeated-run benchmark make the behavior easier to explain and reproduce.
2. Bounded runtime diagnostics and an optional unmapped-obstacle observation make
   integration faults and sensor-driven costmap changes easier to inspect.

These features expose existing Nav2 behavior; they do not replace its algorithms
or constitute a safety system. Five repeat successes on one host/map/configuration
are not a reliability probability. Hardware, changing layouts, moving obstacles
and independent collision/contact validation remain outside the verified scope.
