"""
Step 2 — 통계 기반 이상탐지 (z-score + 이동평균)
---------------------------------------------------
Step 1에서 만든 data/telemetry.csv 를 읽어서,
고정 임계값이 아니라 '데이터 흐름에서 벗어나는 정도'로 이상을 탐지합니다.

핵심 아이디어:
    이동평균(rolling mean)   = 최근 WINDOW분 동안의 정상 기준선
    이동표준편차(rolling std) = 최근의 정상적인 흔들림 폭
    z-score = (현재값 - 이동평균) / 이동표준편차
    |z| > THRESHOLD 이면 '정상 범위에서 통계적으로 많이 벗어남' = 이상

실행:
    python src\\02_statistical_anomaly.py
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "outputs"
OUT_DIR.mkdir(exist_ok=True)

WINDOW = 30        # 이동평균 창 크기(분). 직전 30분을 '정상 기준'으로 삼음
THRESHOLD = 3.0    # |z-score|가 이 값보다 크면 이상으로 판단 (3시그마 규칙)

# z-score로 감시할 상태값들
SIGNALS = ["battery_temperature", "communication_signal", "solar_panel_output"]


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """각 시점의 값이, '바로 직전 window개'의 평균/표준편차 대비 몇 시그마 떨어져 있는지.

    shift(1)로 현재값을 창에서 제외 → 이상값이 자기 기준을 오염시키지 않게 한다.
    그래서 이상이 '시작되는 순간'과 '정상으로 돌아오는 순간'을 민감하게 잡는다.
    """
    past = series.shift(1)
    mean = past.rolling(window, min_periods=window).mean()
    std = past.rolling(window, min_periods=window).std()
    return (series - mean) / std


def main() -> None:
    csv_path = DATA_DIR / "telemetry.csv"
    if not csv_path.exists():
        raise SystemExit(
            f"[!] {csv_path} 가 없습니다. 먼저 Step 1을 실행하세요:\n"
            f"    python src\\01_simulate_telemetry.py"
        )

    print("[1/4] telemetry.csv 를 읽습니다...")
    df = pd.read_csv(csv_path, parse_dates=["time"])
    print(f"    {len(df)}개 샘플 로드 완료")

    print(f"[2/4] 이동평균(창={WINDOW}분) 기반 z-score 를 계산합니다...")
    df["anomaly"] = False
    for sig in SIGNALS:
        z = rolling_zscore(df[sig], WINDOW)
        df[f"{sig}_z"] = z
        df[f"{sig}_anom"] = z.abs() > THRESHOLD
        df["anomaly"] |= df[f"{sig}_anom"].fillna(False)

    n_anom = int(df["anomaly"].sum())
    print(f"    이상 지점 {n_anom}개 발견 (|z| > {THRESHOLD})")
    for sig in SIGNALS:
        c = int(df[f"{sig}_anom"].fillna(False).sum())
        print(f"      - {sig:22s}: {c}개")

    # 이상 구간만 따로 저장(관제 로그용)
    anom_path = DATA_DIR / "anomalies_zscore.csv"
    cols = ["time"] + SIGNALS + [f"{s}_z" for s in SIGNALS]
    df.loc[df["anomaly"], cols].to_csv(anom_path, index=False)
    print(f"[3/4] 이상 로그 저장 → {anom_path}")

    print("[4/4] 대시보드 그래프를 그립니다...")
    fig, axes = plt.subplots(len(SIGNALS), 1, figsize=(11, 9), sharex=True)
    colors = {"battery_temperature": "tab:orange",
              "communication_signal": "tab:blue",
              "solar_panel_output": "tab:green"}
    labels = {"battery_temperature": "Battery Temp (°C)",
              "communication_signal": "Comm Signal",
              "solar_panel_output": "Solar Output (W)"}

    for ax, sig in zip(axes, SIGNALS):
        ax.plot(df["time"], df[sig], color=colors[sig], lw=0.9)
        # 이동평균 ±THRESHOLD*std 정상 밴드 표시 (탐지와 동일한 '직전 구간' 기준)
        past = df[sig].shift(1)
        mean = past.rolling(WINDOW, min_periods=WINDOW).mean()
        std = past.rolling(WINDOW, min_periods=WINDOW).std()
        ax.fill_between(df["time"], mean - THRESHOLD * std, mean + THRESHOLD * std,
                        color="gray", alpha=0.15, label="normal band")
        a = df[df[f"{sig}_anom"].fillna(False)]
        ax.scatter(a["time"], a[sig], color="red", s=14, zorder=3, label="anomaly")
        ax.set_ylabel(labels[sig])
        ax.legend(loc="upper left", fontsize=8)

    axes[-1].set_xlabel("Time")
    fig.suptitle(f"SAT-01 — Statistical Anomaly Detection (z-score, window={WINDOW})",
                 fontsize=13)
    fig.tight_layout()

    out_path = OUT_DIR / "telemetry_zscore.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"    완료! 그래프 저장 → {out_path}")
    print("    회색 밴드 = 통계적 정상 범위, 빨간 점 = 그 범위를 벗어난 이상 지점")
    plt.show()


if __name__ == "__main__":
    main()
