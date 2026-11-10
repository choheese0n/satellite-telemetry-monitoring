"""
telemetry_core — 공용 로직 (Step 3 API / Step 4 대시보드가 함께 사용)
---------------------------------------------------------------
CSV 읽기 + z-score 이동평균 이상탐지를 한 곳에 모아 중복을 없앴습니다.
"""

from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
CSV_PATH = DATA_DIR / "telemetry.csv"

SAT_ID = "SAT-01"                 # 현재 위성 1대
WINDOW = 30                       # 이동평균 창(분)
THRESHOLD = 3.0                   # |z-score| 임계값
SIGNALS = ["battery_temperature", "communication_signal", "solar_panel_output"]


def rolling_zscore(series: pd.Series, window: int = WINDOW) -> pd.Series:
    """직전 window개 대비 몇 시그마 벗어났는지 (현재값은 창에서 제외)."""
    past = series.shift(1)
    mean = past.rolling(window, min_periods=window).mean()
    std = past.rolling(window, min_periods=window).std()
    return (series - mean) / std


def load_telemetry() -> pd.DataFrame:
    """CSV를 읽고 각 신호의 z-score와 이상 플래그를 계산해 반환."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"{CSV_PATH} 가 없습니다. 먼저 Step 1을 실행하세요: "
            f"python src\\01_simulate_telemetry.py"
        )
    df = pd.read_csv(CSV_PATH, parse_dates=["time"])
    df["anomaly"] = False
    for sig in SIGNALS:
        z = rolling_zscore(df[sig])
        df[f"{sig}_z"] = z
        df["anomaly"] |= (z.abs() > THRESHOLD).fillna(False)
    return df
