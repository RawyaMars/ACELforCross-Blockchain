import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Ellipse

OBJECT_TYPE_COLORS = {
    "Lot": "#8fbc8f",
    "RawMaterialBatch": "#00cc00",
    "Shipment": "#6b5b1a",
}
_PALETTE = ["#4477aa", "#aa4499", "#999933", "#cc6677", "#44aa99", "#882255"]

def _color_for(object_type, seen):
    if object_type not in seen:
        if object_type in OBJECT_TYPE_COLORS:
            seen[object_type] = OBJECT_TYPE_COLORS[object_type]
        else:
            unassigned = [c for c in _PALETTE if c not in seen.values()]
            seen[object_type] = (unassigned or _PALETTE)[0]
    return seen[object_type]

def _lighten(hex_color, factor=0.75):

    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"

def _activity_event_count(ocdfg, activity):
    ids = set()
    for ot_events in ocdfg["activities_ot"]["events"].values():
        ids |= ot_events.get(activity, set())
    return len(ids)

def _rank_nodes(activities, edges):
    g = nx.DiGraph()
    g.add_nodes_from(activities)
    for (a1, a2) in edges:
        if a1 != a2:
            g.add_edge(a1, a2)

    rank = {n: 0 for n in g.nodes}
    try:
        order = list(nx.topological_sort(g))
    except nx.NetworkXUnfeasible:
        order = list(g.nodes)

    for n in order:
        for succ in g.successors(n):
            rank[succ] = max(rank[succ], rank[n] + 1)
    return rank

def render_ocdfg(ocdfg, output_png_path, annotation="frequency"):
    activities = sorted(ocdfg["activities"])
    object_types = sorted(ocdfg["object_types"])




    edges = []
    start_nodes = {ot: f"[start:{ot}]" for ot in object_types}
    end_nodes = {ot: f"[end:{ot}]" for ot in object_types}

    for ot, per_act in ocdfg["start_activities"]["events"].items():
        for act, ev_ids in per_act.items():
            edges.append((start_nodes[ot], act, ot, len(ev_ids)))
    for ot, per_act in ocdfg["end_activities"]["events"].items():
        for act, ev_ids in per_act.items():
            edges.append((act, end_nodes[ot], ot, len(ev_ids)))
    for ot, per_pair in ocdfg["edges"]["event_couples"].items():
        for (a1, a2), couples in per_pair.items():
            edges.append((a1, a2, ot, len(couples)))


    rank = _rank_nodes(activities, [(a1, a2) for a1, a2, ot, c in edges if a1 in activities and a2 in activities])
    max_rank = max(rank.values(), default=0)

    pos = {}
    by_rank = {}
    for act in activities:
        by_rank.setdefault(rank[act], []).append(act)
    for r, acts in by_rank.items():
        for i, act in enumerate(sorted(acts)):
            pos[act] = (r * 3.0, -i * 1.6 + (len(acts) - 1) * 0.8)

    for ot_idx, ot in enumerate(object_types):




        targets = [a2 for a1, a2, o, c in edges if a1 == start_nodes[ot] and o == ot]
        min_rank = min((rank.get(t, 0) for t in targets), default=0)
        avg_y = sum(pos[t][1] for t in targets) / len(targets) if targets else 0.0
        pos[start_nodes[ot]] = (min_rank * 3.0 - 2.8, avg_y + 1.6 + ot_idx * 1.3)

        sources = [a1 for a1, a2, o, c in edges if a2 == end_nodes[ot] and o == ot]
        max_r = max((rank.get(s, 0) for s in sources), default=max_rank)
        avg_y_e = sum(pos[s][1] for s in sources) / len(sources) if sources else 0.0
        pos[end_nodes[ot]] = (max_r * 3.0 + 2.8, avg_y_e + 1.6 + ot_idx * 1.3)

    fig_w = max(10, (max_rank + 1) * 3.2)
    fig_h = max(6, max((len(v) for v in by_rank.values()), default=1) * 1.8 + 3)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    color_map = {}
    for ot in object_types:
        _color_for(ot, color_map)

    node_boxes = {}
    for act in activities:
        x, y = pos[act]
        count = _activity_event_count(ocdfg, act)
        w, h = 2.2, 0.9
        box = FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.05,rounding_size=0.08",
            linewidth=1.2, edgecolor="black", facecolor="#e6e6fa", zorder=3,
        )
        ax.add_patch(box)
        ax.text(x, y, f"{act}\nE={count}", ha="center", va="center", fontsize=9, zorder=4)
        node_boxes[act] = (x, y, w, h)

    for ot in object_types:
        base_color = color_map[ot]
        for tag, nodes in (("start", start_nodes), ("end", end_nodes)):
            n = nodes[ot]
            if n not in pos:
                continue
            x, y = pos[n]




            fill = base_color if tag == "start" else _lighten(base_color, 0.8)
            e = Ellipse((x, y), 1.7, 0.8, facecolor=fill, edgecolor="black", zorder=3)
            ax.add_patch(e)
            ax.text(x, y, ot, ha="center", va="center", fontsize=8, zorder=4,
                     color="black" if tag == "start" else base_color, fontweight="bold")
            if tag == "end":
                ax.plot([x - 0.5, x + 0.5], [y - 0.3, y - 0.3], color=base_color, linewidth=1.0, zorder=4)
            node_boxes[n] = (x, y, 1.7, 0.8)



    from collections import defaultdict
    grouped = defaultdict(list)
    for a1, a2, ot, c in edges:
        grouped[(a1, a2)].append((ot, c))

    for (a1, a2), items in grouped.items():
        if a1 not in pos or a2 not in pos:
            continue
        x1, y1 = pos[a1]
        x2, y2 = pos[a2]
        n = len(items)
        for i, (ot, c) in enumerate(items):
            color = color_map[ot]
            if a1 == a2:
                rad = 0.6 + 0.3 * i
                arrow = FancyArrowPatch(
                    (x1 + 0.3, y1 + 0.35), (x1 - 0.3, y1 + 0.35),
                    connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                    color=color, linewidth=1.4, zorder=2, mutation_scale=12,
                )
                lx, ly = x1, y1 + 0.9 + rad * 0.5
            else:
                rad = (i - (n - 1) / 2) * 0.18
                arrow = FancyArrowPatch(
                    (x1, y1), (x2, y2),
                    connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                    color=color, linewidth=1.4, zorder=2, mutation_scale=14,
                    shrinkA=20, shrinkB=20,
                )
                lx, ly = (x1 + x2) / 2, (y1 + y2) / 2 + rad * 2.0 + 0.15
            ax.add_patch(arrow)
            ax.text(lx, ly, f"{ot} EC={c}", ha="center", va="center", fontsize=7,
                     color=color, zorder=5,
                     bbox=dict(boxstyle="round,pad=0.1", facecolor="white", edgecolor="none", alpha=0.75))

    all_x = [p[0] for p in pos.values()]
    all_y = [p[1] for p in pos.values()]
    ax.set_xlim(min(all_x) - 2, max(all_x) + 2)
    ax.set_ylim(min(all_y) - 2, max(all_y) + 2)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(output_png_path, dpi=150)
    plt.close(fig)
