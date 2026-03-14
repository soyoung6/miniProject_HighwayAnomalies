from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from traffic_analyzer import Location, TrafficStatus, Base

app = Flask(__name__)
CORS(app)  # CORS 허용

# DB 연결
DB_URL = "mysql+pymysql://root:1234@localhost:3306/flask_db?charset=utf8mb4"
engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(bind=engine)


# 상태 매핑 함수
def map_status_to_frontend(status):
    """Python 상태를 JavaScript 형식으로 변환"""
    mapping = {
        "Clear": "smooth",
        "Slow": "slow",
        "Congested": "congested",
        "No Traffic": "smooth",
        "N/A": "smooth"
    }
    return mapping.get(status, "smooth")


@app.route('/api/traffic', methods=['GET'])
def get_traffic():
    """최신 교통 상태 반환 (Downstream 기준)"""
    session = Session()
    try:
        # 각 location의 가장 최신 TrafficStatus 조회 (5분 이내)
        five_minutes_ago = datetime.now() - timedelta(minutes=5)

        results = []
        locations = session.query(Location).all()

        for loc in locations:
            # 가장 최신 상태 조회
            latest_status = session.query(TrafficStatus) \
                .filter(TrafficStatus.location_id == loc.id) \
                .filter(TrafficStatus.timestamp >= five_minutes_ago) \
                .order_by(desc(TrafficStatus.timestamp)) \
                .first()

            if latest_status:
                results.append({
                    "name": loc.cctv_name,
                    "status": map_status_to_frontend(latest_status.status_downstream),
                    "status_raw": latest_status.status_downstream,
                    "timestamp": latest_status.timestamp.isoformat()
                })
            else:
                # 데이터 없으면 기본값
                results.append({
                    "name": loc.cctv_name,
                    "status": "smooth",
                    "status_raw": "No Data",
                    "timestamp": None
                })

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        session.close()


@app.route('/api/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)