import requests
from datetime import datetime
from flask import Blueprint
from mp.models import db, Location, TrafficStatus

bp = Blueprint('traffic_mgmt', __name__)
AUTH_KEY = "8892810932"

def get_full_location_db():
    """친구님의 traffic_finder.py에 있던 좌표 수집 로직 그대로 이식"""
    location_db = {}
    # 1. 영업소(TG)
    try:
        tg_res = requests.get("https://data.ex.co.kr/openapi/locationinfo/locationinfoUnit", 
                             params={"key": AUTH_KEY, "type": "json", "numOfRows": "500"}).json()
        if tg_res.get("code") == "SUCCESS":
            for item in tg_res.get("list", []):
                if "경부" in (item.get("routeName") or ""):
                    name = item.get("unitName", "")
                    location_db[f"{name}TG"] = {"lat": str(item.get('yValue')), "lng": str(item.get('xValue'))}
                    location_db[name] = {"lat": str(item.get('yValue')), "lng": str(item.get('xValue'))}
    except: pass

    # 2. IC/JCT
    try:
        ic_res = requests.get("https://data.ex.co.kr/openapi/locationinfo/locationinfoIc", 
                             params={"key": AUTH_KEY, "type": "json", "routeNo": "0010", "numOfRows": "99"}).json()
        if ic_res.get("code") == "SUCCESS":
            for item in ic_res.get("list", []):
                name = item.get("icName", "")
                coord = {"lat": str(item.get('yValue')), "lng": str(item.get('xValue'))}
                location_db[name] = coord
                if "JCT" in name: location_db[name.replace("JCT", "JC")] = coord
    except: pass

    # 3. 핵심 지점 수동 보정
    location_db.update({
        "서초": {"lat": "37.4832", "lng": "127.0191"},
        "서초IC": {"lat": "37.4832", "lng": "127.0191"},
        "판교JC": {"lat": "37.4058", "lng": "127.0945"},
        "달래내": {"lat": "37.4336", "lng": "127.0544"},
        "양재": {"lat": "37.4632", "lng": "127.0420"},
        "금토": {"lat": "37.4154", "lng": "127.0854"}
    })
    return location_db

def sync_traffic_to_db():
    """실제 DB에 적재하는 함수"""
    print("🚀 [Traffic] 데이터 수집 및 DB 적재 프로세스 시작...")
    loc_db = get_full_location_db()
    
    try:
        traffic_res = requests.get("https://data.ex.co.kr/openapi/odtraffic/trafficAmountByRealtime", 
                                  params={"key": AUTH_KEY, "type": "json"}).json()
    except: return

    if traffic_res.get("code") == "SUCCESS":
        summary = {}
        keywords = ["서초", "양재", "판교", "서울", "신갈", "기흥", "동탄", "오산", "안성"]
        
        for item in traffic_res.get("list", []):
            if item.get("routeNo") == "0010":
                name = item.get("conzoneName", "")
                if any(k in name for k in keywords):
                    speed = int(item.get("speed", -1))
                    if speed <= 0: continue
                    
                    direction = "UP" if item.get("updownTypeCode") == "S" else "DOWN"
                    # 구간별로 속도를 모음
                    if name not in summary:
                        summary[name] = {"UP": [], "DOWN": [], "start": name.split('-')[0]}
                    summary[name][direction].append(speed)

        # DB 저장 로직
        for name, data in summary.items():
            # 1. Location 확인 및 생성
            location = Location.query.filter_by(cctv_name=name).first()
            if not location:
                coord = loc_db.get(data["start"])
                if not coord: continue # 좌표 없으면 저장 안 함
                
                location = Location(
                    cctv_name=name,
                    lat=coord['lat'],
                    lng=coord['lng']
                )
                db.session.add(location)
                db.session.flush()

            # 2. TrafficStatus 생성
            avg_up = sum(data["UP"]) / len(data["UP"]) if data["UP"] else None
            avg_down = sum(data["DOWN"]) / len(data["DOWN"]) if data["DOWN"] else None
            
            def get_stat(s):
                if s is None: return "정보없음"
                return "원활" if s >= 80 else "서행" if s >= 40 else "정체"

            new_status = TrafficStatus(
                location_id=location.id,
                status_upstream=get_stat(avg_up),
                status_downstream=get_stat(avg_down),
                timestamp=datetime.now()
            )
            db.session.add(new_status)

        db.session.commit()
        print(f"✅ [Traffic] {len(summary)}개 구간 업데이트 완료.")

@bp.route('/api/traffic/now')
def get_traffic_api():
    # 현재 저장된 최신 데이터를 JSON으로 주는 API (필요시 사용)
    return {"message": "Success"}


@bp.route('/api/traffic')
def get_traffic_for_map():
    """DB에서 최신 교통상태를 가져와 카카오맵용 JSON 반환"""
    from flask import jsonify
    
    results = []
    locations = Location.query.all()
    
    for loc in locations:
        # 해당 Location의 가장 최근 TrafficStatus 가져오기
        latest = TrafficStatus.query.filter_by(location_id=loc.id)\
            .order_by(TrafficStatus.timestamp.desc()).first()
        
        # 상태 결정 (상행/하행 중 더 나쁜 상태 사용)
        status = "smooth"  # 기본값
        if latest:
            up = latest.status_upstream or ""
            down = latest.status_downstream or ""
            if "정체" in up or "정체" in down:
                status = "congested"
            elif "서행" in up or "서행" in down:
                status = "slow"
        
        try:
            lat = float(loc.lat)
            lng = float(loc.lng)
        except (ValueError, TypeError):
            continue  # 좌표 변환 실패 시 스킵
        
        results.append({
            "name": loc.cctv_name,  # 구간명 (예: "서울TG-판교IC")
            "lat": lat,
            "lng": lng,
            "status": status,
            "status_up": latest.status_upstream if latest else "정보없음",
            "status_down": latest.status_downstream if latest else "정보없음"
        })
    
    return jsonify(results)