# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Daniel Delgado-Uriarte. Non-commercial use; companies need a licence (see NOTICE).
"""Figures of the Open Well Data site, drawn at build time as inline SVG (no JavaScript, no external library).

Style: journal and Our World in Data conventions. A title and a one-line subtitle above, direct labels instead of
legends, thin axes, a restrained palette taken from the page tokens (so both themes work), and under every figure a
caption line with the figure number, the source, the licence and a link to the data it was drawn from. Every figure
also carries its data as an HTML table inside <details>, and an accessible name and description on the SVG.
"""
import html
import math

E = html.escape


def _n(x, d=1):
    return f"{x:.{d}f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def figure(num, fid, title, subtitle, svg, source, licence, data_links, table="", note=""):
    """data_links: [(href, label)], e.g. [("data/sources-status.csv", "Download data (CSV)")]."""
    links = " ".join(f'<a href="{E(h)}">{E(t)}</a>' for h, t in data_links)
    tbl = f'<details class="fig-data"><summary>Data table for figure {num}</summary>{table}</details>' if table else ""
    return f"""<figure class="fig" id="{E(fid)}" aria-labelledby="{E(fid)}-t">
<div class="fig-head"><p class="fig-num">Figure {num}</p><h3 class="fig-title" id="{E(fid)}-t">{E(title)}</h3><p class="fig-sub">{subtitle}</p></div>
<div class="fig-body">{svg}</div>
<figcaption class="fig-cap"><span class="fig-src">Source: {source}</span> <span class="fig-lic">Licence: {licence}</span> <span class="fig-links">{links}</span>{f'<span class="fig-note">{note}</span>' if note else ""}</figcaption>
{tbl}
</figure>"""


def _svg(w, h, fid, desc, inner):
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-labelledby="{E(fid)}-t {E(fid)}-d" '
            f'preserveAspectRatio="xMinYMin meet"><desc id="{E(fid)}-d">{E(desc)}</desc>{inner}</svg>')


def bars(fid, rows, desc, part_label="", rest_label="", width=760, label_w=190, row_h=26):
    """Horizontal bars. rows: [(label, total, part)]; part (may be None) is drawn darker from the left. Direct labels:
    the value at the end of each bar; the two segments are named once, on the first bar."""
    vmax = max(r[1] for r in rows) or 1
    plot_w = width - label_w - 200
    h = 28 + row_h * len(rows)
    out = []
    for i, (lab, tot, part) in enumerate(rows):
        y = 22 + i * row_h
        wt = plot_w * tot / vmax
        out.append(f'<text class="f-cat" x="{label_w - 8}" y="{y + 13}" text-anchor="end">{E(lab)}</text>')
        out.append(f'<rect class="f-b2" x="{label_w}" y="{y + 3}" width="{wt:.1f}" height="{row_h - 9}"/>')
        if part:
            wp = plot_w * part / vmax
            out.append(f'<rect class="f-b1" x="{label_w}" y="{y + 3}" width="{wp:.1f}" height="{row_h - 9}"/>')
        val = f"{tot}" + (f" ({part} allow copies)" if (part is not None and i == 0) else "")
        out.append(f'<text class="f-val" x="{label_w + wt + 6:.1f}" y="{y + 13}">{E(val)}</text>')
    if part_label and rows and rows[0][2]:
        wp = plot_w * rows[0][2] / vmax
        out.append(f'<text class="f-key f-key1" x="{label_w}" y="14">{E(part_label)}</text>')
        out.append(f'<line class="f-tick" x1="{label_w + 4}" x2="{label_w + 4}" y1="16" y2="{22 + 3}"/>')
        if rest_label:
            wt = plot_w * rows[0][1] / vmax
            x = label_w + max(wp + 8, wt - 4)
            out.append(f'<text class="f-key f-key2" x="{min(x, label_w + plot_w):.1f}" y="14" text-anchor="end">{E(rest_label)}</text>')
    out.append(f'<line class="f-axis" x1="{label_w}" x2="{label_w}" y1="20" y2="{h - 4}"/>')
    return _svg(width, h, fid, desc, "".join(out))


def class_bars(fid, rows, desc, width=760, label_w=150, row_h=26):
    """Horizontal bars coloured by licence class. rows: [(label, n, css_class)], label written beside each bar."""
    vmax = max(r[1] for r in rows) or 1
    plot_w = width - label_w - 70
    h = 10 + row_h * len(rows)
    out = []
    for i, (lab, n, cls) in enumerate(rows):
        y = 6 + i * row_h
        w = max(2.0, plot_w * n / vmax)
        out.append(f'<text class="f-cat" x="{label_w - 8}" y="{y + 13}" text-anchor="end">{E(lab)}</text>')
        out.append(f'<rect class="f-lic f-lic-{cls}" x="{label_w}" y="{y + 3}" width="{w:.1f}" height="{row_h - 9}"/>')
        out.append(f'<text class="f-val" x="{label_w + w + 6:.1f}" y="{y + 13}">{n}</text>')
    out.append(f'<line class="f-axis" x1="{label_w}" x2="{label_w}" y1="4" y2="{h - 4}"/>')
    return _svg(width, h, fid, desc, "".join(out))


def step(fid, points, desc, y_label, width=760, height=260):
    """Cumulative step line. points: [(date_label, cumulative)], labelled directly at each step."""
    l, r, t, b = 56, 30, 18, 34
    pw, ph = width - l - r, height - t - b
    ymax = max(p[1] for p in points) or 1
    nice = 10 ** math.floor(math.log10(ymax))
    ytop = math.ceil(ymax / nice) * nice
    n = len(points)
    xs = [l + (pw * i / (n - 1) if n > 1 else pw / 2) for i in range(n)]
    ys = [t + ph * (1 - p[1] / ytop) for p in points]
    path = f"M{xs[0]:.1f},{ys[0]:.1f}" + "".join(f"H{xs[i]:.1f}V{ys[i]:.1f}" for i in range(1, n))
    out = []
    for k in range(0, 5):
        v = ytop * k / 4
        y = t + ph * (1 - k / 4)
        out.append(f'<line class="f-grid" x1="{l}" x2="{width - r}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="f-tickl" x="{l - 6}" y="{y + 4:.1f}" text-anchor="end">{int(v)}</text>')
    out.append(f'<line class="f-axis" x1="{l}" x2="{width - r}" y1="{t + ph}" y2="{t + ph}"/>')
    out.append(f'<path class="f-line" d="{path}"/>')
    for i, (lab, v) in enumerate(points):
        out.append(f'<circle class="f-dot" cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="3.5"/>')
        out.append(f'<text class="f-val" x="{xs[i]:.1f}" y="{ys[i] - 9:.1f}" text-anchor="{"end" if i == n - 1 else "middle"}">{v}</text>')
        out.append(f'<text class="f-tickl" x="{xs[i]:.1f}" y="{height - 12}" text-anchor="middle">{E(lab)}</text>')
    out.append(f'<text class="f-tickl" x="{l}" y="{t - 6}">{E(y_label)}</text>')
    return _svg(width, height, fid, desc, "".join(out))


def heat_table(caption, rows, cols, counts, row_head="Country", col_label=lambda c: c, col_class=lambda c: ""):
    """Country x data-type matrix as an HTML table (accessible as is) with five shade steps and the count in each cell."""
    vmax = max([counts.get((r, c), 0) for r in rows for c in cols] or [1]) or 1

    def step_of(v):
        return 0 if not v else min(5, 1 + int(4 * math.log1p(v) / math.log1p(vmax) + 1e-9))
    head = "".join(f'<th scope="col" class="num {col_class(c)}">{E(col_label(c))}</th>' for c in cols)
    body = ""
    for r in rows:
        cells = ""
        for c in cols:
            v = counts.get((r, c), 0)
            cells += f'<td class="num hm hm-s{step_of(v)}">{v if v else "·"}</td>'
        body += f'<tr><th scope="row">{E(r)}</th>{cells}</tr>'
    return (f'<div class="tablewrap heatwrap"><table class="heatm"><caption class="sr">{E(caption)}</caption>'
            f'<thead><tr><th scope="col">{E(row_head)}</th>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def _ticks(lo, hi, log=False):
    if log:
        a, b = math.floor(math.log10(max(lo, 1e-6))), math.ceil(math.log10(max(hi, 1e-6)))
        return [10 ** k for k in range(a, b + 1)], 10 ** a, 10 ** b
    span = (hi - lo) or abs(hi) or 1
    st = 10 ** math.floor(math.log10(span / 2))
    for m in (1, 2, 5, 10):
        if span / (st * m) <= 4:
            st *= m
            break
    a = math.floor(lo / st) * st
    b = math.ceil(hi / st) * st
    return [a + i * st for i in range(int(round((b - a) / st)) + 1)], a, b


def log_plot(fid, ex, desc, track_w=150, height=560):
    """Multi-track log plot of a real excerpt: vertical axis (depth or elapsed time) increasing downwards, one track
    per curve with its standard name and SI unit in the header, thin grid, values as drawn."""
    ax = ex["axis"]
    vals = ax["values"]
    tracks = ex["tracks"]
    l, t, b = 64, 58, 18
    ph = height - t - b
    width = l + track_w * len(tracks) + 10
    y0, y1 = min(v for v in vals if v is not None), max(v for v in vals if v is not None)
    yt, ya, yb = _ticks(y0, y1)

    def Y(v):
        return t + ph * (v - ya) / ((yb - ya) or 1)
    out = []
    for v in yt:
        out.append(f'<line class="f-grid" x1="{l}" x2="{width - 10}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>')
        out.append(f'<text class="f-tickl" x="{l - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{_n(float(v), 1)}</text>')
    out.append(f'<text class="f-trk" x="2" y="{t - 38}">{E(ax["name"].split(" ")[-1])}</text>')
    out.append(f'<text class="f-tickl" x="2" y="{t - 24}">{E(ax["unit"])}</text>')
    for k, tr in enumerate(tracks):
        x0 = l + k * track_w + 8
        w = track_w - 16
        pts = [(a, v) for a, v in zip(vals, tr["values"]) if a is not None and v is not None and (v > 0 or not tr["log"])]
        if not pts:
            continue
        lo, hi = min(p[1] for p in pts), max(p[1] for p in pts)
        xt, xa, xb = _ticks(lo, hi, tr["log"])

        def X(v):
            if tr["log"]:
                return x0 + w * (math.log10(v) - math.log10(xa)) / ((math.log10(xb) - math.log10(xa)) or 1)
            return x0 + w * (v - xa) / ((xb - xa) or 1)
        out.append(f'<rect class="f-track" x="{x0}" y="{t}" width="{w}" height="{ph}"/>')
        for v in (xt[0], xt[-1]):
            out.append(f'<text class="f-tickl" x="{X(v):.1f}" y="{t - 6}" text-anchor="{"start" if v == xt[0] else "end"}">{_n(float(v), 2)}</text>')
        for v in xt[1:-1]:
            out.append(f'<line class="f-grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{t}" y2="{t + ph}"/>')
        out.append(f'<text class="f-trk" x="{x0 + w / 2:.1f}" y="{t - 38}" text-anchor="middle">{E(tr["name"])}</text>')
        out.append(f'<text class="f-tickl" x="{x0 + w / 2:.1f}" y="{t - 24}" text-anchor="middle">{E(tr["unit"])}{" (log)" if tr["log"] else ""}</text>')
        d = "M" + "L".join(f"{X(v):.1f},{Y(a):.1f}" for a, v in pts)
        out.append(f'<path class="f-curve" d="{d}"/>')
    return _svg(width, height, fid, desc, "".join(out))


def excerpt_table(ex):
    ax = ex["axis"]
    head = f'<th scope="col" class="num">{E(ax["name"])} ({E(ax["unit"])})</th>' + "".join(
        f'<th scope="col" class="num">{E(t["name"])} ({E(t["unit"])})</th>' for t in ex["tracks"])
    rows = ""
    for i, a in enumerate(ax["values"]):
        rows += f'<tr><th scope="row" class="num">{"" if a is None else _n(a, 2)}</th>' + "".join(
            f'<td class="num">{"" if t["values"][i] is None else t["values"][i]}</td>' for t in ex["tracks"]) + "</tr>"
    return (f'<div class="tablewrap"><table class="dense"><caption>Values drawn in the figure ({ex["points"]} rows: every '
            f'{ex["stride"]} of {ex["rows_in_window"]} rows in the window)</caption><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>')


def excerpt_csv(ex):
    ax = ex["axis"]
    cols = [f'{ax["name"].replace(" ", "_")} [{ax["unit"]}]'] + [f'{t["name"]} [{t["unit"]}]' for t in ex["tracks"]]
    lines = [",".join(cols)]
    for i, a in enumerate(ax["values"]):
        lines.append(",".join(["" if a is None else repr(a)] + ["" if t["values"][i] is None else repr(t["values"][i]) for t in ex["tracks"]]))
    return "\n".join(lines) + "\n"


def equal_earth(lon, lat):
    """Equal Earth projection (Šavrič, Patterson and Jenny 2018), degrees in, unit coordinates out."""
    A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
    M = math.sqrt(3) / 2
    lam, phi = math.radians(lon), math.radians(lat)
    th = math.asin(M * math.sin(phi))
    t2 = th * th
    t6 = t2 * t2 * t2
    x = 2 * math.sqrt(3) * lam * math.cos(th) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
    y = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


def dot_map(fid, land, points, desc, width=1000, n_labels=10):
    """World map: land outlines (list of rings of [lon, lat]) and one dot per country at its label point, area
    proportional to the number of sources, shade by the share whose licence allows copies (five steps)."""
    sx = sy = width / (2 * 2.7066)
    top_y, bottom_y = equal_earth(0, 84)[1], equal_earth(0, -58)[1]   # crop to inhabited latitudes (no Antarctica)
    height = int((top_y - bottom_y) * sy) + 4

    def P(lon, lat):
        x, y = equal_earth(lon, lat)
        return width / 2 + x * sx, (top_y - y) * sy + 2
    out = []
    out += [f'<path class="f-land" d="{"".join(_ring(r, P) for r in rings)}"/>' for rings in land]
    nmax = max(p[3] for p in points) or 1
    for name, lon, lat, n, share, *cls in sorted(points, key=lambda p: -p[3]):
        x, y = P(lon, lat)
        r = 3 + 26 * math.sqrt(n / nmax)
        s = 1 + min(4, int(share * 5))
        out.append(f'<circle class="f-pt {cls[0] if cls else "hm-s" + str(s)}" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"><title>{E(name)}: {n} sources, {round(100 * share)} % allow copies</title></circle>')
    placed = []  # direct labels for the largest circles, skipping any that would overlap one already placed
    for name, lon, lat, n, share, *_ in sorted(points, key=lambda p: -p[3])[:n_labels]:
        x, y = P(lon, lat)
        r = 3 + 26 * math.sqrt(n / nmax)
        txt = f"{name} {n}"
        box = (x + r + 2, y - 8, x + r + 4 + 6.6 * len(txt), y + 6)
        if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed):
            continue
        placed.append(box)
        out.append(f'<text class="f-maplab" x="{x + r + 3:.1f}" y="{y + 4:.1f}">{E(txt)}</text>')
    return _svg(width, height, fid, desc, "".join(out))


def _ring(r, P, step=1.5):
    """Projected ring, thinned: a point closer than `step` pixels to the last kept one is dropped."""
    pts, last = [], None
    for lo, la in r:
        x, y = P(lo, la)
        if last is None or abs(x - last[0]) + abs(y - last[1]) >= step:
            pts.append((x, y)); last = (x, y)
    if len(pts) < 3:
        return ""
    return "M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in pts) + "Z"


def isotype(fid, rows, desc, part_label="", rest_label="", per_row=50, unit=8, gap=2, label_w=170, legend=None, on_dark=False):
    """Isotype count: one equal square per source, never scaled or cut. rows: [(label, n, part)]; the first `part`
    squares of a row are the highlighted series (accent), the rest grey. Long rows wrap after `per_row` squares."""
    step = unit + gap
    width = label_w + per_row * step + 48
    out, y = [], 22
    if legend:  # [(css class, label)]: one key per class, direct and in order
        x = label_w
        for cls, lab in legend:
            out.append(f'<rect class="{cls}" x="{x}" y="4" width="{unit}" height="{unit}"/><text class="f-val" x="{x + step + 2}" y="12">{E(lab)}</text>')
            x += step + 2 + 7 * len(lab) + 18
        y = 30
        part_label = ""
    if part_label:
        out.append(f'<rect class="iso-a" x="{label_w}" y="4" width="{unit}" height="{unit}"/><text class="f-val" x="{label_w + step + 2}" y="12">{E(part_label)}</text>')
        if rest_label:
            x2 = label_w + step + 2 + 7 * len(part_label) + 24
            out.append(f'<rect class="iso-b" x="{x2}" y="4" width="{unit}" height="{unit}"/><text class="f-val" x="{x2 + step + 2}" y="12">{E(rest_label)}</text>')
        y = 30
    for row in rows:
        lab, n, part = row[:3]
        classes = row[3] if len(row) > 3 else None
        lines = max(1, math.ceil(n / per_row))
        out.append(f'<text class="f-cat" x="{label_w - 10}" y="{y + unit}" text-anchor="end">{E(lab)}</text>')
        for i in range(n):
            r, c = divmod(i, per_row)
            cls = classes[i] if classes else ("iso-a" if i < (part or 0) else "iso-b")
            out.append(f'<rect class="{cls}" x="{label_w + c * step}" y="{y + r * step}" width="{unit}" height="{unit}"/>')
        last_c = (n - 1) % per_row + 1
        out.append(f'<text class="f-val" x="{label_w + last_c * step + 6}" y="{y + (lines - 1) * step + unit}">{n}</text>')
        y += lines * step + 8
    return _svg(width, y + 4, fid, desc, "".join(out))
