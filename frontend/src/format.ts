export function formatDate(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatDistance(value: number | null) {
  if (value == null) return "-";
  return `${(value / 1000).toFixed(2)} km`;
}

export function formatDuration(seconds: number | null) {
  if (seconds == null) return "-";
  const rounded = Math.round(seconds);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const secs = rounded % 60;
  return hours > 0
    ? `${hours}h ${String(minutes).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`
    : `${minutes}m ${String(secs).padStart(2, "0")}s`;
}

export function formatPace(speed: number | null) {
  if (!speed || speed <= 0) return "-";
  const secondsPerKm = Math.round(1000 / speed);
  const minutes = Math.floor(secondsPerKm / 60);
  const seconds = secondsPerKm % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")} /km`;
}

export function formatSpeed(speed: number | null) {
  if (speed == null) return "-";
  return `${(speed * 3.6).toFixed(1)} km/h`;
}

export function formatNumber(value: number | null, suffix = "") {
  if (value == null) return "-";
  return `${Math.round(value)}${suffix}`;
}

export function formatCadence(value: number | null) {
  if (value == null) return "-";
  return `${Math.round(value * 2)} pas/min`;
}

export function formatMilliseconds(value: number | null) {
  if (value == null) return "-";
  return `${Math.round(value)} ms`;
}

export function formatDecimal(value: number | null, digits = 2, suffix = "") {
  if (value == null) return "-";
  return `${value.toFixed(digits)}${suffix}`;
}
