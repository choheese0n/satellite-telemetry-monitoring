"""
Step 5 — PostgreSQL에 telemetry 저장하기
---------------------------------------------------
CSV(data/telemetry.csv) 대신, 위성 상태 데이터를 PostgreSQL DB에 적재합니다.
이제 데이터가 '파일'이 아니라 'DB'에 쌓여서 SQL로 조회할 수 있게 됩니다.

사전 준비:
    1) PostgreSQL 설치 (README/안내 참고)
    2) PowerShell에서 비밀번호 설정:
         $env:PGPASSWORD = "설치할때_정한_비밀번호"
실행:
    python src\\05_load_to_postgres.py
"""

from sqlalchemy import text

from telemetry_core import load_telemetry, SIGNALS, SAT_ID
from db import get_engine, ensure_database

TABLE = "telemetry"


def main() -> None:
    # 0) 데이터 준비 (z-score 이상 플래그 포함)
    df = load_telemetry()
    cols = ["time"] + SIGNALS + ["anomaly"]
    out = df[cols].copy()
    out.insert(0, "satellite", SAT_ID)     # 위성 id 컬럼 추가

    print("[1/4] 대상 데이터베이스 확인/생성...")
    try:
        ensure_database()
    except Exception as e:
        raise SystemExit(
            "[!] PostgreSQL에 연결하지 못했습니다. 아래를 확인하세요:\n"
            "    - PostgreSQL이 설치되어 서비스가 실행 중인가\n"
            "    - PowerShell에서  $env:PGPASSWORD = \"비밀번호\"  를 설정했는가\n"
            f"    (원본 오류: {type(e).__name__}: {e})"
        )

    engine = get_engine()
    print("[2/4] 연결 테스트...")
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("    연결 성공")

    print(f"[3/4] '{TABLE}' 테이블에 {len(out)}행 적재 (기존 있으면 교체)...")
    out.to_sql(TABLE, engine, if_exists="replace", index=False)
    print("    적재 완료")

    print("[4/4] 저장 결과를 SQL로 확인:")
    with engine.connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        n_anom = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE} WHERE anomaly")).scalar()
        latest = conn.execute(text(
            f"SELECT time, battery_temperature, communication_signal "
            f"FROM {TABLE} ORDER BY time DESC LIMIT 1"
        )).fetchone()
    print(f"    총 {total}행, 이상 {n_anom}행")
    print(f"    최신 레코드: {latest}")
    print("\n이제 psql이나 pgAdmin에서 다음처럼 조회할 수 있어요:")
    print("    SELECT * FROM telemetry WHERE anomaly ORDER BY time LIMIT 10;")


if __name__ == "__main__":
    main()
