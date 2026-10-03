import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULTS, bodyCommandToWheelRpm, deriveGeometry, emptyPose, simulateDuration, stepPose, wheelRpmToMotion } from '../js/kinematics.mjs';

const close = (actual, expected, tolerance = 1e-6) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

test('latest measured geometry produces the documented constants', () => {
  const g = deriveGeometry(DEFAULTS);
  close(g.ratedSpeedMps, 0.810845, 1e-6);
  close(g.mmPerCount, 0.110925, 1e-6);
  close(g.countsPerDegree, 20.4545, 1e-3);
  close(g.ratedCountsPerSecond, 7309.8667, 1e-3);
  close(g.secondsToInt16Limit, 4.48258, 1e-4);
});

test('equal wheel speed moves straight without changing heading', () => {
  const result = simulateDuration(100, 100, 2, DEFAULTS);
  close(result.yM, 0);
  close(result.thetaRad, 0);
  close(result.xM, result.motion.linearMps * 2);
});

test('opposite wheel speed spins in place', () => {
  const motion = wheelRpmToMotion(-60, 60, DEFAULTS);
  close(motion.linearMps, 0);
  assert.ok(motion.angularRadps > 0);
  const pose = stepPose(emptyPose(), -60, 60, 1, DEFAULTS);
  close(pose.xM, 0);
  close(pose.yM, 0);
});

test('arc integration follows the exact differential-drive solution', () => {
  const motion = wheelRpmToMotion(50, 100, DEFAULTS);
  const pose = stepPose(emptyPose(), 50, 100, 1.25, DEFAULTS);
  const heading = motion.angularRadps * 1.25;
  const radius = motion.linearMps / motion.angularRadps;
  close(pose.xM, radius * Math.sin(heading));
  close(pose.yM, radius * (1 - Math.cos(heading)));
});

test('body command round-trips to requested linear and angular speeds', () => {
  const wheels = bodyCommandToWheelRpm(0.2, 0.7, DEFAULTS);
  const motion = wheelRpmToMotion(wheels.leftRpm, wheels.rightRpm, DEFAULTS);
  close(motion.linearMps, 0.2);
  close(motion.angularRadps, 0.7);
});
