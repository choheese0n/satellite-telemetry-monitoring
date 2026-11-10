"""
Step 4 — 웹 대시보드 (Mission Control 스타일)
---------------------------------------------------
FastAPI가 대시보드 HTML을 제공하고, 그 페이지가 /api/history 를 불러
24시간치 telemetry를 '실시간처럼' 흐르는 그래프로 보여줍니다.
빨간 점 = Step 2의 z-score 이상탐지 결과.

실행:
    python src\\04_dashboard.py
확인(브라우저):
    http://127.0.0.1:8011/
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from telemetry_core import SAT_ID, SIGNALS, load_telemetry

PORT = 8011                                  # API(8010), TESS(8000)와 겹치지 않게
HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"

TELEMETRY: Optional[pd.DataFrame] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global TELEMETRY
    TELEMETRY = load_telemetry()
    print(f"[Dashboard] telemetry 로드: {len(TELEMETRY)}개, "
          f"이상 {int(TELEMETRY['anomaly'].sum())}개 → http://127.0.0.1:{PORT}/")
    yield


app = FastAPI(title="Satellite Mission Control Dashboard", lifespan=lifespan)


def _get_df() -> pd.DataFrame:
    if TELEMETRY is None:
        raise HTTPException(status_code=503, detail="telemetry 로드 전입니다.")
    return TELEMETRY


@app.get("/")
def dashboard():
    """대시보드 HTML 페이지."""
    return FileResponse(HTML_PATH, media_type="text/html")


@app.get("/api/history")
def api_history():
    """대시보드가 그릴 전체 시계열(시간·신호값·이상여부)."""
    df = _get_df()
    return {
        "satellite": SAT_ID,
        "signals": SIGNALS,
        "count": len(df),
        "series": [
            {
                "time": row["time"].isoformat(),
                **{sig: round(float(row[sig]), 3) for sig in SIGNALS},
                "anomaly": bool(row["anomaly"]),
            }
            for _, row in df.iterrows()
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
