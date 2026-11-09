"""Figure 1–4 (300 dpi PNG + TIFF, 나눔고딕 등록·TrueType 임베드). 범례·축은 영문(투고용).

Fig 1  성인 ICU 분포: 전담전문의 ICU vs 그 외, 점 크기 = 성인 ICU 병상
Fig 2  읍면동별 도로 이동시간: (a) 가장 가까운 성인 ICU, (b) 가장 가까운 전담전문의 ICU (≤30/30–60/60–90/>90분)
Fig 3  60분 미도달 불평등: (a) 연령군별 성인 ICU vs 전담 ICU (b) 재정자립도 5분위 (c) 고령화율 5분위 (전담 ICU, 집중지수 표기)
Fig 4  (a) 2026→2030→2035 전담 ICU 60분 미도달 65세 이상(중위, 막대 끝 = 저위–고위) (b) 정책 대안별 남는 미도달 65세 이상
색: dataviz 기본 팔레트(범주 1 파랑 #2a78d6, 2 주황 #eb6834; 순차 파랑 250/400/550/700), 회색 잉크 체계.
입력: data/raw/admdongkor_ver20261001/*.geojson, data/clean/*, output/scenarios_road.csv, output/policy_road.csv
출력: output/figures/fig{1..4}_*.png/.tif
사용: python -P -X utf8 code/fig_all.py
"""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "code"))  # analyze_equity 재사용
C = ROOT / "data/clean"
OUT = ROOT / "output/figures"
GJ = ROOT / "data/raw/admdongkor_ver20261001/HangJeongDong_ver20261001.geojson"

for f in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf"):
    font_manager.fontManager.addfont(str(ROOT / "assets/fonts" / f))
plt.rcParams.update({
    # 라틴·기호는 Arial(나눔고딕의 '>'·'≤'가 전각 꺾쇠로 찍힘), 한글은 나눔고딕으로 대체
    "font.family": ["Arial", "NanumGothic"], "pdf.fonttype": 42, "ps.fonttype": 42, "axes.unicode_minus": False,
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,  # 2026-11-03: 인쇄 폭에서 8 pt 이상(LRH-WP)
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e", "xtick.color": "#898781", "ytick.color": "#898781",
    "text.color": "#0b0b0b", "figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff",
})
BLUE, ORANGE = "#2a78d6", "#eb6834"
SEQ = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # 순차 파랑 250/400/550/700
INK2, MUTED, GRID, BASE = "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
LAND, OUTLINE = "#f0efec", "#ffffff"
ASPECT = 1 / math.cos(math.radians(36))
SIDO_EN = {"11": "Seoul", "26": "Busan", "27": "Daegu", "28": "Incheon", "30": "Daejeon", "31": "Ulsan", "36": "Sejong",
           "41": "Gyeonggi", "51": "Gangwon", "43": "Chungbuk", "44": "Chungnam", "52": "Jeonbuk", "47": "Gyeongbuk",
           "48": "Gyeongnam", "50": "Jeju", "12": "Jeonnam-Gwangju"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.tif", dpi=300, bbox_inches="tight", pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def load_geo():
    gj = json.loads(GJ.read_text(encoding="utf-8"))
    polys = []  # (adm_cd2, sido, [ring...])
    for f in gj["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = [[(x, y) for x, y, *_ in p[0]] for p in parts]
        polys.append((f["properties"]["adm_cd2"], f["properties"]["sido"], rings))
    return polys


def outlines(polys, keyfun):
    """같은 그룹 안에서 한 번만 나오는 변 = 그룹 경계 (공유 꼭짓점이 같은 위상 일관 경계 가정)."""
    cnt = defaultdict(Counter)
    for code, sido, rings in polys:
        g = keyfun(code, sido)
        for r in rings:
            for a, b in zip(r, r[1:] + r[:1]):
                a2, b2 = (round(a[0], 6), round(a[1], 6)), (round(b[0], 6), round(b[1], 6))
                if a2 != b2:
                    cnt[g][(min(a2, b2), max(a2, b2))] += 1
    segs = []
    for g, c in cnt.items():
        segs += [s for s, n in c.items() if n == 1]
    return segs


def base_map(ax, polys, faces=None, sido_segs=None):
    verts = [r for _, _, rings in polys for r in rings]
    if faces is None:
        fc = [LAND] * len(verts)
    else:
        fc = [faces.get(code, LAND) for code, _, rings in polys for _ in rings]
    ax.add_collection(PolyCollection(verts, facecolors=fc, edgecolors="none", linewidths=0))
    if sido_segs:
        ax.add_collection(LineCollection(sido_segs, colors=OUTLINE if faces else "#ffffff", linewidths=0.6))
        ax.add_collection(LineCollection(sido_segs, colors=BASE, linewidths=0.25))
    ax.set_xlim(124.55, 131.0)
    ax.set_ylim(33.1, 38.65)
    ax.set_aspect(ASPECT)
    ax.axis("off")


def fig1(polys, sido_segs):
    icu = rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"] for r in rd(C / "icu_intensivist_khqa.csv") if r["전담전문의_있음"] == "1"}
    fig, ax = plt.subplots(figsize=(4.2, 5.0))
    base_map(ax, polys, None, sido_segs)
    handles = []
    for grp, col, z, lab in ((False, MUTED, 3, "Adult ICU without a dedicated intensivist"),
                             (True, BLUE, 4, "Adult ICU with a dedicated intensivist")):
        hs = [h for h in icu if (h["암호화요양기호"] in ints) == grp]
        beds = sum(int(h["성인중환자병상수"]) for h in hs)
        ax.scatter([float(h["좌표X_경도"]) for h in hs], [float(h["좌표Y_위도"]) for h in hs],
                   s=[2.2 * math.sqrt(int(h["성인중환자병상수"])) ** 1.6 for h in hs], c=col,
                   alpha=0.85 if grp else 0.7, edgecolors="#ffffff", linewidths=0.35, zorder=z)
        handles.append(Line2D([], [], marker="o", linestyle="none", markersize=6, markerfacecolor=col,
                              markeredgecolor="#ffffff", label=f"{lab} (n={len(hs)}; {beds:,} beds)"))
    fig.legend(handles=handles, loc="lower center", frameon=False, fontsize=8, bbox_to_anchor=(0.5, 0.0))
    sz = [10, 40, 100]
    hs = [ax.scatter([], [], s=2.2 * math.sqrt(b) ** 1.6, c="none", edgecolors=INK2, linewidths=0.6) for b in sz]
    ax.legend(hs, [f"{b} beds" for b in sz], loc="upper left", frameon=False, fontsize=8, title="Adult ICU beds",
              title_fontsize=8, labelspacing=0.9, borderpad=0.2)
    fig.subplots_adjust(bottom=0.08)
    save(fig, "fig1_icu_distribution")


def fig2(polys, sido_segs):
    acc = {r["읍면동코드"]: r for r in rd(C / "access_road_emd.csv")}
    bins = [(30, "≤30 min"), (60, "30–60 min"), (90, "60–90 min"), (1e9, ">90 min")]

    def col(t):
        for (b, _), c in zip(bins, SEQ):
            if t <= b:
                return c

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.4))
    fig.subplots_adjust(wspace=0.02)
    for ax, colname, title in ((axes[0], "ICU_분", "(a) Nearest adult ICU"),
                               (axes[1], "전담ICU_분", "(b) Nearest ICU with a dedicated intensivist")):
        faces = {k: col(float(a[colname])) for k, a in acc.items()}
        base_map(ax, polys, faces, sido_segs)
        ax.set_title(title, loc="left", fontweight="bold")
        pop = sum(int(a["인구"]) for a in acc.values())
        far = sum(int(a["인구"]) for a in acc.values() if float(a[colname]) > 60)
        ax.text(0.98, 0.04, f"Beyond 60 min:\n{far / 1e6:.2f} million ({far / pop:.1%})", transform=ax.transAxes,
                fontsize=8, color=INK2, ha="right", va="bottom")
    handles = [Patch(facecolor=c, edgecolor="none", label=l) for (_, l), c in zip(bins, SEQ)]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8,
               title="Road travel time from administrative-dong representative point", title_fontsize=8,
               bbox_to_anchor=(0.5, 0.0))
    save(fig, "fig2_travel_time_map")


def fig3():
    acc = {r["읍면동코드"]: r for r in rd(C / "access_road_emd.csv")}
    pts = rd(C / "emd_points.csv")
    ages = [k for k in pts[0] if k.endswith("세") or k == "100+"]
    groups = [(f"{10 * i}–{10 * i + 9}", ages[2 * i:2 * i + 2]) for i in range(9)] + [("90+", ages[18:])]
    res = {}
    for lab, cols in groups:
        tot = far_a = far_i = 0
        for p in pts:
            a = acc[p["읍면동코드"]]
            n = sum(int(p[c]) for c in cols)
            tot += n
            far_a += n * (float(a["ICU_분"]) > 60)
            far_i += n * (float(a["전담ICU_분"]) > 60)
        res[lab] = (far_a / tot, far_i / tot)
    fig, (ax, bx, cx) = plt.subplots(1, 3, figsize=(6.95, 2.8), sharey=True,  # 2026-11-03: 저장 폭 ≤180 mm
                                     gridspec_kw={"width_ratios": [2.0, 1.0, 1.0]})
    x = range(len(groups))
    w = 0.38
    ax.bar([i - w / 2 - 0.01 for i in x], [100 * res[g][0] for g, _ in groups], w, color=MUTED, label="Any adult ICU")
    ax.bar([i + w / 2 + 0.01 for i in x], [100 * res[g][1] for g, _ in groups], w, color=BLUE,
           label="ICU with a dedicated intensivist")
    for i, (g, _) in enumerate(groups):
        if g in ("0–9", "40–49", "90+"):
            ax.text(i + w / 2, 100 * res[g][1] + 0.2, f"{100 * res[g][1]:.1f}%", ha="center", fontsize=8, color=INK2)
    # 8 pt에서 가로 라벨이 겹쳐 45° 회전 (2026-11-03)
    ax.set_xticks(list(x), [g for g, _ in groups], fontsize=8, rotation=45, ha="right", rotation_mode="anchor")
    ax.set_xlabel("Age group (years)")
    ax.set_ylabel("Population beyond 60 min (%)")
    ax.set_title("(a) Age", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, loc="upper left")

    # b·c: 시군구 인구가중 5분위 (전담 ICU, 전체 연령) + 집중지수 — analyze_equity와 같은 정의
    import analyze_equity as eq  # noqa: E402
    units = eq_units()
    q_out = {}
    for axx, key, title, xl in ((bx, "fis", "(b) Fiscal self-reliance", "Quintile (Q1 = lowest)"),
                                (cx, "aging", "(c) Population ageing", "Quintile (Q1 = youngest)")):
        q = eq.quint(units, key, ["far", "far65", "o65"])
        vals = [100 * q[k]["far"] / q[k]["pop"] for k in range(5)]
        axx.bar(range(5), vals, 0.6, color=BLUE)
        for k, v in enumerate(vals):
            axx.text(k, v + 0.2, f"{v:.1f}", ha="center", fontsize=8, color=INK2)
        cidx = eq.ci(units, key, "y")
        axx.text(0.03, 0.97, f"CI = {cidx:+.2f}".replace("-", "−"), transform=axx.transAxes, ha="left", va="top",
                 fontsize=8, color=INK2)
        axx.set_xticks(range(5), [f"Q{k + 1}" for k in range(5)], fontsize=8)
        axx.set_xlabel(xl)
        axx.set_title(title, loc="left", fontweight="bold")
        q_out[key] = (vals, cidx)
    for a in (ax, bx, cx):
        a.yaxis.grid(True, color=GRID, linewidth=0.5)
        a.set_axisbelow(True)
        for s in ("top", "right", "left"):
            a.spines[s].set_visible(False)
    fig.tight_layout(w_pad=1.0)
    save(fig, "fig3_inequality_unreached")
    return res, q_out


def eq_units():
    """analyze_equity.main과 같은 시군구 집계 (전담 ICU 60분)."""
    fis = {r["KOSIS코드"]: float(r["재정자립도_2026"]) for r in rd(C / "fiscal_sgg.csv")}
    agg = defaultdict(lambda: defaultdict(float))
    for e in rd(C / "access_road_emd.csv"):
        a = agg[e["시군구코드_KOSIS"]]
        p, o = int(e["인구"]), int(e["65세이상"])
        far = float(e["전담ICU_분"]) > 60
        a["pop"] += p
        a["o65"] += o
        a["far"] += p * far
        a["far65"] += o * far
    return [{"code": k, "pop": a["pop"], "o65": a["o65"], "far": a["far"], "far65": a["far65"],
             "y": a["far"] / a["pop"], "y65": a["far65"] / a["o65"], "fis": fis[k], "aging": a["o65"] / a["pop"]}
            for k, a in agg.items()]


def fig4():
    sc = rd(ROOT / "output/scenarios_road.csv")
    pick = lambda s, y: next(float(r["미도달인구"]) for r in sc if r["시나리오"] == s and r["연도"] == y  # noqa: E731
                             and r["대상"] == "전담ICU" and float(r["컷오프(분)"]) == 60 and r["연령군"] == "65세이상")
    years = ["2026", "2030", "2035"]
    mid = [pick("2026.10 실제", "2026")] + [pick("중위", y) for y in years[1:]]
    lo = [mid[0]] + [pick("저위", y) for y in years[1:]]
    hi = [mid[0]] + [pick("고위", y) for y in years[1:]]
    pol = rd(ROOT / "output/policy_road.csv")
    def prow(name, k=None, goal=None):  # noqa: E306
        for r in pol:
            if r["대안"] == name and (k is None or (r["k"] == str(k) and r["목표"] == goal)):
                return float(r["미도달65세이상"])
    alts = [("Current (2026)", prow("현재")),
            ("All public hospitals (47)", prow("A 공공병원(공립·국립·특수법인) 전부")),
            ("All regional medical centres (26)", prow("B 지방의료원 전부")),
            ("All designated responsible hospitals (36)", prow("D 책임의료기관(2024.3 지정) 전부")),
            ("  …with ICU ≥10 beds (29)", prow("D' 책임의료기관 중 ICU ≥10병상")),
            ("Optimal 5 hospitals (ICU ≥10 beds)", prow("C 탐욕최적(ICU≥10병상)", 5, "65세이상")),
            ("Optimal 10 hospitals (ICU ≥10 beds)", prow("C 탐욕최적(ICU≥10병상)", 10, "65세이상")),
            ("Upper bound: all 220 ICUs", prow("상한: 모든 ICU 강화"))]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.95, 3.0), gridspec_kw={"width_ratios": [1, 1.7]})
    xs = range(3)
    a1.bar(xs, [m / 1e3 for m in mid], 0.55, color=BLUE)
    # 2026은 실제 인구라 범위 없음 → 2030·2035에만 저위–고위 범위
    a1.errorbar([1, 2], [m / 1e3 for m in mid[1:]], yerr=[[(m - l) / 1e3 for m, l in zip(mid[1:], lo[1:])],
                                                          [(h - m) / 1e3 for m, h in zip(mid[1:], hi[1:])]],
                fmt="none", ecolor=INK2, elinewidth=0.8, capsize=3)
    for i, m in enumerate(mid):
        a1.text(i, m / 1e3 * 0.5, f"{m / 1e3:.0f}k", ha="center", color="#ffffff", fontsize=8, fontweight="bold")
    a1.set_xticks(list(xs), years)
    a1.set_ylabel("Residents ≥65 y beyond 60 min (thousands)")
    a1.set_title("(a) Ageing scenarios", loc="left", fontweight="bold")
    a2.barh(range(len(alts)), [v / 1e3 for _, v in alts], 0.6,
            color=[MUTED] + [BLUE] * (len(alts) - 2) + [MUTED])
    for i, (_, v) in enumerate(alts):
        a2.text(v / 1e3 + 8, i, (f"{v / 1e3:.0f}k ({(v - alts[0][1]) / alts[0][1]:+.0%})".replace("-", "−")
                                 if i else f"{v / 1e3:.0f}k"),
                va="center", fontsize=8, color=INK2)
    a2.set_yticks(range(len(alts)), [a for a, _ in alts], fontsize=8)
    a2.invert_yaxis()
    a2.set_xlim(0, alts[0][1] / 1e3 * 1.25)
    a2.set_xlabel("Residents ≥65 y beyond 60 min (thousands)")
    a2.set_title("(b) Policy alternatives (2026 population)", loc="left", fontweight="bold")
    for ax in (a1, a2):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        (ax.yaxis if ax is a1 else ax.xaxis).grid(True, color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
    fig.tight_layout(w_pad=2)
    save(fig, "fig4_scenarios_policy")
    return mid, lo, hi, alts


def main():
    polys = load_geo()
    sido_segs = outlines(polys, lambda code, sido: sido)
    fig1(polys, sido_segs)
    fig2(polys, sido_segs)
    r3, q3 = fig3()
    r4 = fig4()
    lines = ["Fig 3a data (share beyond 60 min: any ICU, intensivist ICU):"] + \
            [f"  {k}: {a:.2%}, {b:.2%}" for k, (a, b) in r3.items()] + [f"Fig 3b/c (quintile %, CI): {q3}",
                                                                        f"Fig 4: {r4}"]
    (OUT / "figure_data_log.txt").write_text("\n".join(map(str, lines)), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
