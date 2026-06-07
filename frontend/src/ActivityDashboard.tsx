import { ChangeEvent, useEffect, useMemo, useState } from "react";
import {
  Activity as ActivityIcon,
  ArrowDownUp,
  FileUp,
  CalendarDays,
  Mountain,
  RefreshCw,
  Route,
  Timer,
  TrendingDown,
  Trash2,
  Zap,
} from "lucide-react";
import {
  Activity,
  AppConfig,
  Lap,
  RecordPoint,
  TrainingCalendar,
  TrainingFractions,
  TrainingMetrics,
  WeeklyHrDistribution,
  WeeklyTss,
  addConfigOption,
  deleteConfigOption,
  fetchActivities,
  fetchActivity,
  fetchConfig,
  fetchLaps,
  fetchRecords,
  fetchTrainingCalendar,
  fetchTrainingFractions,
  fetchTrainingMetrics,
  fetchWeeklyHrDistribution,
  fetchWeeklyTss,
  updateActivity,
  updateConfig,
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
type Page = "dashboard" | "charts" | "calendar" | "fractions" | "config";

type EfPoint = {
  date: Date;
  label: string;
  value: number;
  rollingValue: number;
};

function cycleAbbreviation(appConfig: AppConfig | null, value: string | null | undefined) {
  if (!value) return "-";
  return appConfig?.cycles.find((cycle) => cycle.value === value)?.abbreviation ?? value.slice(0, 3).toUpperCase();
}

export function ActivityDashboard() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [trainingMetrics, setTrainingMetrics] = useState<TrainingMetrics | null>(null);
  const [weeklyTss, setWeeklyTss] = useState<WeeklyTss | null>(null);
  const [weeklyHrDistribution, setWeeklyHrDistribution] = useState<WeeklyHrDistribution | null>(null);
  const [trainingCalendar, setTrainingCalendar] = useState<TrainingCalendar | null>(null);
  const [trainingFractions, setTrainingFractions] = useState<TrainingFractions | null>(null);
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DetailState>(emptyDetail);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [savingThresholdId, setSavingThresholdId] = useState<number | null>(null);
  const [showRecords, setShowRecords] = useState(false);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [weeklyMetric, setWeeklyMetric] = useState<WeeklyMetric>("tss");
  const [page, setPage] = useState<Page>("dashboard");
  const [editingDistanceId, setEditingDistanceId] = useState<number | null>(null);
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
      const [metrics, week, hrDistribution, calendar, fractions] = await Promise.all([
        fetchTrainingMetrics(),
        fetchWeeklyTss(),
        fetchWeeklyHrDistribution(),
        fetchTrainingCalendar(),
        fetchTrainingFractions(),
      ]);
      setTrainingMetrics(metrics);
      setWeeklyTss(week);
      setWeeklyHrDistribution(hrDistribution);
      setTrainingCalendar(calendar);
      setTrainingFractions(fractions);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    }
  }

  async function loadConfig() {
    try {
      setAppConfig(await fetchConfig());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    }
  }

  useEffect(() => {
    void loadActivities();
    void loadTrainingMetrics();
    void loadConfig();
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
      await loadConfig();
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

  function mergeUpdatedActivity(updated: Activity) {
    setActivities((current) => current.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
    if (detail.activity?.id === updated.id) {
      setDetail((current) => ({ ...current, activity: { ...current.activity!, ...updated } }));
    }
  }

  async function handleActivityUpdate(activity: Activity, payload: Parameters<typeof updateActivity>[1]) {
    setError(null);
    try {
      const updated = await updateActivity(activity.id, payload);
      mergeUpdatedActivity(updated);
      await loadTrainingMetrics();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    }
  }

  async function handleAddOption(category: "session_type" | "route_location" | "shoe_type" | "cycle") {
    const value = window.prompt("Nouvelle valeur");
    if (!value?.trim()) return;
    const abbreviation = category === "cycle" ? window.prompt("Abreviation du cycle (3 lettres)") : undefined;
    if (category === "cycle" && !abbreviation?.trim()) return;
    setError(null);
    try {
      await addConfigOption(category, value.trim(), abbreviation?.trim());
      await loadConfig();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
    }
  }

  async function handleDeleteOption(category: "session_type" | "route_location" | "shoe_type" | "cycle", value: string) {
    const confirmed = window.confirm(`Supprimer "${value}" ?`);
    if (!confirmed) return;
    setError(null);
    try {
      setAppConfig(await deleteConfigOption(category, value));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Erreur inconnue");
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
        <button className={page === "calendar" ? "selected" : ""} type="button" onClick={() => setPage("calendar")}>
          Calendrier
        </button>
        <button className={page === "fractions" ? "selected" : ""} type="button" onClick={() => setPage("fractions")}>
          Fractions
        </button>
        <button className={page === "config" ? "selected" : ""} type="button" onClick={() => setPage("config")}>
          Configuration
        </button>
      </nav>

      {error && <div className="notice">{error}</div>}

      {page === "charts" ? (
        <ChartsPage efSeries={efSeries} />
      ) : page === "calendar" ? (
        <CalendarPage calendar={trainingCalendar} />
      ) : page === "fractions" ? (
        <FractionsPage fractions={trainingFractions} />
      ) : page === "config" ? (
        <ConfigPage
          appConfig={appConfig}
          onAddOption={handleAddOption}
          onDeleteOption={handleDeleteOption}
          onRefresh={loadConfig}
          onUpdateConfig={async (payload) => {
            const updated = await updateConfig(payload);
            setAppConfig(updated);
            await loadTrainingMetrics();
          }}
        />
      ) : (
        <DashboardContent
          activities={activities}
          detail={detail}
          formatWeeklyValue={formatWeeklyValue}
          handleThresholdBlur={handleThresholdBlur}
          handleActivityUpdate={handleActivityUpdate}
          onAddOption={handleAddOption}
          onUpdateConfig={async (payload) => {
            const updated = await updateConfig(payload);
            setAppConfig(updated);
            await loadTrainingMetrics();
          }}
          appConfig={appConfig}
          editingDistanceId={editingDistanceId}
          isLoading={isLoading}
          loadActivities={() => void loadActivities()}
          maxWeeklyTss={maxWeeklyTss}
          savingThresholdId={savingThresholdId}
          selectedId={selectedId}
          setSelectedId={setSelectedId}
          setEditingDistanceId={setEditingDistanceId}
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
          weeklyHrDistribution={weeklyHrDistribution}
          weeklyTss={weeklyTss}
        />
      )}
    </main>
  );
}

function DashboardContent({
  trainingMetrics,
  weeklyTss,
  weeklyHrDistribution,
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
  appConfig,
  editingDistanceId,
  handleActivityUpdate,
  onAddOption,
  onUpdateConfig,
  setEditingDistanceId,
}: {
  trainingMetrics: TrainingMetrics | null;
  weeklyTss: WeeklyTss | null;
  weeklyHrDistribution: WeeklyHrDistribution | null;
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
  appConfig: AppConfig | null;
  editingDistanceId: number | null;
  handleActivityUpdate: (activity: Activity, payload: Parameters<typeof updateActivity>[1]) => Promise<void>;
  onAddOption: (category: "session_type" | "route_location" | "shoe_type" | "cycle") => Promise<void>;
  onUpdateConfig: (
    payload: Partial<Pick<AppConfig, "default_ftp" | "default_max_hr" | "default_shoe_type" | "default_cycle">>,
  ) => Promise<void>;
  setEditingDistanceId: (id: number | null) => void;
}) {
  const [commentActivity, setCommentActivity] = useState<Activity | null>(null);
  const [commentDraft, setCommentDraft] = useState("");

  function openCommentModal(activity: Activity) {
    setCommentActivity(activity);
    setCommentDraft(activity.comment ?? "");
  }

  async function saveComment() {
    if (!commentActivity) return;
    await handleActivityUpdate(commentActivity, { comment: commentDraft });
    setCommentActivity(null);
  }

  function activityForWeekDay(date: string) {
    return sortedActivities.find((activity) => activity.started_at?.slice(0, 10) === date) ?? null;
  }

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

      <section className="weekly-zone">
        <div className="side-config weekly-side-config">
          <label>
            <span>FTP par defaut</span>
            <input
              type="number"
              min="1"
              max="2000"
              defaultValue={appConfig?.default_ftp ?? ""}
              onBlur={(event) => {
                const value = Number.parseInt(event.currentTarget.value, 10);
                if (Number.isFinite(value)) void onUpdateConfig({ default_ftp: value });
              }}
            />
          </label>
          <label>
            <span>FCmax</span>
            <input
              type="number"
              min="1"
              max="250"
              defaultValue={appConfig?.default_max_hr ?? 176}
              onBlur={(event) => {
                const value = Number.parseInt(event.currentTarget.value, 10);
                if (Number.isFinite(value)) void onUpdateConfig({ default_max_hr: value });
              }}
            />
          </label>
          <label>
            <span>Chaussures par defaut</span>
            <select
              value={appConfig?.default_shoe_type ?? ""}
              onChange={(event) => void onUpdateConfig({ default_shoe_type: event.currentTarget.value })}
            >
              <option value="">-</option>
              {(appConfig?.shoe_types ?? []).map((shoe) => (
                <option key={shoe} value={shoe}>
                  {shoe}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Cycle en cours</span>
            <select
              value={appConfig?.default_cycle ?? ""}
              onChange={(event) => void onUpdateConfig({ default_cycle: event.currentTarget.value })}
            >
              <option value="">-</option>
              {(appConfig?.cycles ?? []).map((cycle) => (
                <option key={cycle.value} value={cycle.value}>
                  {cycle.value}
                </option>
              ))}
            </select>
            <small className="cycle-current-abbr">
              {appConfig?.default_cycle ?? "-"} / {cycleAbbreviation(appConfig, appConfig?.default_cycle)}
            </small>
          </label>
        </div>

        <HrScaleWidget maxHr={appConfig?.default_max_hr ?? weeklyHrDistribution?.max_hr ?? 176} />

        <div className="weekly-tss-widget" aria-label="TSS de la semaine">
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
            {(weeklyTss?.days ?? []).map((day) => {
              const dayActivity = activityForWeekDay(day.date);
              return (
              <button
                className={dayActivity?.id === selectedId ? "weekly-bar selected" : "weekly-bar"}
                disabled={!dayActivity}
                key={day.date}
                onClick={() => {
                  if (dayActivity) setSelectedId(dayActivity.id);
                }}
                title={dayActivity ? "Selectionner la seance" : "Aucune seance ce jour"}
                type="button"
              >
                <div className="weekly-bar-track">
                  <div
                    className="weekly-bar-fill"
                    style={{ height: `${Math.max(4, (day[weeklyMetric] / maxWeeklyTss) * 100)}%` }}
                  />
                </div>
                <strong>{formatWeeklyValue(day[weeklyMetric])}</strong>
                <span>{day.label}</span>
              </button>
              );
            })}
          </div>
        </div>

        <EnduranceQualityWidget distribution={weeklyHrDistribution} />
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
            <div className="panel-title-inline">
              <h2>Activites</h2>
              <span>{activities.length} seance{activities.length > 1 ? "s" : ""}</span>
            </div>
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
            <div className="activities-content">
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Cycle</th>
                      <th>Date</th>
                      <th>Distance</th>
                      <th>Duree</th>
                      <th>Type de seance</th>
                      <th>Commentaire</th>
                      <th>Lieu/parcours</th>
                      <th>Allure</th>
                      <th>FC moy.</th>
                      <th>Puissance</th>
                      <th>Puiss. norm.</th>
                      <th>FTP</th>
                      <th>EF</th>
                      <th>IF</th>
                      <th>TSS</th>
                      <th>D+</th>
                      <th>D-</th>
                      <th>Cadence</th>
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
                        <td>
                          <CycleSelect
                            appConfig={appConfig}
                            value={activity.cycle ?? appConfig?.default_cycle ?? null}
                            onChange={(value) => void handleActivityUpdate(activity, { cycle: value })}
                          />
                        </td>
                        <td>{formatDate(activity.started_at)}</td>
                        <td>
                          <DistanceCell
                            activity={activity}
                            isEditing={editingDistanceId === activity.id}
                            onEdit={() => setEditingDistanceId(activity.id)}
                            onSave={(distanceKm) => {
                              setEditingDistanceId(null);
                              void handleActivityUpdate(activity, { total_distance: distanceKm * 1000 });
                            }}
                          />
                        </td>
                        <td>{formatDuration(activity.total_timer_time)}</td>
                        <td>
                          <EditableSelect
                            value={activity.session_type}
                            options={appConfig?.session_types ?? []}
                            onAdd={() => void onAddOption("session_type")}
                            onChange={(value) => void handleActivityUpdate(activity, { session_type: value })}
                          />
                        </td>
                        <td>
                          <button
                            className={activity.comment ? "comment-pill filled" : "comment-pill"}
                            onClick={(event) => {
                              event.stopPropagation();
                              openCommentModal(activity);
                            }}
                            type="button"
                          >
                            {activity.comment ? "Voir" : "Ajouter"}
                          </button>
                        </td>
                        <td>
                          <EditableSelect
                            value={activity.route_location}
                            options={appConfig?.route_locations ?? []}
                            onAdd={() => void onAddOption("route_location")}
                            onChange={(value) => void handleActivityUpdate(activity, { route_location: value })}
                          />
                        </td>
                        <td>{formatPace(activity.avg_speed)}</td>
                        <td>{formatNumber(activity.avg_heart_rate, " bpm")}</td>
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
                        <td>{formatCadence(activity.avg_cadence)}</td>
                        <td>{formatMilliseconds(activity.avg_ground_contact_time)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <div className="panel laps-panel">
          <div className="panel-header">
            <h2>Tours</h2>
            <span>{detail.activity ? formatDate(detail.activity.started_at) : "-"}</span>
          </div>

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
      {commentActivity && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setCommentActivity(null)}>
          <div className="comment-modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <div className="panel-header">
              <div>
                <h2>Commentaire</h2>
                <span>{formatDate(commentActivity.started_at)}</span>
              </div>
            </div>
            <textarea
              autoFocus
              className="comment-modal-input"
              onChange={(event) => setCommentDraft(event.currentTarget.value)}
              value={commentDraft}
            />
            <div className="modal-actions">
              <button className="secondary-button" type="button" onClick={() => setCommentActivity(null)}>
                Annuler
              </button>
              <button className="add-button" type="button" onClick={() => void saveComment()}>
                Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function HrScaleWidget({ maxHr }: { maxHr: number }) {
  const ticks = [95, 90, 85, 80, 75, 70, 65];

  return (
    <aside className="hr-scale-widget" aria-label="Repères FCM">
      <div className="hr-scale-header">
        <h2>FCM</h2>
        <strong>{maxHr} bpm</strong>
      </div>
      <div className="hr-scale-track">
        {ticks.map((percent) => (
          <div className="hr-scale-row" key={percent}>
            <span>{percent}%</span>
            <i />
            <strong>{Math.round((maxHr * percent) / 100)}</strong>
          </div>
        ))}
      </div>
    </aside>
  );
}

function EnduranceQualityWidget({ distribution }: { distribution: WeeklyHrDistribution | null }) {
  const enduranceRatio = distribution?.endurance_ratio ?? 0;
  const qualityRatio = distribution?.quality_ratio ?? 0;
  const tips =
    distribution?.tips ??
    "Endurance: jusqu'a 80% FCM. Zone grise: >80-82% hors qualite. Qualite: 83-87% coefficient 0.5, puis 88% et plus coefficient 1.";

  return (
    <aside className="quality-widget" aria-label="Ratio Endurance Qualite" title={tips}>
      <div className="quality-header">
        <h2>Endurance / Qualite</h2>
        <span>cible 90 / 10</span>
      </div>
      <div className="quality-layout">
        <div className="quality-main">
          <div className="quality-ratio">
            <strong>{enduranceRatio.toFixed(0)}%</strong>
            <span>{qualityRatio.toFixed(0)}%</span>
          </div>
          <div className="quality-bar" aria-hidden="true">
            <div className="quality-bar-endurance" style={{ width: `${Math.min(100, enduranceRatio)}%` }} />
            <div className="quality-bar-quality" style={{ width: `${Math.min(100, qualityRatio)}%` }} />
          </div>
          <p className="quality-tips">tips</p>
          <div className="quality-times">
            <div>
              <span>Endurance</span>
              <strong>{formatDuration(distribution?.endurance_seconds ?? null)}</strong>
            </div>
            <div>
              <span>Qualite ponderee</span>
              <strong>{formatDuration(distribution?.quality_weighted_seconds ?? null)}</strong>
            </div>
          </div>
        </div>
        <ul className="zone-list">
          {(distribution?.zones ?? []).map((zone) => (
            <li key={zone.key}>
              <span className="zone-line" style={{ backgroundColor: zone.color }} />
              <div>
                <strong>{zone.label}</strong>
                <span>{zone.range}</span>
              </div>
              <em>{formatDuration(zone.seconds)}</em>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

function EditableSelect({
  value,
  options,
  onChange,
  onAdd,
}: {
  value: string | null;
  options: string[];
  onChange: (value: string | null) => void;
  onAdd: () => void;
}) {
  return (
    <div className="editable-select" onClick={(event) => event.stopPropagation()}>
      <select value={value ?? ""} onChange={(event) => onChange(event.currentTarget.value || null)}>
        <option value="">-</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <button type="button" onClick={onAdd} title="Ajouter une valeur">
        +
      </button>
    </div>
  );
}

function CycleSelect({
  appConfig,
  value,
  onChange,
}: {
  appConfig: AppConfig | null;
  value: string | null;
  onChange: (value: string | null) => void;
}) {
  return (
    <select
      className="cycle-select"
      onChange={(event) => onChange(event.currentTarget.value || null)}
      onClick={(event) => event.stopPropagation()}
      title={value ?? ""}
      value={value ?? ""}
    >
      <option value="">-</option>
      {(appConfig?.cycles ?? []).map((cycle) => (
        <option key={cycle.value} value={cycle.value}>
          {cycle.abbreviation}
        </option>
      ))}
    </select>
  );
}

function DistanceCell({
  activity,
  isEditing,
  onEdit,
  onSave,
}: {
  activity: Activity;
  isEditing: boolean;
  onEdit: () => void;
  onSave: (distanceKm: number) => void;
}) {
  if (isEditing) {
    return (
      <input
        autoFocus
        className="distance-input"
        type="number"
        min="0"
        step="0.01"
        defaultValue={activity.total_distance == null ? "" : (activity.total_distance / 1000).toFixed(2)}
        onClick={(event) => event.stopPropagation()}
        onBlur={(event) => {
          const distanceKm = Number.parseFloat(event.currentTarget.value);
          if (Number.isFinite(distanceKm)) onSave(distanceKm);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
    );
  }

  return (
    <button className="distance-display" type="button" onDoubleClick={onEdit} onClick={(event) => event.stopPropagation()}>
      <span>{formatDistance(activity.total_distance)}</span>
      {activity.distance_manually_edited ? <sup>*</sup> : null}
    </button>
  );
}

function ConfigPage({
  appConfig,
  onAddOption,
  onDeleteOption,
  onRefresh,
  onUpdateConfig,
}: {
  appConfig: AppConfig | null;
  onAddOption: (category: "session_type" | "route_location" | "shoe_type" | "cycle") => Promise<void>;
  onDeleteOption: (category: "session_type" | "route_location" | "shoe_type" | "cycle", value: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  onUpdateConfig: (
    payload: Partial<Pick<AppConfig, "default_ftp" | "default_max_hr" | "default_shoe_type" | "default_cycle">>,
  ) => Promise<void>;
}) {
  return (
    <section className="config-page">
      <div className="panel config-panel">
        <div className="panel-header">
          <h2>Configuration</h2>
          <button className="icon-button" type="button" onClick={() => void onRefresh()} title="Rafraichir">
            <RefreshCw size={17} />
          </button>
        </div>

        <div className="config-grid">
          <label>
            <span>FTP par defaut</span>
            <input
              type="number"
              min="1"
              max="2000"
              defaultValue={appConfig?.default_ftp ?? 221}
              onBlur={(event) => {
                const value = Number.parseInt(event.currentTarget.value, 10);
                if (Number.isFinite(value)) void onUpdateConfig({ default_ftp: value });
              }}
            />
          </label>
          <label>
            <span>FCmax</span>
            <input
              type="number"
              min="1"
              max="250"
              defaultValue={appConfig?.default_max_hr ?? 176}
              onBlur={(event) => {
                const value = Number.parseInt(event.currentTarget.value, 10);
                if (Number.isFinite(value)) void onUpdateConfig({ default_max_hr: value });
              }}
            />
          </label>
          <label>
            <span>Chaussures par defaut</span>
            <select
              value={appConfig?.default_shoe_type ?? ""}
              onChange={(event) => void onUpdateConfig({ default_shoe_type: event.currentTarget.value })}
            >
              <option value="">-</option>
              {(appConfig?.shoe_types ?? []).map((shoe) => (
                <option key={shoe} value={shoe}>
                  {shoe}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Cycle en cours</span>
            <select
              value={appConfig?.default_cycle ?? ""}
              onChange={(event) => void onUpdateConfig({ default_cycle: event.currentTarget.value })}
            >
              <option value="">-</option>
              {(appConfig?.cycles ?? []).map((cycle) => (
                <option key={cycle.value} value={cycle.value}>
                  {cycle.value}
                </option>
              ))}
            </select>
            <small className="cycle-current-abbr">
              {appConfig?.default_cycle ?? "-"} / {cycleAbbreviation(appConfig, appConfig?.default_cycle)}
            </small>
          </label>
        </div>
      </div>

      <OptionPanel
        title="Types de seance"
        values={appConfig?.session_types ?? []}
        onAdd={() => void onAddOption("session_type")}
        onDelete={(value) => void onDeleteOption("session_type", value)}
      />
      <OptionPanel
        title="Lieux / parcours"
        values={appConfig?.route_locations ?? []}
        onAdd={() => void onAddOption("route_location")}
        onDelete={(value) => void onDeleteOption("route_location", value)}
      />
      <OptionPanel
        title="Chaussures"
        values={appConfig?.shoe_types ?? []}
        onAdd={() => void onAddOption("shoe_type")}
        onDelete={(value) => void onDeleteOption("shoe_type", value)}
      />
      <CycleOptionPanel
        title="Cycles"
        values={appConfig?.cycles ?? []}
        onAdd={() => void onAddOption("cycle")}
        onDelete={(value) => void onDeleteOption("cycle", value)}
      />
    </section>
  );
}

function OptionPanel({
  title,
  values,
  onAdd,
  onDelete,
}: {
  title: string;
  values: string[];
  onAdd: () => void;
  onDelete: (value: string) => void;
}) {
  return (
    <div className="panel config-panel">
      <div className="panel-header">
        <h2>{title}</h2>
        <button className="add-button" type="button" onClick={onAdd}>
          Ajouter
        </button>
      </div>
      <ul className="option-list">
        {values.map((value) => (
          <li key={value}>
            <span>{value}</span>
            <button className="delete-option-button" type="button" onClick={() => onDelete(value)} title="Supprimer">
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CycleOptionPanel({
  title,
  values,
  onAdd,
  onDelete,
}: {
  title: string;
  values: AppConfig["cycles"];
  onAdd: () => void;
  onDelete: (value: string) => void;
}) {
  return (
    <div className="panel config-panel">
      <div className="panel-header">
        <h2>{title}</h2>
        <button className="add-button" type="button" onClick={onAdd}>
          Ajouter
        </button>
      </div>
      <ul className="option-list">
        {values.map((cycle) => (
          <li key={cycle.value}>
            <strong>{cycle.abbreviation}</strong>
            <span>{cycle.value}</span>
            <button className="delete-option-button" type="button" onClick={() => onDelete(cycle.value)} title="Supprimer">
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CalendarPage({ calendar }: { calendar: TrainingCalendar | null }) {
  if (!calendar) {
    return (
      <section className="calendar-page">
        <p className="empty-state">Chargement du calendrier...</p>
      </section>
    );
  }

  return (
    <section className="calendar-page">
      <div className="calendar-title">
        <div>
          <h2>Calendrier de charge</h2>
          <p>Semaines a venir, cible Fitness et TSS necessaire.</p>
        </div>
        <CalendarDays size={22} />
      </div>
      <div className="calendar-grid">
        {calendar.weeks.map((week) => (
          <CalendarWeekCard
            key={`${week.start_date}-${week.end_date}`}
            fatigueDays={calendar.fatigue_days}
            fitnessDays={calendar.fitness_days}
            week={week}
          />
        ))}
      </div>
    </section>
  );
}

function CalendarWeekCard({
  week,
  fitnessDays,
  fatigueDays,
}: {
  week: TrainingCalendar["weeks"][number];
  fitnessDays: number;
  fatigueDays: number;
}) {
  const [targetFitness, setTargetFitness] = useState(week.target_fitness);
  const projection = useMemo(
    () => calculateWeekProjection(week.start_fitness, week.start_fatigue, targetFitness, fitnessDays, fatigueDays),
    [fatigueDays, fitnessDays, targetFitness, week.start_fatigue, week.start_fitness],
  );
  const maxTss = Math.max(100, projection.requiredTss, week.actual_tss);

  return (
    <article className={week.index === 0 ? "calendar-card current" : "calendar-card"}>
      <div className="calendar-card-header">
        <span>S{week.week_number}</span>
        <strong>
          du {formatShortDate(week.start_date)} au {formatShortDate(week.end_date)}
        </strong>
      </div>
      <div className="calendar-target">
        <label>
          <span>Fitness cible</span>
          <input
            type="number"
            step="0.1"
            value={targetFitness}
            onChange={(event) => setTargetFitness(Number.parseFloat(event.currentTarget.value) || 0)}
          />
        </label>
      </div>
      <div className="calendar-bars">
        <div>
          <span>TSS cible</span>
          <div className="calendar-mini-track">
            <i style={{ height: `${Math.max(4, (projection.requiredTss / maxTss) * 100)}%` }} />
          </div>
          <strong>{projection.requiredTss.toFixed(0)}</strong>
        </div>
        <div>
          <span>TSS reel</span>
          <div className="calendar-mini-track muted">
            <i style={{ height: `${Math.max(4, (week.actual_tss / maxTss) * 100)}%` }} />
          </div>
          <strong>{week.actual_tss.toFixed(0)}</strong>
        </div>
      </div>
      <div className="calendar-result">
        <div>
          <span>Fitness</span>
          <strong>{projection.resultingFitness.toFixed(1)}</strong>
        </div>
        <div>
          <span>Fatigue</span>
          <strong>{projection.resultingFatigue.toFixed(1)}</strong>
        </div>
        <div>
          <span>Forme</span>
          <strong>{projection.resultingForm.toFixed(1)}</strong>
        </div>
      </div>
    </article>
  );
}

function FractionsPage({ fractions }: { fractions: TrainingFractions | null }) {
  if (!fractions) {
    return (
      <section className="fractions-page">
        <p className="empty-state">Chargement des fractions...</p>
      </section>
    );
  }

  return (
    <section className="fractions-page">
      <div className="fractions-title">
        <div>
          <h2>Fractions</h2>
          <p>Type de seance d'abord, puis filtre FC pour seuil/marathon et allure pour VO2.</p>
        </div>
      </div>
      <div className="fraction-groups">
        {fractions.groups.map((group) => (
          <FractionGroupTable key={group.key} group={group} />
        ))}
      </div>
    </section>
  );
}

function FractionGroupTable({ group }: { group: TrainingFractions["groups"][number] }) {
  return (
    <article className="panel fraction-panel">
      <div className="panel-header">
        <h2>{group.title}</h2>
        <span>{group.rows.length} fraction{group.rows.length > 1 ? "s" : ""}</span>
      </div>
      {group.rows.length === 0 ? (
        <p className="empty-state">Aucune fraction detectee.</p>
      ) : (
        <div className="table-scroll fractions-table">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Seance</th>
                <th>Lieu</th>
                <th>Tour</th>
                <th>Distance</th>
                <th>Duree</th>
                <th>Allure</th>
                <th>FC moy.</th>
                <th>FC max</th>
                <th>Puissance</th>
                <th>Puiss. norm.</th>
                <th>EF fraction</th>
                <th>Cadence</th>
                <th>Contact sol</th>
              </tr>
            </thead>
            <tbody>
              {group.rows.map((row) => (
                <tr key={row.lap_id}>
                  <td>{formatDate(row.date)}</td>
                  <td>{row.session_type || "-"}</td>
                  <td>{row.route_location || "-"}</td>
                  <td>{row.lap_index}</td>
                  <td>{formatDistance(row.total_distance)}</td>
                  <td>{formatDuration(row.total_timer_time)}</td>
                  <td>{formatPace(row.avg_speed)}</td>
                  <td>{formatNumber(row.avg_heart_rate, " bpm")}</td>
                  <td>{formatNumber(row.max_heart_rate, " bpm")}</td>
                  <td>{formatNumber(row.avg_power, " W")}</td>
                  <td>{formatNumber(row.normalized_power, " W")}</td>
                  <td>{formatDecimal(row.efficiency_factor, 2)}</td>
                  <td>{formatCadence(row.avg_cadence)}</td>
                  <td>{formatMilliseconds(row.avg_ground_contact_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

function calculateWeekProjection(
  startFitness: number,
  startFatigue: number,
  targetFitness: number,
  fitnessDays: number,
  fatigueDays: number,
) {
  const fitnessDecay = (1 - 1 / fitnessDays) ** 7;
  const dailyTss = Math.max(0, (targetFitness - startFitness * fitnessDecay) / (1 - fitnessDecay));
  const requiredTss = dailyTss * 7;
  let resultingFitness = startFitness;
  let resultingFatigue = startFatigue;

  for (let day = 0; day < 7; day += 1) {
    resultingFitness += (dailyTss - resultingFitness) / fitnessDays;
    resultingFatigue += (dailyTss - resultingFatigue) / fatigueDays;
  }

  return {
    requiredTss,
    resultingFitness,
    resultingFatigue,
    resultingForm: resultingFitness - resultingFatigue,
  };
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
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
