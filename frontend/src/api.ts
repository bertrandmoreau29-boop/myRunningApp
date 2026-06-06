export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export type Activity = {
  id: number;
  filename: string;
  sport: string | null;
  sub_sport: string | null;
  session_type: string | null;
  route_location: string | null;
  shoe_type: string | null;
  comment: string | null;
  distance_manually_edited: number | null;
  started_at: string | null;
  total_elapsed_time: number | null;
  total_timer_time: number | null;
  total_distance: number | null;
  avg_speed: number | null;
  max_speed: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  avg_cadence: number | null;
  max_cadence: number | null;
  avg_power: number | null;
  max_power: number | null;
  normalized_power: number | null;
  threshold_power: number | null;
  intensity_factor: number | null;
  efficiency_factor: number | null;
  training_stress_score: number | null;
  avg_ground_contact_time: number | null;
  ascent: number | null;
  descent: number | null;
  created_at: string;
  lap_count: number;
  record_count: number;
  raw_summary?: string | null;
};

export type Lap = {
  id: number;
  lap_index: number;
  started_at: string | null;
  total_elapsed_time: number | null;
  total_timer_time: number | null;
  total_distance: number | null;
  avg_speed: number | null;
  max_speed: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  avg_cadence: number | null;
  max_cadence: number | null;
  avg_power: number | null;
  max_power: number | null;
  normalized_power: number | null;
  avg_ground_contact_time: number | null;
};

export type RecordPoint = {
  id: number;
  record_index: number;
  timestamp: string | null;
  distance: number | null;
  speed: number | null;
  heart_rate: number | null;
  cadence: number | null;
  power: number | null;
  ground_contact_time: number | null;
  altitude: number | null;
  latitude: number | null;
  longitude: number | null;
  temperature: number | null;
};

export type TrainingMetrics = {
  fitness: number;
  form: number;
  fatigue: number;
};

export type WeeklyTssDay = {
  date: string;
  label: string;
  tss: number;
  duration: number;
  distance: number;
};

export type WeeklyTss = {
  start_date: string;
  end_date: string;
  days: WeeklyTssDay[];
  total_tss: number;
  total_duration: number;
  total_distance: number;
};

export type HrZoneBreakdown = {
  key: string;
  label: string;
  range: string;
  seconds: number;
  color: string;
};

export type WeeklyHrDistribution = {
  max_hr: number;
  start_date: string;
  end_date: string;
  endurance_seconds: number;
  quality_weighted_seconds: number;
  quality_raw_seconds: number;
  endurance_ratio: number;
  quality_ratio: number;
  zones: HrZoneBreakdown[];
  tips: string;
};

export type AppConfig = {
  default_ftp: number;
  default_max_hr: number;
  default_shoe_type: string | null;
  session_types: string[];
  route_locations: string[];
  shoe_types: string[];
};

export type ActivityUpdate = Partial<{
  session_type: string | null;
  route_location: string | null;
  shoe_type: string | null;
  comment: string | null;
  total_distance: number;
  threshold_power: number;
}>;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `Erreur HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchActivities() {
  return request<Activity[]>("/activities");
}

export function fetchActivity(id: number) {
  return request<Activity>(`/activities/${id}`);
}

export function fetchLaps(id: number) {
  return request<Lap[]>(`/activities/${id}/laps`);
}

export function fetchRecords(id: number) {
  return request<RecordPoint[]>(`/activities/${id}/records?limit=10000`);
}

export function fetchTrainingMetrics() {
  return request<TrainingMetrics>("/training/metrics");
}

export function fetchConfig() {
  return request<AppConfig>("/config");
}

export function updateConfig(payload: Partial<Pick<AppConfig, "default_ftp" | "default_max_hr" | "default_shoe_type">>) {
  return request<AppConfig>("/config", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function addConfigOption(category: "session_type" | "route_location" | "shoe_type", value: string) {
  return request<{ id: number; category: string; value: string }>("/config/options", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, value }),
  });
}

export function fetchWeeklyTss() {
  return request<WeeklyTss>("/training/week");
}

export function fetchWeeklyHrDistribution() {
  return request<WeeklyHrDistribution>("/training/week-zones");
}

export function uploadFit(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<Activity>("/activities/upload", {
    method: "POST",
    body: form,
  });
}

export function updateThresholdPower(id: number, thresholdPower: number) {
  return request<Activity>(`/activities/${id}/threshold-power`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ threshold_power: thresholdPower }),
  });
}

export function updateActivity(id: number, payload: ActivityUpdate) {
  return request<Activity>(`/activities/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
