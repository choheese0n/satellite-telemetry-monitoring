"""
Step 6 — Kafka Producer (위성 → 스트림)
---------------------------------------------------
data/telemetry.csv 를 한 줄씩 Kafka 토픽 'satellite.telemetry' 로 흘려보냅니다.
실제 위성이 1분마다 상태를 쏘는 것을 '실시간'처럼 재현합니다.

사전 준비:
    docker compose up -d        # Kafka 브로커 실행

실행:
    python src\\06_producer.py            # 기본 속도
    python src\\06_producer.py --delay 0  # 최대한 빠르게
"""

import argparse
import json
import time

import pandas as pd
from kafka import KafkaProducer

from telemetry_core import CSV_PATH, SIGNALS, SAT_ID

BOOTSTRAP = "localhost:9092"
TOPIC = "satellite.telemetry"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.05,
                    help="메시지 사이 지연(초). 0이면 최대 속도")
    ap.add_argument("--loop", action="store_true", help="끝나면 처음부터 반복")
    args = ap.parse_args()

    if not CSV_PATH.exists():
        raise SystemExit(f"[!] {CSV_PATH} 없음. 먼저 Step 1 실행: python src\\01_simulate_telemetry.py")

    df = pd.read_csv(CSV_PATH, parse_dates=["time"])

    print(f"[Producer] Kafka({BOOTSTRAP}) 연결 중...")
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    print(f"[Producer] 토픽 '{TOPIC}' 으로 전송 시작 (Ctrl+C 로 중지)")

    sent = 0
    try:
        while True:
            for _, row in df.iterrows():
                msg = {
                    "satellite": SAT_ID,
                    "time": row["time"].isoformat(),
                    **{sig: round(float(row[sig]), 3) for sig in SIGNALS},
                }
                producer.send(TOPIC, msg)
                sent += 1
                if sent % 100 == 0:
                    print(f"    {sent}개 전송... 최근: {msg['time']} "
                          f"batt={msg['battery_temperature']}°C")
                if args.delay > 0:
                    time.sleep(args.delay)
            if not args.loop:
                break
    except KeyboardInterrupt:
        print("\n[Producer] 중지됨")
    finally:
        producer.flush()
        producer.close()
        print(f"[Producer] 총 {sent}개 전송 완료")


if __name__ == "__main__":
    main()
