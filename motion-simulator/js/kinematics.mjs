export const DEFAULTS = Object.freeze({
  wheelDiameterMm: 87,
  wheelWidthMm: 40,
  trackWidthMm: 260,
  countsPerRev: 2464,
  ratedRpm: 178,
  chassisLengthMm: 335,
  chassisWidthMm: 260,
});

const EPSILON = 1e-9;

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function deriveGeometry(params = DEFAULTS) {
  const wheelDiameterMm = positive(params.wheelDiameterMm, "wheelDiameterMm");
  const trackWidthMm = positive(params.trackWidthMm, "trackWidthMm");
  const countsPerRev = positive(params.countsPerRev, "countsPerRev");
  const ratedRpm = positive(params.ratedRpm, "ratedRpm");
  const circumferenceMm = Math.PI * wheelDiameterMm;
  const mmPerCount = circumferenceMm / countsPerRev;
  const countsPerMm = 1 / mmPerCount;
  const countsPerDegree = ((trackWidthMm / 2) * Math.PI / 180) / mmPerCount;
  const ratedSpeedMps = (ratedRpm / 60) * (circumferenceMm / 1000);
  const ratedCountsPerSecond = (ratedRpm / 60) * countsPerRev;
  const secondsToInt16Limit = 32767 / ratedCountsPerSecond;

  return {
    circumferenceMm,
    mmPerCount,
    countsPerMm,
    countsPerDegree,
    ratedSpeedMps,
    ratedCountsPerSecond,
    secondsToInt16Limit,
  };
}

export function wheelRpmToMotion(leftRpm, rightRpm, params = DEFAULTS) {
  const geometry = deriveGeometry(params);
  const trackM = positive(params.trackWidthMm, "trackWidthMm") / 1000;
  const leftMps = (Number(leftRpm) / 60) * (geometry.circumferenceMm / 1000);
  const rightMps = (Number(rightRpm) / 60) * (geometry.circumferenceMm / 1000);
  const linearMps = (rightMps + leftMps) / 2;
  const angularRadps = (rightMps - leftMps) / trackM;
  const radiusM = Math.abs(angularRadps) < EPSILON ? Infinity : linearMps / angularRadps;

  return {
    leftMps,
    rightMps,
    linearMps,
    angularRadps,
    angularDegps: angularRadps * 180 / Math.PI,
    radiusM,
    leftCountsPerSecond: (Number(leftRpm) / 60) * params.countsPerRev,
    rightCountsPerSecond: (Number(rightRpm) / 60) * params.countsPerRev,
  };
}

export function bodyCommandToWheelRpm(linearMps, angularRadps, params = DEFAULTS) {
  const trackM = positive(params.trackWidthMm, "trackWidthMm") / 1000;
  const circumferenceM = Math.PI * positive(params.wheelDiameterMm, "wheelDiameterMm") / 1000;
  const leftMps = Number(linearMps) - Number(angularRadps) * trackM / 2;
  const rightMps = Number(linearMps) + Number(angularRadps) * trackM / 2;
  return {
    leftRpm: leftMps / circumferenceM * 60,
    rightRpm: rightMps / circumferenceM * 60,
  };
}

export function stepPose(pose, leftRpm, rightRpm, dtSeconds, params = DEFAULTS) {
  const dt = Math.max(0, Number(dtSeconds));
  const motion = wheelRpmToMotion(leftRpm, rightRpm, params);
  const theta0 = Number(pose.thetaRad) || 0;
  const theta1 = theta0 + motion.angularRadps * dt;
  let xM = Number(pose.xM) || 0;
  let yM = Number(pose.yM) || 0;

  if (Math.abs(motion.angularRadps) < EPSILON) {
    xM += motion.linearMps * dt * Math.cos(theta0);
    yM += motion.linearMps * dt * Math.sin(theta0);
  } else {
    const radius = motion.linearMps / motion.angularRadps;
    xM += radius * (Math.sin(theta1) - Math.sin(theta0));
    yM -= radius * (Math.cos(theta1) - Math.cos(theta0));
  }

  return {
    xM,
    yM,
    thetaRad: normalizeAngle(theta1),
    distanceM: (Number(pose.distanceM) || 0) + Math.abs(motion.linearMps) * dt,
    leftCounts: (Number(pose.leftCounts) || 0) + motion.leftCountsPerSecond * dt,
    rightCounts: (Number(pose.rightCounts) || 0) + motion.rightCountsPerSecond * dt,
  };
}

export function simulateDuration(leftRpm, rightRpm, durationSeconds, params = DEFAULTS) {
  const motion = wheelRpmToMotion(leftRpm, rightRpm, params);
  const pose = stepPose(emptyPose(), leftRpm, rightRpm, durationSeconds, params);
  return {
    ...pose,
    leftDistanceM: motion.leftMps * durationSeconds,
    rightDistanceM: motion.rightMps * durationSeconds,
    headingChangeRad: motion.angularRadps * durationSeconds,
    motion,
  };
}

export function emptyPose() {
  return { xM: 0, yM: 0, thetaRad: 0, distanceM: 0, leftCounts: 0, rightCounts: 0 };
}

export function normalizeAngle(angleRad) {
  return Math.atan2(Math.sin(angleRad), Math.cos(angleRad));
}

function positive(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) throw new RangeError(`${name} must be positive`);
  return number;
}
