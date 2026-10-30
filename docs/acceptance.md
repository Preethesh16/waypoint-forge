# Acceptance checklist

The assignment and email were inspected on 30 October 2026. No ROS distribution
was specified, so this project uses ROS 2 Jazzy on Ubuntu 24.04 with the matching
TurtleBot3 packages and Gazebo vendor dependencies. The host is Arch Linux;
runtime isolation is provided by Docker. No physical hardware is involved.

| Requirement | Implementation | Acceptance check | Evidence/status |
|---|---|---|---|
| TurtleBot3 in Gazebo | Official Burger model and TurtleBot3 world | Robot spawns, physics/clock/sensors advance | Passed: live Gazebo + doctor evidence |
| Autonomous goal navigation | Nav2 + AMCL + checked-in parameters | Both NavigateToPose actions succeed | Passed: evidence/mission.json, both goals succeeded |
| Obstacle avoidance | Laser-driven costmaps, NavFn, DWB | Observe trajectory around cylinder field in Gazebo/RViz | Passed: actual recorded trajectory around obstacles |
| 1–2 minute screen recording | Dedicated simulation desktop | 60–120 second video visibly shows Gazebo and RViz | Passed: 75 s, 1600×900, 20 fps |
| Relevant public GitHub repository | Launch, mission, configuration, README, attribution | Clean repository; public URL works | Pending final user publication approval |
| Brief setup instructions | Native Jazzy and Docker instructions | Run documented commands against actual environment | Runtime commands passed; clean Dockerfile build not performed |
| Submission answers | User-confirmed ROS 2 experience and factual challenge account | Correct links and truthful answers | Prior experience: Yes; factual draft ready, public links await approval |
| AI assistance allowed | Attribution and disclosure | Explicit disclosure, no fabricated outcomes | Included in THIRD_PARTY.md |

## Supporting quality checks

- [x] Inspect actual brief, deadline and form questions.
- [x] Inspect host capabilities and available storage.
- [x] Python/shell syntax and YAML configuration consistency checks.
- [x] Complete dependency installation and capture package versions.
- [x] Verify simulation clock, topic types/QoS, sensor validity and TF chain.
- [x] Verify nominal mission and bounded failure/interruption behavior.
- [x] Inspect actual Gazebo and RViz visualization.
- [x] Independently test final integrated implementation.
- [x] Resolve substantive independent review findings.
- [x] Record and inspect the final demo, save measured evidence.
- [x] Update README with actual results and known limitations.
- [x] Prepare finished artifacts and publication/submission preview for approval.

## Selected differentiators

1. Repeatable action-based mission with measured results and explicit failure
   status: makes review and debugging easier without replacing Nav2.
2. Bounded runtime diagnostics for clock/sensors/transforms/readiness: useful for
   reproducing the integration. It is a diagnostic aid, not a safety guarantee.

Optional functionality must not delay or weaken the required navigation demo.
