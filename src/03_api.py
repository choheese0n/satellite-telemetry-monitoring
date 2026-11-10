"""
Step 3 — FastAPI 로 위성 상태 API 만들기
---------------------------------------------------
Step 1에서 만든 data/telemetry.csv 를 읽어서, 위성 상태를 웹 API(JSON)로 제공합니다.
Step 2의 z-score 통계 이상탐지를 그대로 적용해 '지금 이상인지'를 함께 알려줍니다.

실행:
    uvicorn src.03_api:app --reload
    # 모듈명이 숫자로 시작해서 import가 안 되면 아래처럼 파일 경로로 실행:
    python src\\03_api.py

확인(브라우저):   ※ 포트 8010 (TESS 프로젝트가 8000을 쓰므로 충돌 방지)
    http://127.0.0.1:8010/docs        ← 자동 생성 API 문서(Swagger)
    http://127.0.0.1:8010/sat/SAT-01/status
    http://127.0.0.1:8010/sat/SAT-01/anomalies
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

PORT = 8010                       # TESS 프로젝트가 8000을 쓰므로 위성은 8010 사용

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
CSV_PATH = DATA_DIR / "telemetry.csv"

SAT_ID = "SAT-01"                 # 지금은 위성 1대만 시뮬레이션
WINDOW = 30                       # Step 2와 동일한 이동평균 창
THRESHOLD = 3.0                   # |z-score| 임계값
SIGNALS = ["battery_temperature", "communication_signal", "solar_panel_output"]


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """직전 window개 대비 몇 시그마 벗어났는지 (현재값은 창에서 제외)."""
    past = series.shift(1)
    mean = past.rolling(window, min_periods=window).mean()
    std = past.rolling(window, min_periods=window).std()
    return (series - mean) / std


def load_telemetry() -> pd.DataFrame:
    """CSV를 읽고 z-score 이상 플래그를 계산해 둔 DataFrame을 반환."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"{CSV_PATH} 가 없습니다. 먼저 Step 1을 실행하세요: "
            f"python src\\01_simulate_telemetry.py"
        )
    df = pd.read_csv(CSV_PATH, parse_dates=["time"])
    df["anomaly"] = False
    for sig in SIGNALS:
        z = rolling_zscore(df[sig], WINDOW)
        df[f"{sig}_z"] = z
        df["anomaly"] |= (z.abs() > THRESHOLD).fillna(False)
    return df


# 서버 시작 시 한 번 로드해서 메모리에 보관
TELEMETRY: Optional[pd.DataFrame] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 telemetry를 메모리에 로드 (요청마다 CSV 다시 안 읽게)."""
    global TELEMETRY
    TELEMETRY = load_telemetry()
    print(f"[API] telemetry 로드 완료: {len(TELEMETRY)}개 샘플, "
          f"이상 {int(TELEMETRY['anomaly'].sum())}개")
    yield


app = FastAPI(
    title="Satellite Telemetry Monitoring API",
    description="가상 위성 SAT-01의 상태(telemetry)와 이상탐지 결과를 제공하는 관제 API",
    version="1.0.0",
    lifespan=lifespan,
)


def _get_df() -> pd.DataFrame:
    if TELEMETRY is None:
        raise HTTPException(status_code=503, detail="telemetry가 아직 로드되지 않았습니다.")
    return TELEMETRY


def _check_sat(sat_id: str) -> None:
    if sat_id != SAT_ID:
        raise HTTPException(status_code=404, detail=f"위성 '{sat_id}'을(를) 찾을 수 없습니다. (사용 가능: {SAT_ID})")


@app.get("/")
def root():
    """API 안내."""
    return {
        "service": "Satellite Telemetry Monitoring API",
        "satellite": SAT_ID,
        "endpoints": [
            f"/sat/{SAT_ID}/status",
            f"/sat/{SAT_ID}/anomalies",
            f"/sat/{SAT_ID}/history?limit=20",
        ],
        "docs": "/docs",
    }


@app.get("/sat/{sat_id}/status")
def get_status(sat_id: str):
    """해당 위성의 '가장 최근' 상태값과 이상 여부를 반환."""
    _check_sat(sat_id)
    df = _get_df()
    last = df.iloc[-1]
    return {
        "satellite": sat_id,
        "time": last["time"].isoformat(),
        "telemetry": {sig: round(float(last[sig]), 3) for sig in SIGNALS},
        "zscore": {sig: (None if pd.isna(last[f"{sig}_z"]) else round(float(last[f"{sig}_z"]), 2))
                   for sig in SIGNALS},
        "anomaly": bool(last["anomaly"]),
        "state": "ANOMALY" if bool(last["anomaly"]) else "NOMINAL",
    }


@app.get("/sat/{sat_id}/anomalies")
def get_anomalies(sat_id: str, limit: int = Query(50, ge=1, le=1000)):
    """탐지된 이상 지점 목록(최근 것부터)."""
    _check_sat(sat_id)
    df = _get_df()
    anom = df[df["anomaly"]].sort_values("time", ascending=False).head(limit)
    items = []
    for _, row in anom.iterrows():
        items.append({
            "time": row["time"].isoformat(),
            "telemetry": {sig: round(float(row[sig]), 3) for sig in SIGNALS},
            "zscore": {sig: (None if pd.isna(row[f"{sig}_z"]) else round(float(row[f"{sig}_z"]), 2))
                       for sig in SIGNALS},
        })
    return {
        "satellite": sat_id,
        "total_anomalies": int(df["anomaly"].sum()),
        "returned": len(items),
        "anomalies": items,
    }


@app.get("/sat/{sat_id}/history")
def get_history(sat_id: str, limit: int = Query(20, ge=1, le=1440)):
    """최근 N개 상태값 시계열(대시보드용)."""
    _check_sat(sat_id)
    df = _get_df()
    recent = df.tail(limit)
    return {
        "satellite": sat_id,
        "count": len(recent),
        "series": [
            {
                "time": row["time"].isoformat(),
                **{sig: round(float(row[sig]), 3) for sig in SIGNALS},
                "anomaly": bool(row["anomaly"]),
            }
            for _, row in recent.iterrows()
        ],
    }


if __name__ == "__main__":
    # python src\03_api.py 로도 바로 실행되게 함 (숫자 시작 모듈명 import 회피)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
