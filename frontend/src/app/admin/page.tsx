"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import Logo from "@/components/Logo";
import { api } from "@/lib/api";

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface HealthIssue {
  type: string;
  severity: "error" | "warning" | "info";
  count: number;
  description: string;
  fix?: string;
}

interface HealthReport {
  status: string;
  issues: HealthIssue[];
  issue_count: number;
  stats: { total_users: number; total_sessions: number; total_sets: number };
}

interface UserSummary {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  onboarding_complete: boolean;
  created_at: string | null;
  division: string | null;
  sex: string | null;
  height_cm: number | null;
  latest_weight_kg: number | null;
  latest_pds: number | null;
  latest_tier: string | null;
  completed_sessions: number;
}

interface UserDetail {
  user: { id: string; username: string; email: string; is_active: boolean; onboarding_complete: boolean };
  profile: { division: string; sex: string; age: number; height_cm: number; competition_date: string | null; training_years: number; days_per_week: number } | null;
  data_counts: { weight_entries: number; total_sessions: number; completed_sessions: number; weekly_checkins: number; pds_entries: number };
  active_program: { name: string; split: string; week: string } | null;
  nutrition: { calories: number; protein_g: number; carbs_g: number; fat_g: number; phase: string } | null;
}

interface FixResult {
  total_fixed: number;
  results: { fix: string; fixed: number; message: string }[];
}

interface CronLogEntry {
  timestamp: string;
  task: string;
  status: string;
  detail: string;
  fixed: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const cls =
    severity === "error"
      ? "bg-red-500/20 text-red-400 border-red-500/30"
      : severity === "warning"
      ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
      : "bg-blue-500/20 text-blue-400 border-blue-500/30";
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded border font-semibold uppercase ${cls}`}>
      {severity}
    </span>
  );
}

function StatBox({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-jungle-deeper rounded-xl p-4 text-center">
      <p className="text-[10px] text-jungle-dim uppercase tracking-wider">{label}</p>
      <p className="text-2xl font-bold text-jungle-accent mt-1">{value}</p>
      {sub && <p className="text-[10px] text-jungle-muted mt-0.5">{sub}</p>}
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function AdminPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserDetail | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [fixing, setFixing] = useState(false);
  const [fixResult, setFixResult] = useState<FixResult | null>(null);
  const [cronLogs, setCronLogs] = useState<CronLogEntry[]>([]);
  const [runningCron, setRunningCron] = useState(false);
  const [tab, setTab] = useState<"health" | "users" | "logs">("health");

  useEffect(() => {
    if (!loading && !user) {
      router.push("/auth/login");
      return;
    }
    if (user && user.username !== "coronado_admin") {
      router.push("/dashboard");
      return;
    }
    if (user) {
      Promise.all([
        api.get<HealthReport>("/admin/health").catch(() => null),
        api.get<{ users: UserSummary[] }>("/admin/users").catch(() => null),
        api.get<{ logs: CronLogEntry[] }>("/admin/cron/logs").catch(() => null),
      ])
        .then(([h, u, l]) => {
          if (h) setHealth(h);
          if (u) setUsers(u.users);
          if (l) setCronLogs(l.logs);
        })
        .finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  const refreshAll = async () => {
    const [h, u, l] = await Promise.all([
      api.get<HealthReport>("/admin/health").catch(() => null),
      api.get<{ users: UserSummary[] }>("/admin/users").catch(() => null),
      api.get<{ logs: CronLogEntry[] }>("/admin/cron/logs").catch(() => null),
    ]);
    if (h) setHealth(h);
    if (u) setUsers(u.users);
    if (l) setCronLogs(l.logs);
  };

  const runFixAll = async () => {
    setFixing(true);
    setFixResult(null);
    try {
      const result = await api.post<FixResult>("/admin/fix/all");
      setFixResult(result);
      await refreshAll();
    } catch { /* */ }
    setFixing(false);
  };

  const runSingleFix = async (endpoint: string) => {
    setFixing(true);
    try {
      await api.post(endpoint);
      await refreshAll();
    } catch { /* */ }
    setFixing(false);
  };

  const runCronManually = async () => {
    setRunningCron(true);
    try {
      await api.post("/admin/cron/run");
      await refreshAll();
    } catch { /* */ }
    setRunningCron(false);
  };

  const loadUserDetail = async (userId: string) => {
    if (selectedUserId === userId) {
      setSelectedUserId(null);
      setSelectedUser(null);
      return;
    }
    setSelectedUserId(userId);
    try {
      const detail = await api.get<UserDetail>(`/admin/users/${userId}/detail`);
      setSelectedUser(detail);
    } catch {
      setSelectedUser(null);
    }
  };

  if (loading || !user) return null;

  return (
    <div className="min-h-screen bg-jungle-dark">
      {/* Admin Header — distinct from athlete UI */}
      <header className="sticky top-0 z-50 bg-red-950/90 backdrop-blur-md border-b border-red-900/50">
        <div className="max-w-5xl mx-auto px-4 flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <Logo size="sm" />
            <div>
              <h1 className="text-sm font-bold text-red-400 uppercase tracking-wider">Admin Panel</h1>
              <p className="text-[10px] text-red-400/50">System Maintenance</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a href="/dashboard" className="text-xs text-jungle-muted hover:text-jungle-accent transition-colors">
              Athlete Dashboard
            </a>
            <button onClick={() => { logout(); router.push("/"); }} className="text-xs text-red-400 hover:text-red-300">
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Tab Switcher */}
        <div className="flex gap-1 bg-jungle-deeper rounded-lg p-0.5">
          {(["health", "users", "logs"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                tab === t
                  ? "bg-red-500/20 text-red-400"
                  : "text-jungle-muted hover:text-jungle-text"
              }`}
            >
              {t === "health" ? "System Health" : t === "users" ? "Users" : "Cron Logs"}
            </button>
          ))}
        </div>

        {/* Loading */}
        {fetching && (
          <div className="flex items-center justify-center py-20 text-jungle-dim">
            <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse mr-2" />
            Loading admin data...
          </div>
        )}

        {/* ═══ HEALTH TAB ═══ */}
        {!fetching && tab === "health" && health && (
          <div className="space-y-6">
            {/* Status Banner */}
            <div
              className={`card border-2 ${
                health.status === "healthy"
                  ? "border-green-500/30 bg-green-500/5"
                  : "border-red-500/30 bg-red-500/5"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-lg ${
                      health.status === "healthy" ? "bg-green-500/20" : "bg-red-500/20"
                    }`}
                  >
                    {health.status === "healthy" ? "+" : "!"}
                  </div>
                  <div>
                    <p className={`text-lg font-bold ${health.status === "healthy" ? "text-green-400" : "text-red-400"}`}>
                      System {health.status === "healthy" ? "Healthy" : "Needs Attention"}
                    </p>
                    <p className="text-xs text-jungle-dim">
                      {health.issue_count === 0 ? "No issues found" : `${health.issue_count} issue${health.issue_count > 1 ? "s" : ""} detected`}
                    </p>
                  </div>
                </div>
                <button
                  onClick={runFixAll}
                  disabled={fixing || health.issue_count === 0}
                  className="px-4 py-2 rounded-xl text-sm font-bold transition-all disabled:opacity-30 bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 active:scale-95"
                >
                  {fixing ? "Fixing..." : "Fix All"}
                </button>
              </div>
            </div>

            {/* Fix Results */}
            {fixResult && (
              <div className="card border-green-500/30 bg-green-500/5 space-y-2">
                <p className="text-sm font-semibold text-green-400">
                  Fixed {fixResult.total_fixed} issue{fixResult.total_fixed !== 1 ? "s" : ""}
                </p>
                {fixResult.results.map((r, i) => (
                  <p key={i} className="text-xs text-jungle-muted">
                    {r.fix}: {r.message}
                  </p>
                ))}
              </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Users" value={health.stats.total_users} />
              <StatBox label="Sessions" value={health.stats.total_sessions.toLocaleString()} />
              <StatBox label="Sets Logged" value={health.stats.total_sets.toLocaleString()} />
            </div>

            {/* Issues */}
            {health.issues.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">Issues</h3>
                {health.issues.map((issue, i) => (
                  <div key={i} className="card flex items-start gap-3">
                    <SeverityBadge severity={issue.severity} />
                    <div className="flex-1">
                      <p className="text-sm text-jungle-text">{issue.description}</p>
                      <p className="text-[10px] text-jungle-dim mt-0.5">{issue.type} | count: {issue.count}</p>
                    </div>
                    {issue.fix && (
                      <button
                        onClick={() => runSingleFix(issue.fix!.replace("POST ", ""))}
                        disabled={fixing}
                        className="text-[10px] px-2 py-1 rounded-lg border border-jungle-border text-jungle-muted hover:border-red-500/50 hover:text-red-400 transition-colors disabled:opacity-50"
                      >
                        Fix
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {health.issues.length === 0 && (
              <div className="card text-center py-8 border-green-500/20">
                <p className="text-green-400 text-lg font-medium">All Clear</p>
                <p className="text-jungle-dim text-sm mt-1">No issues found. System is running optimally.</p>
              </div>
            )}
          </div>
        )}

        {/* ═══ USERS TAB ═══ */}
        {!fetching && tab === "users" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                All Users ({users.length})
              </h3>
            </div>

            {users.map((u) => (
              <div key={u.id}>
                <button
                  onClick={() => loadUserDetail(u.id)}
                  className={`w-full text-left card transition-all ${
                    selectedUserId === u.id ? "border-jungle-accent" : "hover:border-jungle-border-hover"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {/* Avatar */}
                    <div className="w-10 h-10 rounded-full bg-jungle-deeper flex items-center justify-center text-jungle-accent font-bold shrink-0">
                      {u.username.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold truncate">{u.username}</span>
                        {u.onboarding_complete ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 border border-green-500/30">Active</span>
                        ) : (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">Onboarding</span>
                        )}
                        {u.username === "coronado_admin" && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">Admin</span>
                        )}
                      </div>
                      <p className="text-[10px] text-jungle-dim">{u.email}</p>
                    </div>
                    <div className="text-right shrink-0">
                      {u.division && (
                        <p className="text-[10px] text-jungle-muted capitalize">{u.division.replace(/_/g, " ")}</p>
                      )}
                      {u.latest_pds && (
                        <p className="text-xs text-jungle-accent font-bold">PDS {u.latest_pds.toFixed(0)}</p>
                      )}
                      <p className="text-[10px] text-jungle-dim">{u.completed_sessions} sessions</p>
                    </div>
                  </div>
                </button>

                {/* Expanded Detail */}
                {selectedUserId === u.id && selectedUser && (
                  <div className="card mt-1 border-jungle-accent/30 space-y-4">
                    {/* Profile */}
                    {selectedUser.profile && (
                      <div>
                        <p className="text-[10px] text-jungle-dim uppercase tracking-wider mb-2">Profile</p>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                          <div className="bg-jungle-deeper rounded-lg p-2 text-center">
                            <p className="text-[9px] text-jungle-dim">Division</p>
                            <p className="text-xs font-medium capitalize">{selectedUser.profile.division?.replace(/_/g, " ")}</p>
                          </div>
                          <div className="bg-jungle-deeper rounded-lg p-2 text-center">
                            <p className="text-[9px] text-jungle-dim">Height</p>
                            <p className="text-xs font-medium">{selectedUser.profile.height_cm}cm</p>
                          </div>
                          <div className="bg-jungle-deeper rounded-lg p-2 text-center">
                            <p className="text-[9px] text-jungle-dim">Age</p>
                            <p className="text-xs font-medium">{selectedUser.profile.age || "—"}</p>
                          </div>
                          <div className="bg-jungle-deeper rounded-lg p-2 text-center">
                            <p className="text-[9px] text-jungle-dim">Experience</p>
                            <p className="text-xs font-medium">{selectedUser.profile.training_years}yr</p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Data Counts */}
                    <div>
                      <p className="text-[10px] text-jungle-dim uppercase tracking-wider mb-2">Data</p>
                      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                        {Object.entries(selectedUser.data_counts).map(([k, v]) => (
                          <div key={k} className="bg-jungle-deeper rounded-lg p-2 text-center">
                            <p className="text-[9px] text-jungle-dim">{k.replace(/_/g, " ")}</p>
                            <p className="text-sm font-bold text-jungle-accent">{v}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Active Program */}
                    {selectedUser.active_program && (
                      <div className="bg-jungle-deeper rounded-lg p-3">
                        <p className="text-[10px] text-jungle-dim uppercase tracking-wider mb-1">Active Program</p>
                        <p className="text-sm font-semibold">{selectedUser.active_program.name}</p>
                        <p className="text-[10px] text-jungle-muted">
                          {selectedUser.active_program.split} | Week {selectedUser.active_program.week}
                        </p>
                      </div>
                    )}

                    {/* Nutrition */}
                    {selectedUser.nutrition && (
                      <div className="bg-jungle-deeper rounded-lg p-3">
                        <p className="text-[10px] text-jungle-dim uppercase tracking-wider mb-1">Nutrition Rx</p>
                        <div className="flex gap-4 text-xs">
                          <span className="text-jungle-accent font-bold">{Math.round(selectedUser.nutrition.calories)} kcal</span>
                          <span className="text-blue-400">P{Math.round(selectedUser.nutrition.protein_g)}g</span>
                          <span className="text-amber-400">C{Math.round(selectedUser.nutrition.carbs_g)}g</span>
                          <span className="text-red-400">F{Math.round(selectedUser.nutrition.fat_g)}g</span>
                          <span className="text-jungle-muted capitalize">{selectedUser.nutrition.phase}</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ═══ CRON LOGS TAB ═══ */}
        {!fetching && tab === "logs" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                Maintenance Logs ({cronLogs.length})
              </h3>
              <button
                onClick={runCronManually}
                disabled={runningCron}
                className="px-4 py-2 rounded-xl text-sm font-bold transition-all disabled:opacity-50 bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 active:scale-95"
              >
                {runningCron ? "Running..." : "Run Now"}
              </button>
            </div>

            {cronLogs.length === 0 ? (
              <div className="card text-center py-8">
                <p className="text-jungle-muted">No cron logs yet</p>
                <p className="text-jungle-dim text-sm mt-1">Maintenance runs automatically every 6 hours, or click &quot;Run Now&quot;</p>
              </div>
            ) : (
              <div className="space-y-1">
                {cronLogs.map((log, i) => {
                  const statusColor =
                    log.status === "error" ? "text-red-400" :
                    log.status === "warning" ? "text-yellow-400" :
                    log.status === "fixed" ? "text-green-400" :
                    log.status === "complete" ? "text-jungle-accent" :
                    "text-jungle-muted";
                  const bgColor =
                    log.status === "error" ? "border-red-500/20" :
                    log.status === "fixed" ? "border-green-500/20" :
                    "border-jungle-border/50";
                  const time = new Date(log.timestamp).toLocaleString("en-US", {
                    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
                  });

                  return (
                    <div key={i} className={`flex items-start gap-3 px-3 py-2 rounded-lg border bg-jungle-card/50 ${bgColor}`}>
                      <span className="text-[9px] text-jungle-dim font-mono w-28 shrink-0 pt-0.5">{time}</span>
                      <span className={`text-[10px] font-bold uppercase w-14 shrink-0 pt-0.5 ${statusColor}`}>{log.status}</span>
                      <div className="flex-1 min-w-0">
                        <span className="text-xs text-jungle-text">{log.detail}</span>
                        <span className="text-[9px] text-jungle-dim ml-2">{log.task}</span>
                      </div>
                      {log.fixed > 0 && (
                        <span className="text-[10px] text-green-400 font-bold shrink-0">+{log.fixed}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
