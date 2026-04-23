"use client";

/**
 * V3.P10 — Prep Replay / Cycle Archive.
 *
 * Lists every completed PPM improvement cycle with the key readiness
 * metrics at each checkpoint. Click a row to drill into the full cycle
 * detail: macros, training split, volume, limiting factor, focus
 * muscles — everything the engine captured when the cycle closed.
 *
 * The archive becomes more valuable over time: by cycle 4+ the user
 * can compare "in my first cut at 10% I ate X; at the same BF now I
 * eat Y" and learn from their own history.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import NavBar from "@/components/NavBar";
import PageTitle from "@/components/PageTitle";
import ViltrumLoader from "@/components/ViltrumLoader";
import { api } from "@/lib/api";
import type { CycleSummary, CycleDetail } from "@/lib/types";

export default function CycleArchivePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [cycles, setCycles] = useState<CycleSummary[]>([]);
  const [fetching, setFetching] = useState(true);
  const [selected, setSelected] = useState<CycleSummary | null>(null);
  const [detail, setDetail] = useState<CycleDetail | null>(null);
  const [compareWith, setCompareWith] = useState<CycleSummary | null>(null);
  const [compareDetail, setCompareDetail] = useState<CycleDetail | null>(null);

  useEffect(() => {
    if (!loading && !user) { router.push("/auth/login"); return; }
    if (user) {
      api.get<{ cycles: CycleSummary[] }>("/insights/archive/cycles")
        .then((r) => setCycles(r.cycles))
        .catch(() => setCycles([]))
        .finally(() => setFetching(false));
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (selected) {
      api.get<CycleDetail>(`/insights/archive/cycle/${selected.cycle_number}`)
        .then(setDetail)
        .catch(() => setDetail(null));
    } else {
      setDetail(null);
    }
  }, [selected]);

  useEffect(() => {
    if (compareWith) {
      api.get<CycleDetail>(`/insights/archive/cycle/${compareWith.cycle_number}`)
        .then(setCompareDetail)
        .catch(() => setCompareDetail(null));
    } else {
      setCompareDetail(null);
    }
  }, [compareWith]);

  if (loading || !user) return null;

  return (
    <div className="min-h-screen">
      <NavBar username={user.username} onLogout={() => { logout(); router.push("/"); }} />
      <main className="container-app py-6">
        <div className="max-w-4xl mx-auto space-y-5">
          <PageTitle
            text="Cycle Archive"
            actions={
              <a href="/dashboard" className="btn-secondary text-sm px-3 py-2" aria-label="Back">
                ← Dashboard
              </a>
            }
          />

          <p className="body-serif-sm italic text-iron text-sm leading-relaxed">
            Every completed improvement cycle, preserved. The longer you train, the more valuable this gets — by
            cycle 4+ you can compare macros, volume, and readiness across runs and let your own history tell you
            what worked.
          </p>

          {fetching ? (
            <div className="py-20 flex justify-center">
              <ViltrumLoader />
            </div>
          ) : cycles.length === 0 ? (
            <div className="card text-center py-14 space-y-3">
              <p className="h-display-sm">No cycles completed yet.</p>
              <p className="body-serif-sm italic text-iron max-w-md mx-auto">
                Your archive fills in as you complete PPM improvement cycles. Each 14-week cycle lands here with
                full macros, training split, volume allocation, and checkpoint metrics.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.3fr] gap-5">
              {/* Cycle list */}
              <div className="space-y-2">
                <div className="flex items-baseline justify-between px-1">
                  <h3 className="h-card text-obsidian">Completed cycles</h3>
                  <span className="text-[10px] tracking-[0.15em] uppercase text-travertine tabular-nums">
                    {cycles.length}
                  </span>
                </div>
                {cycles.map((c) => {
                  const isSelected = selected?.cycle_number === c.cycle_number;
                  const isCompare = compareWith?.cycle_number === c.cycle_number;
                  return (
                    <button
                      key={c.cycle_number}
                      type="button"
                      onClick={() => {
                        if (!selected) setSelected(c);
                        else if (isSelected) setSelected(null);
                        else if (!compareWith) setCompareWith(c);
                        else if (isCompare) setCompareWith(null);
                        else { setCompareWith(null); setSelected(c); }
                      }}
                      className={`w-full card text-left transition-colors ${
                        isSelected ? "border-adriatic ring-1 ring-adriatic/30"
                          : isCompare ? "border-aureus ring-1 ring-aureus/30"
                          : "hover:border-pumice"
                      }`}
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <div className="flex items-baseline gap-2">
                          <span className="h-card text-obsidian">Cycle {c.cycle_number}</span>
                          {isSelected && <span className="text-[9px] bg-adriatic text-white px-1.5 rounded">A</span>}
                          {isCompare && <span className="text-[9px] bg-aureus text-white px-1.5 rounded">B</span>}
                        </div>
                        <span className="text-[10px] tabular-nums text-travertine">
                          {c.checkpoint_date ?? "—"}
                        </span>
                      </div>
                      <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
                        <div>
                          <div className="text-travertine uppercase tracking-wider text-[9px]">BW</div>
                          <div className="tabular-nums text-iron">{c.body_weight_kg?.toFixed(1) ?? "—"}kg</div>
                        </div>
                        <div>
                          <div className="text-travertine uppercase tracking-wider text-[9px]">BF</div>
                          <div className="tabular-nums text-iron">{c.bf_pct?.toFixed(1) ?? "—"}%</div>
                        </div>
                        <div>
                          <div className="text-travertine uppercase tracking-wider text-[9px]">HQI</div>
                          <div className="tabular-nums text-iron">{c.hqi_score?.toFixed(0) ?? "—"}</div>
                        </div>
                      </div>
                      {c.limiting_factor && (
                        <p className="text-[10px] body-serif-sm italic text-iron mt-2 leading-snug">
                          Limiter: <span className="text-travertine">{c.limiting_factor}</span>
                          {c.cycle_focus && <>  ·  Focus: <span className="text-travertine">{c.cycle_focus}</span></>}
                        </p>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Detail / comparison view */}
              <div className="space-y-3">
                {!selected && (
                  <div className="card text-center py-12 text-sm text-travertine">
                    Select a cycle to see its full snapshot.
                  </div>
                )}
                {selected && detail && (
                  <CycleDetailCard
                    detail={detail}
                    compareDetail={compareDetail}
                    label={compareDetail ? "A" : undefined}
                  />
                )}
                {compareWith && compareDetail && (
                  <CycleDetailCard
                    detail={compareDetail}
                    label="B"
                  />
                )}
                {selected && (
                  <p className="text-[11px] body-serif-sm italic text-iron text-center px-4">
                    {compareWith
                      ? "Click the selected cycle again to deselect, or pick another to swap."
                      : "Tip: click a second cycle to compare side-by-side."}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
      <div className="md:hidden h-16" />
    </div>
  );
}

function CycleDetailCard({
  detail,
  compareDetail,
  label,
}: {
  detail: CycleDetail;
  compareDetail?: CycleDetail | null;
  label?: string;
}) {
  const r = detail.readiness;

  type NumLike = number | null | undefined;
  const Row = ({ name, value, compareValue, unit = "", digits = 1 }: {
    name: string; value: NumLike; compareValue?: NumLike; unit?: string; digits?: number;
  }) => (
    <div className="flex items-baseline justify-between py-1 text-[12px] border-b border-ash last:border-0">
      <span className="text-travertine">{name}</span>
      <div className="flex items-baseline gap-3 tabular-nums">
        <span className="text-obsidian font-medium">
          {value != null ? value.toFixed(digits) : "—"}{unit}
        </span>
        {compareValue != null && value != null && (
          <span className={`text-[10px] ${compareValue < value ? "text-laurel" : compareValue > value ? "text-terracotta" : "text-travertine"}`}>
            Δ {(value - compareValue).toFixed(digits)}
          </span>
        )}
      </div>
    </div>
  );

  const cr = compareDetail?.readiness;

  return (
    <div className="card space-y-3">
      <div className="flex items-baseline justify-between">
        <h3 className="h-card text-obsidian flex items-center gap-2">
          Cycle {detail.cycle_number}
          {label && <span className={`text-[9px] px-1.5 rounded text-white ${label === "A" ? "bg-adriatic" : "bg-aureus"}`}>{label}</span>}
        </h3>
        <span className="text-[10px] tracking-[0.1em] uppercase text-travertine">
          {r.state?.replace(/_/g, " ")}
        </span>
      </div>

      <div>
        <p className="h-section text-travertine mb-1">Readiness metrics</p>
        <Row name="Body Weight"         value={r.bf_pct != null ? detail.body_weight_kg : null} compareValue={compareDetail?.body_weight_kg} unit="kg" />
        <Row name="Body Fat %"           value={r.bf_pct} compareValue={cr?.bf_pct} unit="%" />
        <Row name="FFMI"                 value={r.ffmi} compareValue={cr?.ffmi} digits={1} />
        <Row name="HQI"                  value={r.hqi_score} compareValue={cr?.hqi_score} digits={0} />
        <Row name="Shoulder : Waist"    value={r.shoulder_waist_ratio} compareValue={cr?.shoulder_waist_ratio} digits={2} />
        <Row name="Chest : Waist"       value={r.chest_waist_ratio} compareValue={cr?.chest_waist_ratio} digits={2} />
        <Row name="Arm-Calf-Neck Parity" value={r.arm_calf_neck_parity} compareValue={cr?.arm_calf_neck_parity} unit='"' digits={2} />
        <Row name="Illusion (X-frame)"  value={r.illusion_xframe} compareValue={cr?.illusion_xframe} digits={2} />
        <Row name="Conditioning %"       value={r.conditioning_pct} compareValue={cr?.conditioning_pct} unit="%" digits={1} />
      </div>

      {(detail.limiting_factor || detail.cycle_focus) && (
        <div>
          <p className="h-section text-travertine mb-1">Decisions</p>
          {detail.limiting_factor && (
            <p className="text-[12px] text-iron leading-relaxed">
              <span className="uppercase tracking-wider text-[9px] text-travertine mr-1.5">Limiter</span>
              {detail.limiting_factor}
            </p>
          )}
          {detail.cycle_focus && (
            <p className="text-[12px] text-iron leading-relaxed">
              <span className="uppercase tracking-wider text-[9px] text-travertine mr-1.5">Focus</span>
              {detail.cycle_focus}
            </p>
          )}
        </div>
      )}

      {detail.macros_snapshot && (
        <div>
          <p className="h-section text-travertine mb-1">Macros at checkpoint</p>
          <pre className="text-[10px] text-iron bg-alabaster rounded border border-ash px-2 py-1.5 overflow-x-auto leading-snug">
{JSON.stringify(detail.macros_snapshot, null, 2)}
          </pre>
        </div>
      )}

      {detail.notes && (
        <div>
          <p className="h-section text-travertine mb-1">Notes</p>
          <p className="text-[12px] body-serif-sm italic text-iron leading-relaxed">{detail.notes}</p>
        </div>
      )}
    </div>
  );
}
