"""
Step 1 — 위성 Telemetry 시뮬레이션 + 기본 이상탐지
---------------------------------------------------
가상 위성 'SAT-01'의 24시간 상태 데이터를 1분 간격으로 만들고,
중간에 이상 이벤트(배터리 과열 등)를 섞은 뒤 임계값으로 이상 지점을 탐지합니다.

실행:
    python src\\01_simulate_telemetry.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "outputs"
DATA_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

rng = np.random.default_rng(42)   # 결과 재현용 고정 시드
N = 24 * 60                        # 24시간 * 60분 = 1440개 샘플

def main() -> None:
    print("[1/4] 위성 SAT-01의 24시간 telemetry를 생성합니다...")
    time = pd.date_range("2026-01-01", periods=N, freq="min")

    # 정상 상태값 (평균 주변에서 약간씩 흔들림)
    battery_temperature = 30 + 2 * np.sin(np.linspace(0, 6, N)) + rng.normal(0, 0.4, N)
    battery_voltage = 7.4 + rng.normal(0, 0.05, N)
    solar_panel_output = np.clip(80 + 15 * np.sin(np.linspace(0, 6, N)), 0, None) + rng.normal(0, 2, N)
    comm_signal = 95 + rng.normal(0, 1.5, N)

    # 이상 이벤트 주입: 배터리 과열 + 통신 급락
    battery_temperature[700:730] += np.linspace(0, 25, 30)   # 서서히 과열
    comm_signal[1000:1010] -= 60                              # 통신 급락

    df = pd.DataFrame({
        "time": time,
        "battery_temperature": battery_temperature,
        "battery_voltage": battery_voltage,
        "solar_panel_output": solar_panel_output,
        "communication_signal": comm_signal,
    })

    csv_path = DATA_DIR / "telemetry.csv"
    df.to_csv(csv_path, index=False)
    print(f"    원본 저장 → {csv_path}")

    # [2] 임계값(threshold) 기반 이상탐지
    print("[2/4] 임계값으로 이상 상태를 탐지합니다...")
    df["anomaly"] = (
        (df["battery_temperature"] > 40) |      # 배터리 40도 초과 = 과열
        (df["communication_signal"] < 70)       # 통신 70 미만 = 약함
    )
    n_anom = int(df["anomaly"].sum())
    print(f"    이상 지점 {n_anom}개 발견")

    # [3] 그래프
    print("[3/4] 대시보드 그래프를 그립니다...")
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    anom = df[df["anomaly"]]

    axes[0].plot(df["time"], df["battery_temperature"], color="tab:orange")
    axes[0].scatter(anom["time"], anom["battery_temperature"], color="red", s=12, zorder=3, label="anomaly")
    axes[0].axhline(40, ls="--", color="gray", lw=0.8)
    axes[0].set_ylabel("Battery Temp (°C)"); axes[0].legend(loc="upper left")

    axes[1].plot(df["time"], df["communication_signal"], color="tab:blue")
    axes[1].scatter(anom["time"], anom["communication_signal"], color="red", s=12, zorder=3)
    axes[1].axhline(70, ls="--", color="gray", lw=0.8)
    axes[1].set_ylabel("Comm Signal")

    axes[2].plot(df["time"], df["solar_panel_output"], color="tab:green")
    axes[2].set_ylabel("Solar Output (W)"); axes[2].set_xlabel("Time")

    fig.suptitle("SAT-01 Mission Control — Telemetry Monitoring", fontsize=13)
    fig.tight_layout()

    out_path = OUT_DIR / "telemetry_dashboard.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[4/4] 완료! 그래프 저장 → {out_path}")
    print("빨간 점이 이상(과열/통신불량) 지점입니다.")
    plt.show()


if __name__ == "__main__":
    main()
