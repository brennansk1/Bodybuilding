"""
Plotly chart generators — return Plotly JSON dicts for frontend rendering.
"""
import plotly.graph_objects as go

# Coronado jungle color palette
COLORS = {
    "bg": "#0b1410",
    "card": "#0f1f18",
    "border": "#1a3328",
    "accent": "#c8a84e",
    "primary": "#2d8a4e",
    "success": "#4ade80",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "text": "#e8efe9",
    "muted": "#8faa96",
    "green_fill": "rgba(45, 138, 78, 0.3)",
    "gold_fill": "rgba(200, 168, 78, 0.3)",
}

LAYOUT_DEFAULTS = dict(
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["card"],
    font=dict(color=COLORS["text"], size=12),
    margin=dict(l=40, r=40, t=50, b=40),
)


def generate_spider_plot(site_scores: dict[str, float], overall: float) -> dict:
    """Radar chart of HQI scores per muscle site."""
    sites = list(site_scores.keys())
    scores = list(site_scores.values())
    # Close the polygon
    sites_closed = sites + [sites[0]]
    scores_closed = scores + [scores[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores_closed,
        theta=[s.replace("_", " ").title() for s in sites_closed],
        fill="toself",
        fillcolor=COLORS["green_fill"],
        line=dict(color=COLORS["accent"], width=2),
        name=f"HQI ({overall})",
    ))
    # Ideal ring at 100
    fig.add_trace(go.Scatterpolar(
        r=[100] * len(sites_closed),
        theta=[s.replace("_", " ").title() for s in sites_closed],
        line=dict(color=COLORS["border"], width=1, dash="dot"),
        name="Ideal",
    ))

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        polar=dict(
            bgcolor=COLORS["card"],
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=COLORS["border"]),
            angularaxis=dict(gridcolor=COLORS["border"]),
        ),
        showlegend=False,
        title=dict(text=f"Hypertrophy Quality Index — {overall}", font=dict(size=14)),
    )

    return fig.to_plotly_json()


def generate_pds_glide_path(
    history: list[tuple[str, float, str | None]],
) -> dict:
    """Line chart with PDS over time + tier bands."""
    dates = [h[0] for h in history]
    scores = [h[1] for h in history]

    fig = go.Figure()

    # Tier bands
    tier_bands = [
        ("Novice", 0, 50, "rgba(239,68,68,0.08)"),
        ("Intermediate", 50, 70, "rgba(245,158,11,0.08)"),
        ("Advanced", 70, 85, "rgba(200,168,78,0.08)"),
        ("Elite", 85, 100, "rgba(74,222,128,0.08)"),
    ]
    for label, y0, y1, color in tier_bands:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0)
        fig.add_annotation(
            x=dates[-1] if dates else 0, y=(y0 + y1) / 2,
            text=label, showarrow=False,
            font=dict(color=COLORS["muted"], size=9),
            xanchor="right",
        )

    # Main line
    fig.add_trace(go.Scatter(
        x=dates, y=scores,
        mode="lines+markers",
        line=dict(color=COLORS["accent"], width=3),
        marker=dict(size=8, color=COLORS["accent"]),
        name="PDS",
    ))

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        yaxis=dict(range=[0, 100], gridcolor=COLORS["border"]),
        xaxis=dict(gridcolor=COLORS["border"]),
        title=dict(text="PDS Glide Path", font=dict(size=14)),
        showlegend=False,
    )

    return fig.to_plotly_json()


def generate_autonomic_gauge(ari_score: float) -> dict:
    """Gauge chart for Autonomic Readiness Index."""
    if ari_score >= 70:
        bar_color = COLORS["success"]
    elif ari_score >= 40:
        bar_color = COLORS["warning"]
    else:
        bar_color = COLORS["danger"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=ari_score,
        title=dict(text="Autonomic Readiness", font=dict(size=14)),
        number=dict(font=dict(size=36)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor=COLORS["muted"]),
            bar=dict(color=bar_color),
            bgcolor=COLORS["card"],
            bordercolor=COLORS["border"],
            steps=[
                dict(range=[0, 40], color="rgba(239,68,68,0.15)"),
                dict(range=[40, 70], color="rgba(245,158,11,0.15)"),
                dict(range=[70, 100], color="rgba(74,222,128,0.15)"),
            ],
            threshold=dict(
                line=dict(color=COLORS["accent"], width=3),
                value=ari_score,
            ),
        ),
    ))

    fig.update_layout(**LAYOUT_DEFAULTS)
    return fig.to_plotly_json()


def generate_adherence_grid(
    data: list[tuple[str, float, float]],
) -> dict:
    """Grouped bar chart: nutrition + training adherence by week."""
    dates = [d[0] for d in data]
    nutrition = [d[1] for d in data]
    training = [d[2] for d in data]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=nutrition,
        name="Nutrition",
        marker_color=COLORS["accent"],
    ))
    fig.add_trace(go.Bar(
        x=dates, y=training,
        name="Training",
        marker_color=COLORS["primary"],
    ))

    # 85% adherence lock threshold
    fig.add_hline(y=85, line_dash="dash", line_color=COLORS["danger"],
                  annotation_text="Adherence Lock (85%)",
                  annotation_font_color=COLORS["danger"],
                  annotation_font_size=10)

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        barmode="group",
        yaxis=dict(range=[0, 100], gridcolor=COLORS["border"]),
        xaxis=dict(gridcolor=COLORS["border"]),
        title=dict(text="Adherence Grid", font=dict(size=14)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    return fig.to_plotly_json()


def generate_hypertrophy_heatmap(site_scores: dict[str, float]) -> dict:
    """Heatmap visualization of muscle development by site."""
    sites = list(site_scores.keys())
    scores = list(site_scores.values())

    # Color mapping: red (low) -> yellow (mid) -> green (high)
    colors: list[str] = []
    for s in scores:
        if s >= 80:
            colors.append(COLORS["success"])
        elif s >= 60:
            colors.append(COLORS["accent"])
        elif s >= 40:
            colors.append(COLORS["warning"])
        else:
            colors.append(COLORS["danger"])

    fig = go.Figure(go.Bar(
        x=scores,
        y=[s.replace("_", " ").title() for s in sites],
        orientation="h",
        marker=dict(color=colors),
        text=[f"{s:.0f}" for s in scores],
        textposition="outside",
    ))

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        xaxis=dict(range=[0, 100], gridcolor=COLORS["border"], title="HQI Score"),
        yaxis=dict(gridcolor=COLORS["border"]),
        title=dict(text="Hypertrophy Heatmap", font=dict(size=14)),
        height=max(300, len(sites) * 40),
    )

    return fig.to_plotly_json()
