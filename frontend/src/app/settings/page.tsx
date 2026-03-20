"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import { api } from "@/lib/api";

interface Profile {
  sex: string;
  age: number | null;
  height_cm: number;
  division: string;
  competition_date: string | null;
  training_experience_years: number;
  wrist_circumference_cm: number | null;
  ankle_circumference_cm: number | null;
  manual_body_fat_pct: number | null;
  preferences: {
    training_days_per_week?: number;
    preferred_split?: string;
    meal_count?: number;
    dietary_restrictions?: string[];
    display_name?: string;
    cardio_machine?: string;
    cut_threshold_bf_pct?: number;
  };
}

interface ShareTokenResponse {
  share_token: string;
  expires_at: string;
}

const DIVISIONS = [
  { value: "mens_open", label: "Men's Open" },
  { value: "classic_physique", label: "Men's Classic Physique" },
  { value: "mens_physique", label: "Men's Physique" },
  { value: "womens_bikini", label: "Women's Bikini" },
  { value: "womens_figure", label: "Women's Figure" },
  { value: "womens_physique", label: "Women's Physique" },
];

const SPLITS = [
  { value: "auto", label: "Auto — Algorithmic Split" },
  { value: "ppl", label: "Push / Pull / Legs" },
  { value: "upper_lower", label: "Upper / Lower" },
  { value: "full_body", label: "Full Body" },
  { value: "bro_split", label: "Bro Split (1 muscle/day)" },
];

export default function SettingsPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [activeSection, setActiveSection] = useState<"profile" | "training" | "account" | "notifications">("profile");

  // Editable fields
  const [age, setAge] = useState("");
  const [division, setDivision] = useState("mens_open");
  const [compDate, setCompDate] = useState("");
  const [expYears, setExpYears] = useState("");
  const [wrist, setWrist] = useState("");
  const [ankle, setAnkle] = useState("");
  const [manualBF, setManualBF] = useState("");
  const [cutThreshold, setCutThreshold] = useState("");
  const [daysPerWeek, setDaysPerWeek] = useState("4");
  const [split, setSplit] = useState("ppl");
  const [mealCount, setMealCount] = useState("4");
  const [displayName, setDisplayName] = useState("");
  const [cardioMachine, setCardioMachine] = useState("treadmill");

  // Notifications state
  const [notifyCheckin, setNotifyCheckin] = useState(false);
  const [notifyTraining, setNotifyTraining] = useState(false);
  const [notifyMeals, setNotifyMeals] = useState(false);
  const [notifPermission, setNotifPermission] = useState<NotificationPermission | "unavailable">("default");
  const [enablingNotif, setEnablingNotif] = useState(false);

  // Export state
  const [exporting, setExporting] = useState(false);

  // Coach share link state
  const [shareToken, setShareToken] = useState("");
  const [shareExpiry, setShareExpiry] = useState("");
  const [generatingShare, setGeneratingShare] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<Profile>("/onboarding/profile")
        .then((p) => {
          setProfile(p);
          setAge(p.age?.toString() ?? "");
          setDivision(p.division);
          setCompDate(p.competition_date ?? "");
          setExpYears(p.training_experience_years.toString());
          setWrist(p.wrist_circumference_cm?.toString() ?? "");
          setAnkle(p.ankle_circumference_cm?.toString() ?? "");
          setManualBF(p.manual_body_fat_pct?.toString() ?? "");
          setCutThreshold(p.preferences?.cut_threshold_bf_pct?.toString() ?? "");
          setDaysPerWeek(p.preferences?.training_days_per_week?.toString() ?? "4");
          setSplit(p.preferences?.preferred_split ?? "ppl");
          setMealCount(p.preferences?.meal_count?.toString() ?? "4");
          setDisplayName(p.preferences?.display_name ?? "");
          setCardioMachine(p.preferences?.cardio_machine ?? "treadmill");
        })
        .catch(() => {});

      // Load notification preferences from localStorage
      if (typeof window !== "undefined") {
        setNotifyCheckin(localStorage.getItem("notify_checkin") === "true");
        setNotifyTraining(localStorage.getItem("notify_training") === "true");
        setNotifyMeals(localStorage.getItem("notify_meals") === "true");
        if ("Notification" in window) {
          setNotifPermission(Notification.permission);
        } else {
          setNotifPermission("unavailable");
        }
      }
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  const saveProfile = async () => {
    setSaving(true);
    try {
      await api.patch("/onboarding/profile", {
        age: age ? parseInt(age) : null,
        division,
        competition_date: compDate || null,
        training_experience_years: expYears ? parseInt(expYears) : 0,
        wrist_circumference_cm: wrist ? parseFloat(wrist) : null,
        ankle_circumference_cm: ankle ? parseFloat(ankle) : null,
        manual_body_fat_pct: manualBF ? parseFloat(manualBF) : null,
        preferences: {
          preferred_split: split,
          training_days_per_week: parseInt(daysPerWeek),
          meal_count: parseInt(mealCount),
          display_name: displayName,
          cardio_machine: cardioMachine,
          cut_threshold_bf_pct: cutThreshold ? parseFloat(cutThreshold) : null,
        },
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      //
    } finally {
      setSaving(false);
    }
  };

  const handleEnableNotifications = async () => {
    if (!("Notification" in window)) return;
    setEnablingNotif(true);
    try {
      const perm = await Notification.requestPermission();
      setNotifPermission(perm);
      if (perm === "granted") {
        if (notifyCheckin) localStorage.setItem("notify_checkin", "true");
        else localStorage.removeItem("notify_checkin");
        if (notifyTraining) localStorage.setItem("notify_training", "true");
        else localStorage.removeItem("notify_training");
        if (notifyMeals) localStorage.setItem("notify_meals", "true");
        else localStorage.removeItem("notify_meals");
      }
    } finally {
      setEnablingNotif(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${baseUrl}/export/report`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "coronado-progress-report.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      //
    } finally {
      setExporting(false);
    }
  };

  const handleGenerateShareLink = async () => {
    setGeneratingShare(true);
    try {
      const res = await api.post<ShareTokenResponse>("/auth/share-token");
      setShareToken(res.share_token);
      setShareExpiry(res.expires_at);
    } catch {
      //
    } finally {
      setGeneratingShare(false);
    }
  };

  const shareUrl = shareToken
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/share/${shareToken}`
    : "";

  const handleCopyShare = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2000);
    } catch {
      //
    }
  };

  const permissionBadge = () => {
    if (notifPermission === "unavailable") return null;
    const map: Record<string, { label: string; cls: string }> = {
      granted: { label: "Allowed", cls: "bg-green-500/20 text-green-400" },
      denied: { label: "Blocked", cls: "bg-red-500/20 text-red-400" },
      default: { label: "Not set", cls: "bg-jungle-border/40 text-jungle-muted" },
    };
    const info = map[notifPermission] ?? map["default"];
    return (
      <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${info.cls}`}>
        {info.label}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-jungle-dark">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />

      <main className="container-app py-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">
                <span className="text-jungle-accent">Settings</span>
              </h1>
              <p className="text-jungle-muted text-sm mt-1">Profile & training preferences</p>
            </div>
            <a href="/dashboard" className="btn-secondary text-sm px-3 py-2">← Dashboard</a>
          </div>

          {/* Section tabs */}
          <div className="flex gap-1 bg-jungle-deeper border border-jungle-border rounded-xl p-1 flex-wrap">
            {(["profile", "training", "account", "notifications"] as const).map((sec) => (
              <button
                key={sec}
                onClick={() => setActiveSection(sec)}
                className={`flex-1 min-w-[70px] py-2 text-xs sm:text-sm rounded-lg transition-colors capitalize ${
                  activeSection === sec
                    ? "bg-jungle-accent text-jungle-dark font-semibold"
                    : "text-jungle-muted hover:text-jungle-accent"
                }`}
              >
                {sec}
              </button>
            ))}
          </div>

          {/* Profile Section */}
          {activeSection === "profile" && (
            <div className="card space-y-4">
              <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                Competitor Profile
              </h2>

              {profile && (
                <div className="bg-jungle-deeper rounded-lg p-3 text-xs text-jungle-dim grid grid-cols-2 gap-2">
                  <span>Height: <span className="text-jungle-muted">{profile.height_cm}cm</span></span>
                  <span>Sex: <span className="text-jungle-muted capitalize">{profile.sex}</span></span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label-field">Age</label>
                  <input
                    type="number"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. 28"
                    min={16}
                    max={70}
                  />
                </div>
                <div>
                  <label className="label-field">Training Experience (years)</label>
                  <input
                    type="number"
                    value={expYears}
                    onChange={(e) => setExpYears(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. 5"
                    min={0}
                    max={40}
                  />
                </div>
              </div>

              <div>
                <label className="label-field">Division</label>
                <select
                  value={division}
                  onChange={(e) => setDivision(e.target.value)}
                  className="input-field mt-1"
                >
                  {DIVISIONS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label-field">Competition Date</label>
                <input
                  type="date"
                  value={compDate}
                  onChange={(e) => setCompDate(e.target.value)}
                  className="input-field mt-1"
                />
                {compDate && (
                  <p className="text-xs text-jungle-dim mt-1">
                    {Math.max(0, Math.round((new Date(compDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))} days out
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label-field">Wrist Circumference (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={wrist}
                    onChange={(e) => setWrist(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. 17.5"
                  />
                  <p className="text-[10px] text-jungle-dim mt-1">Structural anchor measurement</p>
                </div>
                <div>
                  <label className="label-field">Ankle Circumference (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={ankle}
                    onChange={(e) => setAnkle(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. 22.0"
                  />
                  <p className="text-[10px] text-jungle-dim mt-1">Structural anchor measurement</p>
                </div>
              </div>

              <div className="pt-2 mt-2 border-t border-jungle-border" />
              <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                Body Composition Analysis Control
              </h2>
              <div className="grid grid-cols-2 gap-4 mt-2">
                <div>
                  <label className="label-field">Manual Body Fat %</label>
                  <input
                    type="number"
                    step="0.1"
                    value={manualBF}
                    onChange={(e) => setManualBF(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. 15.0"
                  />
                  <p className="text-[10px] text-jungle-dim mt-1">Overrides caliper/tape estimates globally</p>
                </div>
                <div>
                  <label className="label-field">Cut Threshold BF %</label>
                  <input
                    type="number"
                    step="0.1"
                    value={cutThreshold}
                    onChange={(e) => setCutThreshold(e.target.value)}
                    className="input-field mt-1"
                    placeholder="e.g. 18.0"
                  />
                  <p className="text-[10px] text-jungle-dim mt-1">Max body fat before a &apos;cut&apos; is recommended</p>
                </div>
              </div>
            </div>
          )}

          {/* Training Section */}
          {activeSection === "training" && (
            <div className="card space-y-4">
              <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                Training Preferences
              </h2>

              <div>
                <label className="label-field">Training Days per Week</label>
                <div className="grid grid-cols-5 gap-2 mt-2">
                  {[2, 3, 4, 5, 6].map((d) => (
                    <button
                      key={d}
                      onClick={() => setDaysPerWeek(d.toString())}
                      className={`py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                        daysPerWeek === d.toString()
                          ? "bg-jungle-accent text-jungle-dark"
                          : "bg-jungle-deeper border border-jungle-border hover:border-jungle-accent text-jungle-muted"
                      }`}
                    >
                      {d}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-jungle-dim mt-2">
                  {daysPerWeek === "2" && "Minimum frequency — full body or upper/lower recommended"}
                  {daysPerWeek === "3" && "Good for beginners — Push/Pull/Legs or full body"}
                  {daysPerWeek === "4" && "Optimal for most — Upper/Lower or PPL rotation"}
                  {daysPerWeek === "5" && "High frequency — PPL + arm/shoulder focus day"}
                  {daysPerWeek === "6" && "Advanced — full PPL with lagging muscle specialization"}
                </p>
              </div>

              <div>
                <label className="label-field">Preferred Split</label>
                <div className="space-y-2 mt-2">
                  {SPLITS.map((s) => (
                    <button
                      key={s.value}
                      onClick={() => setSplit(s.value)}
                      className={`w-full flex items-center gap-3 py-3 px-4 rounded-lg text-sm text-left transition-colors border ${
                        split === s.value
                          ? "border-jungle-accent bg-jungle-accent/10 text-jungle-accent"
                          : "border-jungle-border bg-jungle-deeper text-jungle-muted hover:border-jungle-accent/50"
                      }`}
                    >
                      <span
                        className={`w-3 h-3 rounded-full border-2 shrink-0 ${
                          split === s.value ? "border-jungle-accent bg-jungle-accent" : "border-jungle-border"
                        }`}
                      />
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="label-field">Display Name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="input-field mt-1"
                  placeholder="e.g. Alex"
                />
                <p className="text-[10px] text-jungle-dim mt-1">Shown on the dashboard greeting</p>
              </div>

              <div>
                <label className="label-field">Cardio Machine</label>
                <select
                  value={cardioMachine}
                  onChange={(e) => setCardioMachine(e.target.value)}
                  className="input-field mt-1"
                >
                  <option value="treadmill">Treadmill</option>
                  <option value="stairmaster">StairMaster</option>
                </select>
              </div>
            </div>
          )}

          {/* Account Section */}
          {activeSection === "account" && (
            <div className="space-y-4">
              <div className="card space-y-4">
                <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                  Nutrition Preferences
                </h2>

                <div>
                  <label className="label-field">Daily Meals</label>
                  <div className="grid grid-cols-6 gap-2 mt-2">
                    {[2, 3, 4, 5, 6, 7].map((n) => (
                      <button
                        key={n}
                        onClick={() => setMealCount(n.toString())}
                        className={`py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                          mealCount === n.toString()
                            ? "bg-jungle-accent text-jungle-dark"
                            : "bg-jungle-deeper border border-jungle-border hover:border-jungle-accent text-jungle-muted"
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="card">
                <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider mb-3">
                  Account
                </h2>
                <div className="space-y-2">
                  <div className="flex justify-between items-center py-2 text-sm border-b border-jungle-border">
                    <span className="text-jungle-muted">Username</span>
                    <span className="text-jungle-text font-medium">{user.username}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 text-sm">
                    <span className="text-jungle-muted">Email</span>
                    <span className="text-jungle-text font-medium">{user.email}</span>
                  </div>
                </div>
                <button
                  onClick={() => { logout(); router.push("/"); }}
                  className="mt-4 w-full py-2.5 text-sm text-red-400 border border-red-500/30 rounded-lg hover:bg-red-500/10 transition-colors"
                >
                  Log out
                </button>
              </div>
            </div>
          )}

          {/* Notifications Section */}
          {activeSection === "notifications" && (
            <div className="space-y-4">
              {/* Reminders */}
              <div className="card space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                    Reminders
                  </h2>
                  {permissionBadge()}
                </div>

                {notifPermission === "denied" && (
                  <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    Notifications are blocked — enable in browser settings
                  </p>
                )}

                <div className="space-y-3">
                  <Toggle
                    label="Check-in reminder (Sunday mornings)"
                    checked={notifyCheckin}
                    onChange={(v) => {
                      setNotifyCheckin(v);
                      if (notifPermission === "granted") {
                        if (v) localStorage.setItem("notify_checkin", "true");
                        else localStorage.removeItem("notify_checkin");
                      }
                    }}
                  />
                  <Toggle
                    label="Training day reminder"
                    checked={notifyTraining}
                    onChange={(v) => {
                      setNotifyTraining(v);
                      if (notifPermission === "granted") {
                        if (v) localStorage.setItem("notify_training", "true");
                        else localStorage.removeItem("notify_training");
                      }
                    }}
                  />
                  <Toggle
                    label="Meal logging reminder (8 PM)"
                    checked={notifyMeals}
                    onChange={(v) => {
                      setNotifyMeals(v);
                      if (notifPermission === "granted") {
                        if (v) localStorage.setItem("notify_meals", "true");
                        else localStorage.removeItem("notify_meals");
                      }
                    }}
                  />
                </div>

                {notifPermission !== "granted" && notifPermission !== "unavailable" && (
                  <button
                    onClick={handleEnableNotifications}
                    disabled={enablingNotif || notifPermission === "denied"}
                    className="btn-primary w-full disabled:opacity-50"
                  >
                    {enablingNotif ? "Requesting..." : "Enable Notifications"}
                  </button>
                )}
                {notifPermission === "unavailable" && (
                  <p className="text-xs text-jungle-dim">Browser notifications are not supported.</p>
                )}
              </div>

              {/* Data Export */}
              <div className="card space-y-3">
                <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                  Data Export
                </h2>
                <p className="text-xs text-jungle-dim">
                  Downloads a PDF summary of your current PDS score, measurements, and training program.
                </p>
                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="btn-primary w-full disabled:opacity-50"
                >
                  {exporting ? "Downloading..." : "Download Progress Report"}
                </button>
              </div>

              {/* Share with Coach */}
              <div className="card space-y-3">
                <h2 className="text-sm font-semibold text-jungle-muted uppercase tracking-wider">
                  Share with Coach
                </h2>
                <p className="text-xs text-jungle-dim">
                  Generate a temporary link that gives your coach read-only access to your progress data.
                </p>

                {!shareToken ? (
                  <button
                    onClick={handleGenerateShareLink}
                    disabled={generatingShare}
                    className="btn-primary w-full disabled:opacity-50"
                  >
                    {generatingShare ? "Generating..." : "Generate Share Link"}
                  </button>
                ) : (
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        readOnly
                        value={shareUrl}
                        className="input-field flex-1 text-xs font-mono"
                        onFocus={(e) => e.target.select()}
                      />
                      <button
                        onClick={handleCopyShare}
                        className="btn-secondary px-3 whitespace-nowrap text-xs"
                      >
                        {shareCopied ? "Copied!" : "Copy"}
                      </button>
                    </div>
                    {shareExpiry && (
                      <p className="text-[10px] text-jungle-dim">
                        Expires {new Date(shareExpiry).toLocaleDateString()}
                      </p>
                    )}
                    <button
                      onClick={() => { setShareToken(""); setShareExpiry(""); }}
                      className="text-xs text-red-400 hover:underline"
                    >
                      Revoke
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Save button (not on account or notifications tab) */}
          {activeSection !== "account" && activeSection !== "notifications" && (
            <button
              onClick={saveProfile}
              disabled={saving}
              className="btn-primary w-full disabled:opacity-50"
            >
              {saved ? "Saved!" : saving ? "Saving..." : "Save Changes"}
            </button>
          )}
        </div>
      </main>

      <div className="md:hidden h-16" />
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-jungle-muted">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${
          checked ? "bg-jungle-accent" : "bg-jungle-border"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}
