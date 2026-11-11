"""
Step 6 — Kafka Consumer (스트림 → 실시간 이상탐지 → PostgreSQL 저장)
---------------------------------------------------
'satellite.telemetry' 토픽에서 메시지를 받아, 들어오는 즉시
스트리밍 z-score(직전 WINDOW개 기준)로 이상을 판정하고,
탐지된 이상은 PostgreSQL의 anomaly_events 테이블에 저장합니다.

  풀 파이프라인:  Producer → Kafka → (이 Consumer: 이상탐지) → PostgreSQL

CSV 전체를 한 번에 보는 Step 2와 달리, 여기서는 '도착하는 순간'에
과거 버퍼만으로 판단합니다 — 진짜 관제처럼요.

사전 준비:
    docker compose up -d                 # Kafka 브로커
    $env:PGPASSWORD = "DB비밀번호"        # PostgreSQL 저장용 (Step 5와 동일)
    (다른 터미널에서) python src\\06_producer.py

실행:
    python src\\06_consumer.py            # 이상탐지 + DB 저장
    python src\\06_consumer.py --no-db    # DB 없이 콘솔 경보만
"""

import argparse
import json
import statistics
from collections import deque

from kafka import KafkaConsumer

from telemetry_core import SIGNALS, WINDOW, THRESHOLD
from db import ensure_database, get_engine, ensure_anomaly_table, insert_anomaly

BOOTSTRAP = "localhost:9092"
TOPIC = "satellite.telemetry"


def streaming_zscore(buf: deque, x: float):
    """직전 버퍼(현재값 제외) 기준 z-score. 버퍼가 아직 작으면 None."""
    if len(buf) < WINDOW:
        return None
    mean = statistics.fmean(buf)
    std = statistics.pstdev(buf)
    if std == 0:
        return 0.0
    return (x - mean) / std


def connect_db():
    """DB 연결을 준비. 실패하면 None을 돌려주고 콘솔 전용으로 계속 진행."""
    try:
        ensure_database()
        engine = get_engine()
        ensure_anomaly_table(engine)
        print("[Consumer] PostgreSQL 연결 OK — 이상을 anomaly_events 테이블에 저장합니다.")
        return engine
    except Exception as e:
        print("[Consumer][경고] PostgreSQL 연결 실패 → 콘솔 경보만 합니다.")
        print(f"           ($env:PGPASSWORD 설정 확인)  원인: {type(e).__name__}: {e}")
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db", action="store_true", help="DB 저장 없이 콘솔 경보만")
    args = ap.parse_args()

    engine = None if args.no_db else connect_db()

    print(f"[Consumer] Kafka({BOOTSTRAP}) 연결, 토픽 '{TOPIC}' 구독...")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        auto_offset_reset="earliest",
        group_id="satellite-monitor",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    print("[Consumer] 대기 중... (Producer가 보내면 실시간 판정, Ctrl+C 중지)")

    buffers = {sig: deque(maxlen=WINDOW) for sig in SIGNALS}
    n_msg = n_anom = n_saved = 0

    try:
        for record in consumer:
            msg = record.value
            n_msg += 1

            flagged = []
            for sig in SIGNALS:
                x = msg[sig]
                z = streaming_zscore(buffers[sig], x)
                if z is not None and abs(z) > THRESHOLD:
                    flagged.append(f"{sig}(z={z:+.1f})")
                buffers[sig].append(x)      # 판정 후 버퍼에 추가

            if flagged:
                n_anom += 1
                reason = ", ".join(flagged)
                print(f"🔴 ANOMALY @ {msg['time']}  →  {reason}")
                if engine is not None:
                    try:
                        insert_anomaly(
                            engine,
                            satellite=msg["satellite"],
                            event_time=msg["time"],
                            flagged=reason,
                            values={s: msg[s] for s in SIGNALS},
                        )
                        n_saved += 1
                    except Exception as e:
                        print(f"   [DB 저장 실패] {type(e).__name__}: {e}")
            elif n_msg % 200 == 0:
                print(f"   ...{n_msg}개 처리 (이상 {n_anom}개, DB저장 {n_saved}개), "
                      f"최근 {msg['time']} 정상")
    except KeyboardInterrupt:
        print(f"\n[Consumer] 중지됨 — 총 {n_msg}개 처리, 이상 {n_anom}개 탐지, "
              f"DB 저장 {n_saved}개")
        if engine is not None:
            print("   확인:  SELECT * FROM anomaly_events ORDER BY event_time LIMIT 10;")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
