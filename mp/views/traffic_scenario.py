from flask import Blueprint, request, jsonify, render_template
import pandas as pd
import numpy as np
from datetime import time

# =============================
# Blueprint
# =============================
bp = Blueprint(
    'traffic_scenario',
    __name__,
    url_prefix='/traffic_scenario'
)

# =============================
# HTML 페이지
# =============================
@bp.route('/traffic_scenario.html')
def traffic_scenario_page():
    return render_template('traffic_scenario.html')

# =============================
# 시간대 정의 (세분화)
# =============================
TIME_ZONES = {
    "출근": (time(7, 0), time(9, 0)),
    "오전": (time(9, 0), time(12, 0)),
    "점심": (time(12, 0), time(14, 0)),
    "오후": (time(14, 0), time(17, 0)),
    "퇴근": (time(17, 0), time(19, 0)),
    "야간": (time(19, 0), time(22, 0)),
}

# =============================
# 혼잡도
# =============================
def congestion_level(v):
    if v < 30:
        return "원활"
    elif v < 60:
        return "보통"
    elif v < 90:
        return "혼잡"
    else:
        return "매우 혼잡"

# =============================
# 더미 데이터 (30분 단위)
# =============================
def make_dummy_prediction(start, end):
    rng = pd.date_range(start, end, freq='30min')
    traffic = []

    for t in rng:
        base = np.random.randint(25, 60)

        if 7 <= t.hour <= 9:
            base += np.random.randint(30, 50)
        if 17 <= t.hour <= 19:
            base += np.random.randint(40, 60)

        traffic.append(base)

    return pd.DataFrame({
        "datetime": rng,
        "traffic": traffic
    })

# =============================
# 시간대 필터
# =============================
def filter_time(df, start, end):
    return df[
        (df["datetime"].dt.time >= start) &
        (df["datetime"].dt.time < end)
    ]

# =============================
# 📊 차트 전용 API (핵심)
# =============================
@bp.route('/chart-data', methods=['POST'])
def chart_data():
    data = request.get_json()

    df = make_dummy_prediction(
        data["start_date"],
        data["end_date"]
    )
    df["datetime"] = pd.to_datetime(df["datetime"])

    labels = df["datetime"].dt.strftime("%H:%M").tolist()

    datasets = {
        "전체": df["traffic"].tolist()
    }

    # 시간대별 데이터셋 생성
    for name, (s, e) in TIME_ZONES.items():
        zdf = filter_time(df, s, e)
        zone_values = [
            row["traffic"] if s <= row["datetime"].time() < e else None
            for _, row in df.iterrows()
        ]
        datasets[name] = zone_values

    return jsonify({
        "labels": labels,
        "datasets": datasets
    })

# =============================
# 📈 상세 분석 API
# =============================
@bp.route('/scenario-analysis', methods=['POST'])
def scenario_analysis():
    data = request.get_json()

    df = make_dummy_prediction(
        data["start_date"],
        data["end_date"]
    )
    df["datetime"] = pd.to_datetime(df["datetime"])

    analysis = {}

    for name, (s, e) in TIME_ZONES.items():
        zdf = filter_time(df, s, e)

        analysis[name] = {
            "avg": round(zdf["traffic"].mean(), 1),
            "max": int(zdf["traffic"].max()),
            "min": int(zdf["traffic"].min()),
            "congestion": congestion_level(zdf["traffic"].mean())
        }

    # 이상치
    mean = df["traffic"].mean()
    std = df["traffic"].std()
    anomalies = df[df["traffic"] > mean + 2 * std]

    return jsonify({
        "overall": {
            "avg": round(mean, 1),
            "max": int(df["traffic"].max()),
            "min": int(df["traffic"].min())
        },
        "zones": analysis,
        "anomalies": [
            {
                "time": r["datetime"].strftime("%H:%M"),
                "traffic": int(r["traffic"])
            } for _, r in anomalies.iterrows()
        ]
    })
