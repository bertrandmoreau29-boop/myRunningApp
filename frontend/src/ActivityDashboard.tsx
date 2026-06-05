import { ChangeEvent, useEffect, useMemo, useState } from "react";
import {
  Activity as ActivityIcon,
  ArrowDownUp,
  FileUp,
  Mountain,
  RefreshCw,
  Route,
  Timer,
  TrendingDown,
  Zap,
} from "lucide-react";
import {
  Activity,
  Lap,
  RecordPoint,
  TrainingMetrics,
  WeeklyTss,
  fetchActivities,
  fetchActivity,
  fetchLaps,
  fetchRecords,
  fetchTrainingMetrics,
  fetchWeeklyTss,
  updateThresholdPower,
  uploadFit,
} from "./api";
import {
  formatCadence,
  formatDate,
  formatDecimal,
  formatDistance,
  formatDuration,
  formatMilliseconds,
  formatNumber,
  formatPace,
  formatSpeed,
} from "./format";

type DetailState = {
  activity: Activity | null;
  laps: Lap[];
  records: RecordPoint[];
};

const emptyDetail: DetailState = { activity: null, laps: [], records: [] };
type WeeklyMetric = "tss" | "duration" | "distance";
type Page = "dashboard" | "charts";

type EfPoint = {
  date: Date;
  label: string;
  value: number;
  rollingValue: number;
};

export function ActivityDashboard() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [trainingMetrics, setTrainingMetrics] = useState<TrainingMetrics | null>(null);
  const [weeklyTss, setWeeklyTss] = useState<WeeklyTss | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DetailState>(emptyDetail);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [savingThresholdId, setSavingThresholdId] = useState<number | null>(null);
  const [showRecords, setShowRecords] = useState(false);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [weeklyMetric, setWeeklyMetric] = useState<WeeklyMetric>("tss");
  const [page, setPage] = useState<Page>("dashboard");
  const [error, setError] = useState<string | null>(null);

  async function loadActivities(nextSelectedId?: number) {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchActivities();
      setActivities(data);
      const id = nextSelectedId ?? selectedId ?? data[0]?.id ?? null;
      setSelectedId(id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadTrainingMetrics() {
    try {
      const [metrics, week] = await Promise.all([fetchTrainingMetrics(), fetchWeeklyTss()]);
      setTrainingMetrics(metrics);
      setWeeklyTss(week);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    }
  }

  useEffect(() => {
    void loadActivities();
    void loadTrainingMetrics();
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(emptyDetail);
      setShowRecords(false);
      return;
    }

    let isCurrent = true;
    setError(null);
    Promise.all([fetchActivity(selectedId), fetchLaps(selectedId), fetchRecords(selectedId)])
      .then(([activity, laps, records]) => {
        if (isCurrent) {
          setDetail({ activity, laps, records });
          setShowRecords(false);
        }
      })
      .catch((caught) => {
        if (isCurrent) setError(caught instanceof Error ? caught.message : "Erreur inconnue");
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedId]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);
    try {
      const uploaded = await uploadFit(file);
      await loadActivities(uploaded.id);
      await loadTrainingMetrics();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  async function handleThresholdBlur(activity: Activity, value: string) {
    const thresholdPower = Number.parseInt(value, 10);
    if (!Number.isFinite(thresholdPower) || thresholdPower <= 0 || thresholdPower === activity.threshold_power) {
      return;
    }

    setSavingThresholdId(activity.id);
    setError(null);
    try {
      const updated = await updateThresholdPower(activity.id, thresholdPower);
      setActivities((current) => current.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
      if (detail.activity?.id === updated.id) {
        setDetail((current) => ({ ...current, activity: { ...current.activity!, ...updated } }));
      }
      await loadTrainingMetrics();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    } finally {
      setSavingThresholdId(null);
    }
  }

  const stats = useMemo(() => {
    const activity = detail.activity;
    return [
      { label: "Distance", value: formatDistance(activity?.total_distance ?? null), icon: Route },
      { label: "Duree", value: formatDuration(activity?.total_timer_time ?? null), icon: Timer },
      { label: "Allure moy.", value: formatPace(activity?.avg_speed ?? null), icon: RefreshCw },
      { label: "Cadence", value: formatCadence(activity?.avg_cadence ?? null), icon: ActivityIcon },
      { label: "Puissance", value: formatNumber(activity?.avg_power ?? null, " W"), icon: Zap },
      { label: "Puiss. norm.", value: formatNumber(activity?.normalized_power ?? null, " W"), icon: Zap },
      { label: "EF", value: formatDecimal(activity?.efficiency_factor ?? null, 2), icon: Zap },
      { label: "TSS", value: formatDecimal(activity?.training_stress_score ?? null, 1), icon: Zap },
      { label: "D+", value: formatNumber(activity?.ascent ?? null, " m"), icon: Mountain },
      { label: "D-", value: formatNumber(activity?.descent ?? null, " m"), icon: TrendingDown },
    ];
  }, [detail.activity]);

  const sortedActivities = useMemo(() => {
    return [...activities].sort((first, second) => {
      const firstTime = first.started_at ? new Date(first.started_at).getTime() : 0;
      const secondTime = second.started_at ? new Date(second.started_at).getTime() : 0;
      return sortDirection === "asc" ? firstTime - secondTime : secondTime - firstTime;
    });
  }, [activities, sortDirection]);

  const efSeries = useMemo<EfPoint[]>(() => {
    const points = activities
      .filter((activity) => activity.started_at && activity.efficiency_factor != null)
      .map((activity) => ({
        date: new Date(activity.started_at!),
        label: new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit" }).format(
          new Date(activity.started_at!),
        ),
        value: activity.efficiency_factor!,
      }))
      .sort((first, second) => first.date.getTime() - second.date.getTime());

    return points.map((point) => {
      const windowStart = point.date.getTime() - 6 * 24 * 60 * 60 * 1000;
      const windowValues = points.filter(
        (candidate) => candidate.date.getTime() >= windowStart && candidate.date.getTime() <= point.date.getTime(),
      );
      const rollingValue =
        windowValues.reduce((sum, candidate) => sum + candidate.value, 0) / Math.max(1, windowValues.length);
      return { ...point, rollingValue };
    });
  }, [activities]);

  const maxWeeklyTss = useMemo(() => {
    const values = weeklyTss?.days.map((day) => day[weeklyMetric]) ?? [];
    return Math.max(100, ...values);
  }, [weeklyMetric, weeklyTss]);

  const weeklyMetricLabel = {
    tss: "TSS",
    duration: "Duree",
    distance: "Kilometres",
  }[weeklyMetric];

  function formatWeeklyValue(value: number) {
    if (weeklyMetric === "duration") return formatDuration(value);
    if (weeklyMetric === "distance") return formatDistance(value);
    return value.toFixed(0);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>MonAppliRunning</h1>
          <p>Import FIT Garmin, stockage local et exploration des donnees.</p>
        </div>
        <label className="upload-button">
          <FileUp size={18} />
          <span>{isUploading ? "Import..." : "Importer FIT"}</span>
          <input type="file" accept=".fit,.zip" disabled={isUploading} onChange={handleUpload} />
        </label>
      </header>

      <nav className="page-tabs" aria-label="Navigation">
        <button className={page === "dashboard" ? "selected" : ""} type="button" onClick={() => setPage("dashboard")}>
          Tableau de bord
        </button>
        <button className={page === "charts" ? "selected" : ""} type="button" onClick={() => setPage("charts")}>
          Graphiques
        </button>
      </nav>

      {error && <div className="notice">{error}</div>}

      {page === "charts" ? (
        <ChartsPage efSeries={efSeries} />
      ) : (
        <DashboardContent
          activities={activities}
          detail={detail}
          formatWeeklyValue={formatWeeklyValue}
          handleThresholdBlur={handleThresholdBlur}
          isLoading={isLoading}
          loadActivities={() => void loadActivities()}
          maxWeeklyTss={maxWeeklyTss}
          savingThresholdId={savingThresholdId}
          selectedId={selectedId}
          setSelectedId={setSelectedId}
          setShowRecords={setShowRecords}
          setSortDirection={setSortDirection}
          setWeeklyMetric={setWeeklyMetric}
          showRecords={showRecords}
          sortDirection={sortDirection}
          sortedActivities={sortedActivities}
          stats={stats}
          trainingMetrics={trainingMetrics}
          weeklyMetric={weeklyMetric}
          weeklyMetricLabel={weeklyMetricLabel}
          weeklyTss={weeklyTss}
        />
      )}
    </main>
  );
}

function DashboardContent({
  trainingMetrics,
  weeklyTss,
  weeklyMetric,
  maxWeeklyTss,
  weeklyMetricLabel,
  setWeeklyMetric,
  formatWeeklyValue,
  stats,
  isLoading,
  activities,
  sortedActivities,
  selectedId,
  savingThresholdId,
  setSelectedId,
  loadActivities,
  handleThresholdBlur,
  detail,
  showRecords,
  setShowRecords,
  sortDirection,
  setSortDirection,
}: {
  trainingMetrics: TrainingMetrics | null;
  weeklyTss: WeeklyTss | null;
  weeklyMetric: WeeklyMetric;
  maxWeeklyTss: number;
  weeklyMetricLabel: string;
  setWeeklyMetric: (metric: WeeklyMetric) => void;
  formatWeeklyValue: (value: number) => string;
  stats: { label: string; value: string; icon: typeof Route }[];
  isLoading: boolean;
  activities: Activity[];
  sortedActivities: Activity[];
  selectedId: number | null;
  savingThresholdId: number | null;
  setSelectedId: (id: number) => void;
  loadActivities: () => void;
  handleThresholdBlur: (activity: Activity, value: string) => Promise<void>;
  detail: DetailState;
  showRecords: boolean;
  setShowRecords: (updater: (current: boolean) => boolean) => void;
  sortDirection: "asc" | "desc";
  setSortDirection: (updater: (current: "asc" | "desc") => "asc" | "desc") => void;
}) {
  return (
    <>
      <section className="training-widget" aria-label="Metriques TrainingPeaks">
        <article className="training-metric">
          <span>Fitness</span>
          <strong>{formatDecimal(trainingMetrics?.fitness ?? null, 1)}</strong>
        </article>
        <article className="training-metric">
          <span>Forme</span>
          <strong>{formatDecimal(trainingMetrics?.form ?? null, 1)}</strong>
        </article>
        <article className="training-metric">
          <span>Fatigue</span>
          <strong>{formatDecimal(trainingMetrics?.fatigue ?? null, 1)}</strong>
        </article>
      </section>

      <section className="weekly-tss-widget" aria-label="TSS de la semaine">
        <div className="weekly-tss-header">
          <h2>Vue semaine</h2>
          <div className="weekly-totals" aria-label="Totaux semaine">
            <button
              className={weeklyMetric === "tss" ? "selected" : ""}
              type="button"
              onClick={() => setWeeklyMetric("tss")}
            >
              <span>TSS</span>
              <strong>{weeklyTss ? weeklyTss.total_tss.toFixed(1) : "-"}</strong>
            </button>
            <button
              className={weeklyMetric === "duration" ? "selected" : ""}
              type="button"
              onClick={() => setWeeklyMetric("duration")}
            >
              <span>Duree</span>
              <strong>{weeklyTss ? formatDuration(weeklyTss.total_duration) : "-"}</strong>
            </button>
            <button
              className={weeklyMetric === "distance" ? "selected" : ""}
              type="button"
              onClick={() => setWeeklyMetric("distance")}
            >
              <span>Km</span>
              <strong>{weeklyTss ? formatDistance(weeklyTss.total_distance) : "-"}</strong>
            </button>
          </div>
        </div>
        <p className="weekly-chart-label">{weeklyMetricLabel}</p>
        <div className="weekly-bars">
          {(weeklyTss?.days ?? []).map((day) => (
            <article className="weekly-bar" key={day.date}>
              <div className="weekly-bar-track">
                <div
                  className="weekly-bar-fill"
                  style={{ height: `${Math.max(4, (day[weeklyMetric] / maxWeeklyTss) * 100)}%` }}
                />
              </div>
              <strong>{formatWeeklyValue(day[weeklyMetric])}</strong>
              <span>{day.label}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="stats-grid">
        {stats.map(({ label, value, icon: Icon }) => (
          <article className="metric" key={label}>
            <Icon size={18} />
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className="workspace">
        <div className="panel activities-panel">
          <div className="panel-header">
            <h2>Activites</h2>
            <div className="panel-actions">
              <button
                className="icon-button"
                type="button"
                onClick={() => setSortDirection((current) => (current === "asc" ? "desc" : "asc"))}
                title={sortDirection === "asc" ? "Afficher les plus recentes en haut" : "Afficher les plus anciennes en haut"}
              >
                <ArrowDownUp size={17} />
              </button>
              <button className="icon-button" type="button" onClick={() => void loadActivities()} title="Rafraichir">
                <RefreshCw size={17} />
              </button>
            </div>
          </div>
          {isLoading ? (
            <p className="empty-state">Chargement...</p>
          ) : activities.length === 0 ? (
            <p className="empty-state">Aucune activite importee.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Distance</th>
                    <th>Duree</th>
                    <th>Allure</th>
                    <th>FC moy.</th>
                    <th>Cadence</th>
                    <th>Puissance</th>
                    <th>Puiss. norm.</th>
                    <th>FTP</th>
                    <th>EF</th>
                    <th>IF</th>
                    <th>TSS</th>
                    <th>D+</th>
                    <th>D-</th>
                    <th>Contact sol</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedActivities.map((activity) => (
                    <tr
                      key={activity.id}
                      className={activity.id === selectedId ? "selected" : ""}
                      onClick={() => setSelectedId(activity.id)}
                    >
                      <td>{formatDate(activity.started_at)}</td>
                      <td>{formatDistance(activity.total_distance)}</td>
                      <td>{formatDuration(activity.total_timer_time)}</td>
                      <td>{formatPace(activity.avg_speed)}</td>
                      <td>{formatNumber(activity.avg_heart_rate, " bpm")}</td>
                      <td>{formatCadence(activity.avg_cadence)}</td>
                      <td>{formatNumber(activity.avg_power, " W")}</td>
                      <td>{formatNumber(activity.normalized_power, " W")}</td>
                      <td>
                        <input
                          className="ftp-input"
                          type="number"
                          min="1"
                          max="2000"
                          defaultValue={activity.threshold_power ?? ""}
                          disabled={savingThresholdId === activity.id}
                          onBlur={(event) => void handleThresholdBlur(activity, event.currentTarget.value)}
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              event.currentTarget.blur();
                            }
                          }}
                          title="FTP en watts"
                        />
                      </td>
                      <td>{formatDecimal(activity.efficiency_factor, 2)}</td>
                      <td>{formatDecimal(activity.intensity_factor, 2)}</td>
                      <td>{formatDecimal(activity.training_stress_score, 1)}</td>
                      <td>{formatNumber(activity.ascent, " m")}</td>
                      <td>{formatNumber(activity.descent, " m")}</td>
                      <td>{formatMilliseconds(activity.avg_ground_contact_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="panel detail-panel">
          <div className="panel-header">
            <h2>Details</h2>
            <span>{detail.activity ? formatDate(detail.activity.started_at) : "-"}</span>
          </div>

          <div className="summary-strip">
            <span>Sport: {detail.activity?.sport ?? "-"}</span>
            <span>Vitesse moy.: {formatSpeed(detail.activity?.avg_speed ?? null)}</span>
            <span>Puissance: {formatNumber(detail.activity?.avg_power ?? null, " W")}</span>
            <span>Puiss. norm.: {formatNumber(detail.activity?.normalized_power ?? null, " W")}</span>
            <span>FTP: {formatNumber(detail.activity?.threshold_power ?? null, " W")}</span>
            <span>EF: {formatDecimal(detail.activity?.efficiency_factor ?? null, 2)}</span>
            <span>TSS: {formatDecimal(detail.activity?.training_stress_score ?? null, 1)}</span>
            <span>Contact sol: {formatMilliseconds(detail.activity?.avg_ground_contact_time ?? null)}</span>
            <span>D+: {formatNumber(detail.activity?.ascent ?? null, " m")}</span>
            <span>D-: {formatNumber(detail.activity?.descent ?? null, " m")}</span>
          </div>

          <h3>Tours</h3>
          <div className="table-scroll compact">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Distance</th>
                  <th>Duree</th>
                  <th>Allure</th>
                  <th>FC moy.</th>
                  <th>Cadence</th>
                  <th>Puissance</th>
                  <th>Puiss. norm.</th>
                  <th>Contact sol</th>
                </tr>
              </thead>
              <tbody>
                {detail.laps.map((lap) => (
                  <tr key={lap.id}>
                    <td>{lap.lap_index}</td>
                    <td>{formatDistance(lap.total_distance)}</td>
                    <td>{formatDuration(lap.total_timer_time)}</td>
                    <td>{formatPace(lap.avg_speed)}</td>
                    <td>{formatNumber(lap.avg_heart_rate, " bpm")}</td>
                    <td>{formatCadence(lap.avg_cadence)}</td>
                    <td>{formatNumber(lap.avg_power, " W")}</td>
                    <td>{formatNumber(lap.normalized_power, " W")}</td>
                    <td>{formatMilliseconds(lap.avg_ground_contact_time)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="accordion">
            <button
              className="accordion-trigger"
              type="button"
              onClick={() => setShowRecords((current) => !current)}
            >
              <span>Points</span>
              <strong>{showRecords ? "Fermer" : "Ouvrir"}</strong>
            </button>

            {showRecords && (
              <div className="table-scroll records">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Temps</th>
                      <th>Distance</th>
                      <th>Vitesse</th>
                      <th>FC</th>
                      <th>Cadence</th>
                      <th>Puissance</th>
                      <th>Contact sol</th>
                      <th>Altitude</th>
                      <th>GPS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.records.map((record) => (
                      <tr key={record.id}>
                        <td>{record.record_index}</td>
                        <td>{formatDate(record.timestamp)}</td>
                        <td>{formatDistance(record.distance)}</td>
                        <td>{formatSpeed(record.speed)}</td>
                        <td>{formatNumber(record.heart_rate, " bpm")}</td>
                        <td>{formatCadence(record.cadence)}</td>
                        <td>{formatNumber(record.power, " W")}</td>
                        <td>{formatMilliseconds(record.ground_contact_time)}</td>
                        <td>{formatNumber(record.altitude, " m")}</td>
                        <td>
                          {record.latitude == null || record.longitude == null
                            ? "-"
                            : `${record.latitude.toFixed(5)}, ${record.longitude.toFixed(5)}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </section>
    </>
  );
}

function ChartsPage({ efSeries }: { efSeries: EfPoint[] }) {
  const chart = useMemo(() => buildEfChart(efSeries), [efSeries]);

  if (efSeries.length === 0) {
    return (
      <section className="chart-page">
        <div className="panel chart-panel">
          <h2>EF au fil du temps</h2>
          <p className="empty-state">Aucune activite avec EF disponible.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="chart-page">
      <div className="panel chart-panel">
        <div className="chart-header">
          <div>
            <h2>EF au fil du temps</h2>
            <p>Efficiency Factor et moyenne 7 jours</p>
          </div>
          <div className="chart-legend">
            <span className="legend-current">EF</span>
            <span className="legend-average">Moy. 7 jours</span>
          </div>
        </div>
        <svg className="line-chart" viewBox="0 0 900 360" role="img" aria-label="Graphique EF">
          {chart.gridLines.map((line) => (
            <g key={line.value}>
              <line x1="56" x2="872" y1={line.y} y2={line.y} />
              <text x="44" y={line.y + 4}>
                {line.value.toFixed(2)}
              </text>
            </g>
          ))}
          <polyline className="average-line" points={chart.averagePath} />
          <polyline className="current-line" points={chart.currentPath} />
          {chart.points.map((point) => (
            <g key={`${point.x}-${point.label}`}>
              <circle cx={point.x} cy={point.y} r="4" />
              <text className="x-label" x={point.x} y="338">
                {point.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
}

function buildEfChart(series: EfPoint[]) {
  const width = 900;
  const height = 360;
  const left = 56;
  const right = 28;
  const top = 28;
  const bottom = 52;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const values = series.flatMap((point) => [point.value, point.rollingValue]);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const min = Math.max(0, rawMin - 0.05);
  const max = rawMax + 0.05;
  const span = Math.max(0.1, max - min);
  const xStep = series.length > 1 ? chartWidth / (series.length - 1) : chartWidth;
  const yFor = (value: number) => top + (1 - (value - min) / span) * chartHeight;
  const xFor = (index: number) => left + index * xStep;
  const points = series.map((point, index) => ({
    ...point,
    x: xFor(index),
    y: yFor(point.value),
    rollingY: yFor(point.rollingValue),
  }));
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = min + span * ratio;
    return { value, y: yFor(value) };
  });

  return {
    points,
    gridLines,
    currentPath: points.map((point) => `${point.x},${point.y}`).join(" "),
    averagePath: points.map((point) => `${point.x},${point.rollingY}`).join(" "),
  };
}
