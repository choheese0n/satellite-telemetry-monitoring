"""
데모용 애니메이션 GIF 생성 (포트폴리오/README용)
---------------------------------------------------
telemetry가 왼→오로 흐르며, z-score 이상 지점이 빨간 점으로 나타나는
'관제 화면'을 애니메이션 GIF(outputs/telemetry_demo.gif)로 저장합니다.

실행:
    python src\\make_demo_gif.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # 창 없이 파일로만 저장
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

from telemetry_core import load_telemetry, SIGNALS

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "outputs" / "telemetry_demo.gif"

WIN = 120        # 화면에 보이는 창(분)
STEP = 10        # 프레임당 전진할 샘플 수 (클수록 짧고 가벼움)
FPS = 18

COLORS = {"battery_temperature": "#ff9f45",
          "communication_signal": "#4aa8ff",
          "solar_panel_output": "#36d399"}
LABELS = {"battery_temperature": "Battery Temp (°C)",
          "communication_signal": "Comm Signal",
          "solar_panel_output": "Solar Output (W)"}


def main() -> None:
    df = load_telemetry()
    frames = list(range(WIN, len(df), STEP))
    print(f"[gif] {len(df)}개 데이터 → {len(frames)}프레임 렌더링...")

    plt.style.use("dark_background")
    fig, axes = plt.subplots(3, 1, figsize=(8, 5), sharex=True)
    fig.suptitle("SAT-01 Mission Control — Live Telemetry", fontsize=12)

    lines, dots = {}, {}
    for ax, sig in zip(axes, SIGNALS):
        (lines[sig],) = ax.plot([], [], color=COLORS[sig], lw=1.5)
        dots[sig] = ax.scatter([], [], color="#ff5069", s=16, zorder=3)
        ax.set_ylabel(LABELS[sig], fontsize=8)
        ax.tick_params(labelsize=7)
    axes[-1].set_xlabel("time (min)", fontsize=8)

    def update(end):
        start = end - WIN
        xs = range(start, end)
        for sig in SIGNALS:
            seg = df[sig].iloc[start:end]
            lines[sig].set_data(list(xs), seg.values)
            amask = df["anomaly"].iloc[start:end].values
            ax = lines[sig].axes
            ax.set_xlim(start, end)
            lo, hi = seg.min(), seg.max()
            pad = (hi - lo) * 0.2 + 1e-6
            ax.set_ylim(lo - pad, hi + pad)
            ax_dots = [(x, y) for x, y, a in zip(xs, seg.values, amask) if a]
            dots[sig].set_offsets(ax_dots if ax_dots else [[None, None]])
        now_anom = bool(df["anomaly"].iloc[end - 1])
        fig.suptitle(
            f"SAT-01 Mission Control — {'● ANOMALY' if now_anom else '● NOMINAL'}  (t={end})",
            fontsize=12, color="#ff5069" if now_anom else "#36d399")
        return list(lines.values()) + list(dots.values())

    anim = FuncAnimation(fig, update, frames=frames, blit=False, interval=1000 / FPS)
    OUT.parent.mkdir(exist_ok=True)
    anim.save(OUT, writer=PillowWriter(fps=FPS))
    size_kb = OUT.stat().st_size / 1024
    print(f"[gif] 저장 완료 → {OUT}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
