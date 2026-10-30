# Clean-build and simulation reproducibility

The local successful run used a blank Ubuntu 24.04 container with the project
dependencies installed into it. That establishes working integration, but is
different from successfully building the final Dockerfile on a clean machine.
The `Clean build and real Nav2 simulation` workflow closes that gap only when its
actual run is green. A checked-in workflow alone is not evidence of a passing run.

## Verified initial clean run

[Actions run 41102204300](https://github.com/Preethesh16/waypoint-forge/actions/runs/41102204300)
completed successfully for commit `c05b6d5e275b4d31411873ffae578e9d44e8c495`.
The downloaded artifacts confirm an uncached Docker build, four real CLI tests,
two successful autonomous goals (31.456 s and 19.585 s wall time), and all 15 live
diagnostic checks passing. Selected durable evidence and original artifact-file
SHA256 hashes are archived in `evidence/v1.1/ci-initial/`.

This initial CI run predates the final v1.1 mission evidence, benchmark and dynamic
obstacle additions. It validates the pinned environment and original mission;
**exact-final-source CI remains pending** until a later run verifies that commit.
The artifact’s full build/runtime logs remain linked from the run while retained.

## What is pinned

- The Ubuntu base uses the official registry manifest digest for `24.04`,
  verified against the manifest bytes on 30 October 2026:
  `sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852`.
  This is registry-verified, not a claim that the local run used that exact image.
  The clean CI run must validate the pinned combination.
- Five explicitly installed ROS packages are pinned to the exact versions in
  `evidence/package-versions.tsv`: TurtleBot3 Gazebo/navigation, Nav2 Simple
  Commander, RViz and ros2launch.
- The ROS repository signing-key download uses a particular rosdistro commit.
- Checkout and artifact-upload Actions use verified commit SHAs.

This is **not a hermetic build**. Ubuntu packages and transitive ROS dependencies
still come from live signed package repositories. Repository retention can remove
an exact version; that should produce a visible build failure rather than silently
installing an unreviewed replacement. A deliberate dependency update needs a new
clean-build and simulation run. The CI artifact records every installed package
version, the resulting image inspection and the source commit.

## Actual clean CI procedure

The workflow runs on a fresh standard `ubuntu-24.04` GitHub-hosted runner. These
standard runners are free for this public repository; it does not select a paid
larger runner or publish a container image. It uses read-only repository permission
and no project credentials or deployment secrets.

1. Check out the exact source commit with persisted credentials disabled.
2. Build the checked-in Dockerfile using `docker build --pull --no-cache`.
3. Start a new container with a private Xvfb display and software rendering.
   Gazebo's GPU lidar still needs a rendering context even with GUI clients off.
4. Run the actual CLI and absent-stack interruption tests against installed ROS.
5. Launch Gazebo, TurtleBot3, bridges and Nav2 using `gui:=false`.
6. Execute the same two `NavigateToPose` goals through the real simulator and
   assert both terminal action results succeed.
7. Run read-only clock, sensor, TF, lifecycle and action-readiness diagnostics.
8. Upload build/runtime logs, fresh mission/diagnostic JSON and package versions
   even when a step fails. Stop and remove the container afterward.

The workflow job is bounded to 50 minutes, with shorter build, mission and
diagnostic step deadlines. The mission also has its own action and process
timeouts. Old checked-in evidence and videos are excluded from the image by
`.dockerignore`, so CI cannot mistake a previous successful report for a fresh run.
Artifacts expire after seven days; copy the accepted run's evidence into the
release records if long-term access is required.

## Run and inspect it

Pushing a commit to `main` starts the workflow. It can also be run manually:

```bash
gh workflow run clean-simulation.yml --repo Preethesh16/waypoint-forge --ref main
gh run list --repo Preethesh16/waypoint-forge --workflow clean-simulation.yml --limit 5
gh run watch RUN_ID --repo Preethesh16/waypoint-forge --exit-status
gh run download RUN_ID --repo Preethesh16/waypoint-forge --dir ci-evidence
```

Replace `RUN_ID` with the actual run identifier and check that the run's source
commit matches the intended final revision. `build.log` proves the installation
steps ran, `ci-mission.json` contains the real goal outcomes, and `ci-doctor.json`
contains the live diagnostic checks. Failed runs are retained as failed evidence;
they must not be relabeled as passes.

The corresponding local build command is:

```bash
docker build --pull --no-cache --progress=plain -t waypoint-forge:clean .
```

For the visible demonstration, use the README's desktop commands. Headless CI
does not replace the required Gazebo/RViz screen recording, prove zero contacts,
or guarantee identical physics/localization trajectories across different hosts.

## Primary references

- [GitHub standard hosted runners and public-repository pricing](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [Docker clean builds, digest pinning and build-context exclusions](https://docs.docker.com/build/building/best-practices/)
- [ROS/Gazebo supported version combinations](https://gazebosim.org/docs/harmonic/ros_installation/)
