"""Style Engine for DC-ShiftMaster Pro.

All visual constants live here so you can tweak colors, fonts, and
spacing without touching business logic. Inspired by AWS SageMaker /
Google Anthos design language.
"""

# ── Color Palette: "Midnight Deep" ───────────────────────────────────

COLORS = {
    # Backgrounds
    "bg":               "#020617",   # Deepest Navy
    "surface":          "#1E293B",   # Slate 800 — cards, panels
    "surface_border":   "#334155",   # Slate 700 — card borders
    "surface_hover":    "#253349",   # Slightly lighter on hover
    "input_bg":         "#0F172A",   # Input field background

    # Accents
    "primary":          "#6366F1",   # Indigo-500 — primary actions
    "primary_hover":    "#818CF8",   # Indigo-400
    "secondary":        "#22D3EE",   # Cyan-400 — secondary accents
    "secondary_hover":  "#67E8F9",   # Cyan-300

    # Shift colors
    "day_shift":        "#c87533",   # Warm orange
    "day_shift_bg":     "#3D2A15",   # Low-opacity orange for pills
    "night_shift":      "#336699",   # Cool blue
    "night_shift_bg":   "#1A2D40",   # Low-opacity blue for pills
    "front_half":       "#22C55E",   # Green-500
    "back_half":        "#EAB308",   # Yellow-500

    # Status
    "success":          "#22C55E",   # Green
    "warning":          "#F59E0B",   # Amber
    "danger":           "#EF4444",   # Red
    "nobody_bg":        "#0F172A",   # Darker than surface
    "nobody_fg":        "#475569",   # Slate 600
    "override_border":  "#F59E0B",   # Amber glow for overrides
    "today_border":     "#6366F1",   # Indigo for today

    # Text
    "text":             "#F1F5F9",   # Slate 100
    "text_secondary":   "#94A3B8",   # Slate 400
    "text_muted":       "#64748B",   # Slate 500
    "text_on_primary":  "#FFFFFF",

    # Sidebar
    "sidebar_bg":       "#020617",   # Same as bg
    "sidebar_active":   "#1E293B",
    "sidebar_icon":     "#64748B",   # Slate 500
    "sidebar_icon_active": "#6366F1",

    # Canvas
    "canvas_bg":        "#020617",
    "grid_line":        "#1E293B",
}

# ── Typography ───────────────────────────────────────────────────────

FONTS = {
    "family":           "Segoe UI",      # Falls back gracefully on Windows
    "mono":             "Consolas",       # Monospace for timers

    # Sizes
    "h1":               ("Segoe UI", 22, "bold"),
    "h2":               ("Segoe UI", 16, "bold"),
    "h3":               ("Segoe UI", 13, "bold"),
    "body":             ("Segoe UI", 12),
    "body_bold":        ("Segoe UI", 12, "bold"),
    "small":            ("Segoe UI", 10),
    "small_bold":       ("Segoe UI", 10, "bold"),
    "tiny":             ("Segoe UI", 9),
    "label":            ("Segoe UI", 9),   # Uppercase labels
    "mono_large":       ("Consolas", 16, "bold"),
    "mono_small":       ("Consolas", 11),
    "pill":             ("Segoe UI", 9, "bold"),
    "badge":            ("Segoe UI", 8, "bold"),
    "stat_value":       ("Consolas", 20, "bold"),
    "stat_label":       ("Segoe UI", 9),
}

# ── Spacing & Sizing ────────────────────────────────────────────────

SPACING = {
    "pad_xs":           4,
    "pad_sm":           8,
    "pad_md":           12,
    "pad_lg":           16,
    "pad_xl":           24,
    "card_radius":      8,
    "pill_radius":      12,
    "sidebar_width":    56,
    "header_height":    52,
    "cell_min_h":       90,
}
