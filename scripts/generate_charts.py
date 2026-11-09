"""
Generates crisp, academic vector SVG charts for the research paper:
1. Figure 1: Pipeline Architecture Flow
2. Figure 2: Geographic District Distribution Bar Chart
3. Figure 3: Lead Score Distribution & Tier Histogram
4. Figure 4: Union-Find Entity Resolution Graph Topology
5. Figure 5: Verification & Conversion Funnel
"""

import sqlite3

def generate_district_chart_svg() -> str:
    conn = sqlite3.connect("data/metrixa_leads.db")
    cur = conn.cursor()
    cur.execute("SELECT district, count(*) FROM companies_golden GROUP BY district ORDER BY 2 DESC")
    districts = cur.fetchall()
    conn.close()

    max_val = 220
    w = 640
    h = 285
    pad_left = 160
    pad_right = 50
    pad_top = 26
    pad_bot = 26
    chart_w = w - pad_left - pad_right
    bar_h = 13
    gap = 6

    lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="font-family:\'Latin Modern Roman\',\'Times New Roman\',Georgia,serif; background:#ffffff;">',
        f'<rect width="{w}" height="{h}" fill="#fcfcfd" rx="2" stroke="#d1d5db" stroke-width="0.75"/>',
        f'<text x="16" y="18" font-size="9" font-weight="bold" fill="#111827">Figure 2: Empirical Geographic Distribution of Property Managers across Berlin Districts (N = 1,200)</text>',
    ]

    # Grid lines
    for tick in [0, 50, 100, 150, 200]:
        x = pad_left + (tick / max_val) * chart_w
        lines.append(f'<line x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" y2="{h - pad_bot}" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>')
        lines.append(f'<text x="{x:.1f}" y="{h - pad_bot + 13}" font-size="7.5" fill="#4b5563" text-anchor="middle">{tick}</text>')

    for i, (name, val) in enumerate(districts):
        y = pad_top + i * (bar_h + gap)
        bw = (val / max_val) * chart_w
        color = "#1e3a8a" if val >= 100 else ("#2563eb" if val >= 50 else "#60a5fa")
        pct = (val / 1200.0) * 100
        lines.append(f'<text x="{pad_left - 8}" y="{y + 9.5}" font-size="8" fill="#1f2937" text-anchor="end">{name}</text>')
        lines.append(f'<rect x="{pad_left}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}" rx="1"/>')
        lines.append(f'<text x="{pad_left + bw + 5:.1f}" y="{y + 9.5}" font-size="7.5" fill="#111827" font-weight="600">{val} ({pct:.1f}%)</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def generate_score_histogram_svg() -> str:
    conn = sqlite3.connect("data/metrixa_leads.db")
    cur = conn.cursor()
    cur.execute("SELECT (metrixa_lead_score/10)*10, count(*) FROM companies_golden GROUP BY 1 ORDER BY 1 ASC")
    buckets = cur.fetchall()
    conn.close()

    # Buckets: (20, 265), (30, 398), (40, 344), (50, 101), (60, 57), (70, 20), (80, 14), (90, 1)
    max_count = 420
    w = 640
    h = 240
    pad_left = 50
    pad_right = 30
    pad_top = 35
    pad_bot = 40
    chart_w = w - pad_left - pad_right
    chart_h = h - pad_top - pad_bot

    lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="font-family:\'Latin Modern Roman\',\'Times New Roman\',Georgia,serif; background:#ffffff;">',
        f'<rect width="{w}" height="{h}" fill="#fcfcfd" rx="2" stroke="#d1d5db" stroke-width="0.75"/>',
        f'<text x="16" y="18" font-size="9" font-weight="bold" fill="#111827">Figure 3: Lead Qualification Score Distribution and Tier Demarcations (Score Range 0 to 100, N = 1,200)</text>',
    ]

    # Y-axis grid
    for tick in [0, 100, 200, 300, 400]:
        y = pad_top + chart_h - (tick / max_count) * chart_h
        lines.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{w - pad_right}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>')
        lines.append(f'<text x="{pad_left - 8}" y="{y + 3:.1f}" font-size="7.5" fill="#4b5563" text-anchor="end">{tick}</text>')

    bar_width = chart_w / len(buckets) - 12
    for i, (b_start, count) in enumerate(buckets):
        bx = pad_left + i * (chart_w / len(buckets)) + 6
        bh = (count / max_count) * chart_h
        by = pad_top + chart_h - bh

        # Tier color
        if b_start >= 70:
            color = "#15803d"  # Tier A green
            tier_label = "Tier A"
        elif b_start >= 50 or b_start == 40:
            # Note: 40-49 contains both Tier C (<45) and Tier B (>=45)
            color = "#b45309" if b_start >= 50 else "#d97706"
            tier_label = "Tier B" if b_start >= 50 else "Mid"
        else:
            color = "#64748b"  # Tier C slate gray
            tier_label = "Tier C"

        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_width:.1f}" height="{bh:.1f}" fill="{color}" rx="1"/>')
        lines.append(f'<text x="{bx + bar_width/2:.1f}" y="{by - 4:.1f}" font-size="7.5" fill="#111827" font-weight="bold" text-anchor="middle">{count}</text>')
        lines.append(f'<text x="{bx + bar_width/2:.1f}" y="{pad_top + chart_h + 13}" font-size="7.5" fill="#374151" text-anchor="middle">{b_start}-{b_start+9}</text>')

    # Axis Labels
    lines.append(f'<text x="{w/2}" y="{h - 10}" font-size="8" fill="#374151" text-anchor="middle" font-weight="bold">Qualification Score Bracket (Points)</text>')
    lines.append(f'<text x="14" y="{pad_top + chart_h/2}" font-size="8" fill="#374151" text-anchor="middle" font-weight="bold" transform="rotate(-90 14 {pad_top + chart_h/2})">Entity Count</text>')

    # Tier Legend
    lines.append(f'<rect x="{w - 220}" y="24" width="10" height="8" fill="#64748b" rx="1"/>')
    lines.append(f'<text x="{w - 206}" y="31" font-size="7.5" fill="#374151">Tier C (&lt;45): 756 (63.0%)</text>')
    lines.append(f'<rect x="{w - 220}" y="36" width="10" height="8" fill="#d97706" rx="1"/>')
    lines.append(f'<text x="{w - 206}" y="43" font-size="7.5" fill="#374151">Tier B (45-69): 409 (34.1%)</text>')
    lines.append(f'<rect x="{w - 220}" y="48" width="10" height="8" fill="#15803d" rx="1"/>')
    lines.append(f'<text x="{w - 206}" y="55" font-size="7.5" fill="#374151">Tier A (&ge;70): 35 (2.9%)</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def generate_funnel_svg() -> str:
    steps = [
        ("1. Multi-Source Raw Ingested", 1375, "100.0%", "#1e3a8a"),
        ("2. Deduplicated Golden Entities", 1200, "87.3%", "#1d4ed8"),
        ("3. Crawled Corporate Subpages", 885, "64.4%", "#2563eb"),
        ("4. Corporate Domains Verified", 243, "17.7%", "#3b82f6"),
        ("5. Executive Decision Makers Named", 104, "7.6%", "#0284c7"),
        ("6. RFC 5321 DNS MX Verified Emails", 102, "7.4%", "#0f766e"),
        ("7. DOM PropTech ERP Detected", 41, "3.0%", "#b45309"),
        ("8. Tier A High-Priority Qualified", 35, "2.5%", "#15803d"),
    ]

    w = 640
    h = 230
    pad_left = 180
    pad_right = 75
    pad_top = 28
    pad_bot = 16
    chart_w = w - pad_left - pad_right
    bar_h = 16
    gap = 7
    max_val = 1375

    lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="font-family:\'Latin Modern Roman\',\'Times New Roman\',Georgia,serif; background:#ffffff;">',
        f'<rect width="{w}" height="{h}" fill="#fcfcfd" rx="2" stroke="#d1d5db" stroke-width="0.75"/>',
        f'<text x="16" y="18" font-size="9" font-weight="bold" fill="#111827">Figure 5: Empirical Conversion Funnel from Raw Directory Records to Verified Qualified Leads</text>',
    ]

    for i, (name, val, pct, color) in enumerate(steps):
        y = pad_top + i * (bar_h + gap)
        bw = (val / max_val) * chart_w
        lines.append(f'<text x="{pad_left - 10}" y="{y + 11.5}" font-size="8" fill="#1f2937" text-anchor="end">{name}</text>')
        lines.append(f'<rect x="{pad_left}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{color}" rx="1.5"/>')
        lines.append(f'<text x="{pad_left + bw + 6:.1f}" y="{y + 11.5}" font-size="7.5" fill="#111827" font-weight="600">{val:,} ({pct})</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def generate_architecture_topology_svg() -> str:
    w = 640
    h = 175
    lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="font-family:\'Latin Modern Roman\',\'Times New Roman\',Georgia,serif; background:#ffffff;">',
        f'<rect width="{w}" height="{h}" fill="#fcfcfd" rx="2" stroke="#d1d5db" stroke-width="0.75"/>',
        f'<text x="16" y="18" font-size="9" font-weight="bold" fill="#111827">Figure 4: Disjoint-Set Union-Find Clustering and Multi-Key Entity Deduplication Topology</text>',
    ]

    # Raw Sources box
    lines.append(f'<rect x="20" y="32" width="130" height="125" fill="#f8fafc" stroke="#64748b" stroke-width="0.75" rx="2"/>')
    lines.append(f'<text x="85" y="48" font-size="8" font-weight="bold" fill="#0f172a" text-anchor="middle">Raw Directory Shards</text>')
    sources = ["11880.com (838)", "Gelbe Seiten (405)", "OpenStreetMap (100)", "VDIV Roster (30)", "Web Search (2)"]
    for i, s in enumerate(sources):
        lines.append(f'<rect x="28" y="{58 + i * 18}" width="114" height="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="0.5" rx="1"/>')
        lines.append(f'<text x="85" y="{68 + i * 18}" font-size="6.8" fill="#334155" text-anchor="middle">{s}</text>')

    # Blocking Keys and Normalization
    lines.append(f'<rect x="180" y="32" width="145" height="125" fill="#f8fafc" stroke="#64748b" stroke-width="0.75" rx="2"/>')
    lines.append(f'<text x="252" y="48" font-size="8" font-weight="bold" fill="#0f172a" text-anchor="middle">Multi-Key Blocking Engine</text>')
    keys = [
        "1. eTLD+1 Domain Key",
        "2. E.164 Clean Phone Key",
        "3. Legal Suffix Normalizer",
        "4. Jaro-Winkler Token-Sort",
        "5. 5-Digit Postal Code Block",
    ]
    for i, k in enumerate(keys):
        lines.append(f'<rect x="188" y="{58 + i * 18}" width="129" height="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="0.5" rx="1"/>')
        lines.append(f'<text x="252" y="{68 + i * 18}" font-size="6.8" fill="#334155" text-anchor="middle">{k}</text>')

    # Union-Find Graph Engine
    lines.append(f'<rect x="355" y="32" width="135" height="125" fill="#eff6ff" stroke="#2563eb" stroke-width="0.75" rx="2"/>')
    lines.append(f'<text x="422" y="48" font-size="8" font-weight="bold" fill="#1e3a8a" text-anchor="middle">Disjoint-Set Union-Find</text>')
    uf_steps = [
        "Find(u): Path Compression",
        "Union(u, v): Rank Balance",
        "Edge: Sim_JW &ge; 0.88 + PLZ",
        "Connected Components",
        "175 Redundant Merged",
    ]
    for i, u in enumerate(uf_steps):
        lines.append(f'<rect x="363" y="{58 + i * 18}" width="119" height="14" fill="#ffffff" stroke="#bfdbfe" stroke-width="0.5" rx="1"/>')
        lines.append(f'<text x="422" y="{68 + i * 18}" font-size="6.8" fill="#1e40af" text-anchor="middle">{u}</text>')

    # Golden Ledger
    lines.append(f'<rect x="520" y="32" width="100" height="125" fill="#f0fdf4" stroke="#16a34a" stroke-width="0.75" rx="2"/>')
    lines.append(f'<text x="570" y="48" font-size="8" font-weight="bold" fill="#14532d" text-anchor="middle">Canonical Master</text>')
    g_steps = [
        "1,200 Unique Leads",
        "Immutable SHA-256",
        "Postal Match: 95.4%",
        "Golden Entity ID",
        "Relational Store",
    ]
    for i, g in enumerate(g_steps):
        lines.append(f'<rect x="526" y="{58 + i * 18}" width="88" height="14" fill="#ffffff" stroke="#bbf7d0" stroke-width="0.5" rx="1"/>')
        lines.append(f'<text x="570" y="{68 + i * 18}" font-size="6.8" fill="#166534" text-anchor="middle">{g}</text>')

    # Arrows
    for x_arr in [150, 325, 490]:
        lines.append(f'<line x1="{x_arr}" y1="94" x2="{x_arr + 25}" y2="94" stroke="#2563eb" stroke-width="1.5"/>')
        lines.append(f'<polygon points="{x_arr + 29},94 {x_arr + 22},90 {x_arr + 22},98" fill="#2563eb"/>')

    lines.append('</svg>')
    return '\n'.join(lines)


if __name__ == "__main__":
    print("Testing chart generation...")
    s1 = generate_district_chart_svg()
    s2 = generate_score_histogram_svg()
    s3 = generate_funnel_svg()
    s4 = generate_architecture_topology_svg()
    print("All 4 SVGs generated successfully!")
