"""
Step 6 — Kafka Consumer (스트림 → 실시간 이상탐지)
---------------------------------------------------
'satellite.telemetry' 토픽에서 메시지를 받아, 들어오는 즉시
스트리밍 z-score(직전 WINDOW개 기준)로 이상을 판정하고 경보를 출력합니다.

CSV 전체를 한 번에 보는 Step 2와 달리, 여기서는 '도착하는 순간'에
과거 버퍼만으로 판단합니다 — 진짜 관제처럼요.

사전 준비:
    docker compose up -d        # Kafka 브로커
    (다른 터미널에서) python src\\06_producer.py

실행:
    python src\\06_consumer.py
"""

import json
from collections import deque

from kafka import KafkaConsumer

from telemetry_core import SIGNALS, WINDOW, THRESHOLD

BOOTSTRAP = "localhost:9092"
TOPIC = "satellite.telemetry"


def streaming_zscore(buf: deque, x: float):
    """직전 버퍼(현재값 제외) 기준 z-score. 버퍼가 아직 작으면 None."""
    if len(buf) < WINDOW:
        return None
    import statistics
    mean = statistics.fmean(buf)
    std = statistics.pstdev(buf)
    if std == 0:
        return 0.0
    return (x - mean) / std


def main() -> None:
    print(f"[Consumer] Kafka({BOOTSTRAP}) 연결, 토픽 '{TOPIC}' 구독...")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        auto_offset_reset="earliest",     # 처음부터 읽기
        group_id="satellite-monitor",
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    print("[Consumer] 대기 중... (Producer가 보내면 실시간 판정, Ctrl+C 중지)")

    buffers = {sig: deque(maxlen=WINDOW) for sig in SIGNALS}
    n_msg = n_anom = 0

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
                print(f"🔴 ANOMALY @ {msg['time']}  →  " + ", ".join(flagged))
            elif n_msg % 200 == 0:
                print(f"   ...{n_msg}개 처리 (이상 {n_anom}개), 최근 {msg['time']} 정상")
    except KeyboardInterrupt:
        print(f"\n[Consumer] 중지됨 — 총 {n_msg}개 처리, 이상 {n_anom}개 탐지")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
