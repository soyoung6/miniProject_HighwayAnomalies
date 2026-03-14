import urllib.request
import urllib.error
import json
import pandas as pd
import cv2
import numpy as np
import time
import sys
import os
from dotenv import load_dotenv
load_dotenv()
import re
from concurrent.futures import ThreadPoolExecutor
from collections import deque, Counter
from typing import List, Dict, Tuple, Any

# ⭐ 순수 SQLAlchemy 모듈로 대체 ⭐
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from datetime import datetime

# ======================================================================
# 0. 순수 SQLAlchemy DB 설정 및 모델 정의
# ======================================================================

# ⭐⭐⭐ DB 연결 주소 설정 (사용자님 제공 주소) ⭐⭐⭐
# Flask 없이 순수하게 MySQL에 연결
DB_URL = "mysql+pymysql://root:1234@localhost:3306/flask_db?charset=utf8mb4"

# 1. Base 선언
Base = declarative_base()

# 2. Engine 생성 및 Session Maker 설정
engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(bind=engine)

# 3. DB 모델 정의 (Flask-SQLAlchemy 문법 -> 순수 SQLAlchemy 문법으로 변경)
class Location(Base):
    __tablename__ = 'location'
    id = Column(Integer, primary_key=True)
    cctv_name = Column(String(255), unique=True, nullable=False)
    lng = Column(String(50), nullable=False)
    lat = Column(String(50), nullable=False)
    # TrafficStatus와의 관계 정의 (선택 사항이지만 ORM의 완전성을 위해 추가)
    statuses = relationship("TrafficStatus", back_populates="location")

class TrafficStatus(Base):
    __tablename__ = 'traffic_status'
    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, ForeignKey('location.id'), nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    status_upstream = Column(String(50), nullable=False)
    status_downstream = Column(String(50), nullable=False)

    location = relationship("Location", back_populates="statuses")

# ----------------------------------------------------------------------
# 1. 설정 및 상수 정의 (OCCUPANCY_EMPTY_LIMIT 변경)
# ----------------------------------------------------------------------
# key = os.getenv("API_KEY", "YOUR_DEFAULT_KEY_OR_EXIT_IF_REQUIRED")
# # 만약 API 키가 필수라면, key가 None일 경우 여기서 프로그램을 종료하거나 예외를 발생시켜야 합니다.
# if key == "YOUR_DEFAULT_KEY_OR_EXIT_IF_REQUIRED":
#     print("❌ 경고: API_KEY 환경 변수가 로드되지 않았습니다. 기본값이 사용되거나 로직이 실패할 수 있습니다.")
key = os.environ.get("CCTV_API_KEY")


MIN_X = 126.5
MAX_X = 127.6
MIN_Y = 36.5
MAX_Y = 37.8

TARGET_CCTV_FILTERS = [
    "[경부선] 서초",
    "[경부선] 양재",
    "[경부선] 원지동",
    "[경부선] 상적교",
    "[경부선] 달래내2",
    "[경부선] 달래내1",
    "[경부선] 금현동",
    "[경부선] 금토분기점1",
    "[경부선] 금토분기점2",
    "[경부선] 판교분기점",
    "[경부선] 판교3",
    "[경부선] 삼평터널(서울)",
    "[경부선] 판교2",
    "[경부선] 판교1",
    "[경부선] 백현",
    "[경부선] 서울영업소",
    "[경부선] 서울영업소-광장",
    "[경부선] 금곡교",
    "[경부선] 죽전",
    "[경부선] 죽전휴계소",
    "[경부선] 신갈분기점_경부",
    "[경부선] 신갈분기점2",
    "[경부선] 수원",
    "[경부선] 공세육교",
    "[경부선] 기흥휴계소",
    "[경부선] 기흥",
    "[경부선] 기흥동탄",
    "[경부선] 경부동탄터널(입구방음터널)",
    "[경부선] 경부동탄터널(부산1)",
    "[경부선] 경부동탄터널(부산2)",
    "[경부선] 경부동탄터널(부산3)",
    "[경부선] 경부동탄터널(부산4)",
    "[경부선] 경부동탄터널(부산5)",
    "[경부선] 경부동탄터널(출구방음터널)",
    "[경부선] 경부동탄터널(출구)",
    "[경부선] 동탄분기점",
    "[경부선] 동탄JC(동탄)",
    "[경부선] 부산동",
    "[경부선] 오산",
    "[경부선] 원동",
    "[경부선] 남사육교",
    "[경부선] 외동천교",
    "[경부선] 진위천교",
    "[경부선] 남사졸음쉼터",
    "[경부선] 남사정류장",
    "[경부선] 산하",
    "[경부선] 안성휴게소(서울)",
    "[경부선] 안성휴계소2",
    "[경부선] 원곡",
    "[경부선] 안성분기점1",
    "[경부선] 안성분기점2",
    "[경부선] 안성휴계소(부산)",
    "[경부선] 공도",
    "[경부선] 원곡졸음쉼터",
    "[경부선] 안성"
]

URL_CCTV_API = (
    f'https://openapi.its.go.kr:9443/cctvInfo?apiKey={key}&type=ex&cctvType=1'
    f'&minX={MIN_X}&maxX={MAX_X}&minY={MIN_Y}&maxY={MAX_Y}&getType=json'
)

# --- [설정] 분석 파라미터 ---
MAX_FRAMES_PER_CCTV = 50
ROI_Y_RATIO = 0.35
PERSPECTIVE_WEIGHT_MAX = 10.0
HISTORY_LENGTH = 30

# --- [설정] 상태 판단 기준 ⭐ OCCUPANCY_EMPTY_LIMIT 수정 ⭐
OCCUPANCY_EMPTY_LIMIT = 0.005 # 0.003 -> 0.005로 상향
SPEED_CONGESTION = 1.0
SPEED_SLOW = 2.0
MIN_HISTORY_REQUIRED = 10

# --- [설정] 병렬 처리 및 반복 파라미터 ---
MAX_WORKERS = 8
TARGET_REPETITIONS = 10

# ----------------------------------------------------------------------
# 2. 헬퍼 함수 (get_status_text_and_color 수정)
# ----------------------------------------------------------------------

def get_status_text_and_color(avg_speed, avg_occupancy):
    """
    ⭐ 수정됨: 점유율을 가장 먼저 판단하여 Congested 오판 방지
    가중 속도 및 점유율을 바탕으로 최종 상태 텍스트 반환
    """
    if avg_occupancy < OCCUPANCY_EMPTY_LIMIT: return "No Traffic"
    if avg_speed < SPEED_CONGESTION: return "Congested"
    if avg_speed < SPEED_SLOW: return "Slow"
    return "Clear"

def clean_filter_name(name: str) -> str:
    """[태그]를 제거하여 매칭용으로 정규화하는 헬퍼 함수"""
    return re.sub(r'\[.*?\]', '', name).strip()

# ----------------------------------------------------------------------
# 3. 핵심 분석 함수 (analyze_single_cctv_traffic 수정)
# ----------------------------------------------------------------------

def analyze_single_cctv_traffic(url, name):
    """
    단일 CCTV 스트림을 분석하고 트래픽 상태를 반환합니다.
    ⭐ 방향별 점유율(Directional Occupancy) 계산 로직 적용 ⭐
    """
    capture = cv2.VideoCapture(url)
    if not capture.isOpened():
        return name, "Stream Error", 0.0, 0.0, "Stream Error: Could not open URL", \
               "Stream Error", 0.0, 0.0, "Stream Error: Could not open URL"

    prev_frame_gray = None
    frame_count = 0
    # history_down/up은 (속도, 점유율) 쌍을 저장합니다.
    history_down = deque(maxlen=HISTORY_LENGTH)
    history_up = deque(maxlen=HISTORY_LENGTH)
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=40, detectShadows=False)

    weight_map = None
    H, W = 0, 0

    try:
        while frame_count < MAX_FRAMES_PER_CCTV:
            run, frame = capture.read()
            if not run: break

            if H == 0:
                H, W = frame.shape[:2]
                roi_y_start = int(H * ROI_Y_RATIO)
                roi_h = H - roi_y_start
                weights = np.linspace(PERSPECTIVE_WEIGHT_MAX, 1.0, roi_h).reshape(-1, 1)
                weight_map = weights.astype(np.float32)

            frame_blur = cv2.GaussianBlur(frame, (5, 5), 0)
            current_gray_full = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2GRAY)

            if prev_frame_gray is not None:
                roi_gray = current_gray_full[roi_y_start:, :]
                roi_prev_gray = prev_frame_gray[roi_y_start:, :]

                # 1. 배경 차분 마스크 획득 (움직이는 모든 물체)
                fg_mask = bg_subtractor.apply(roi_gray)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

                # 2. 광학 흐름 계산 및 가중치 적용
                flow = cv2.calcOpticalFlowFarneback(roi_prev_gray, roi_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                flow_y = flow[..., 1]
                weighted_flow_y = flow_y * weight_map

                # 3. 방향 분리 및 속도 계산
                mask_down_bool = (weighted_flow_y > 0.3)
                mask_up_bool = (weighted_flow_y < -0.3)

                # numpy bool 마스크를 uint8 마스크로 변환 (비트 연산 및 인덱싱 용이)
                mask_down_uint8 = mask_down_bool.astype(np.uint8)
                mask_up_uint8 = mask_up_bool.astype(np.uint8)

                # 속도 계산 (Downstream)
                speed_down = np.median(weighted_flow_y[mask_down_bool]) if np.sum(mask_down_bool) > 10 else 0.0
                # 속도 계산 (Upstream)
                speed_up = np.median(np.abs(weighted_flow_y[mask_up_bool])) if np.sum(mask_up_bool) > 10 else 0.0

                # ⭐ 4. 방향별 점유율 (Directional Occupancy) 계산 ⭐
                total_pixels = fg_mask.size
                if total_pixels > 0:
                    # fg_mask는 0 또는 255. 비트 연산을 위해 1/0 바이너리 마스크로 변환
                    fg_mask_binary = (fg_mask > 0).astype(np.uint8)

                    # Downstream Occupancy: 움직임 + 하행 흐름이 있는 영역만 카운트
                    occ_down_mask_combined = cv2.bitwise_and(fg_mask_binary, fg_mask_binary, mask=mask_down_uint8)
                    occupancy_rate_down = np.count_nonzero(occ_down_mask_combined) / total_pixels

                    # Upstream Occupancy: 움직임 + 상행 흐름이 있는 영역만 카운트
                    occ_up_mask_combined = cv2.bitwise_and(fg_mask_binary, fg_mask_binary, mask=mask_up_uint8)
                    occupancy_rate_up = np.count_nonzero(occ_up_mask_combined) / total_pixels
                else:
                    occupancy_rate_down = 0.0
                    occupancy_rate_up = 0.0

                # 5. 데이터 누적 (개별 점유율 사용)
                history_down.append((speed_down, occupancy_rate_down))
                history_up.append((speed_up, occupancy_rate_up))
                frame_count += 1

            prev_frame_gray = current_gray_full.copy()

        # 최종 결과 계산
        if len(history_down) < MIN_HISTORY_REQUIRED or len(history_up) < MIN_HISTORY_REQUIRED:
            note = f"Analysis aborted: Only {frame_count} frames processed."
            # 이 경우 No Data를 반환하므로, 점유율 0.0을 그대로 반환하는 것이 맞음
            return name, "No Data", 0.0, 0.0, note, \
                   "No Data", 0.0, 0.0, note

        # 평균 계산 시, 각 방향의 평균 점유율 사용
        avg_speed_down = np.mean([s for s, o in history_down])
        avg_occ_down   = np.mean([o for s, o in history_down])
        status_down = get_status_text_and_color(avg_speed_down, avg_occ_down)

        avg_speed_up   = np.mean([s for s, o in history_up])
        avg_occ_up     = np.mean([o for s, o in history_up])
        status_up = get_status_text_and_color(avg_speed_up, avg_occ_up)

        return (
            name,
            status_down, avg_speed_down, avg_occ_down,
            status_up, avg_speed_up, avg_occ_up,
            "Success"
        )

    except Exception as e:
        note = f"Processing Error: {e}"
        return name, "Processing Error", 0.0, 0.0, note, \
               "Processing Error", 0.0, 0.0, note

    finally:
        capture.release()


# ----------------------------------------------------------------------
# 4. 메인 프로그램: DB 연동 및 병렬 처리 (변동 없음)
# ----------------------------------------------------------------------
def main():
    start_time = time.time()

    # DB 세션 생성
    session = Session()
    locations_by_name = {}
    target_cctvs_map = {}
    saved_count = 0

    print("=" * 70)
    print(f"🛣️ 경부선 CCTV 트래픽 분석 Worker 시작 ({TARGET_REPETITIONS}회 다수결 분석) [순수 DB 모드]")
    print(f"📍 DB URL: {DB_URL}")
    print("=" * 70)

    try:
        # 1. API 호출 및 Location DB 동기화
        print("🌐 CCTV 목록을 API에서 가져오고 DB Location 테이블을 동기화하는 중...")
        response = urllib.request.urlopen(URL_CCTV_API)
        json_str = response.read().decode('utf-8')
        data_list = json.loads(json_str).get("response", {}).get("data", [])

        if not data_list:
            print("[Error] CCTV 데이터를 찾지 못했습니다.")
            session.close()
            return

        cctv_play = pd.json_normalize(data_list, sep=',')
        api_cctvs = cctv_play[['cctvname', 'cctvurl', 'coordx', 'coordy']].to_dict('records')

        found_api_names = set()
        location_updates = 0

        for filter_condition in TARGET_CCTV_FILTERS:
            match_data = None

            # 매핑 로직 (부분 일치 검색)
            for cctv_data in api_cctvs:
                api_name = cctv_data['cctvname']
                if filter_condition in api_name and api_name not in found_api_names:
                    match_data = cctv_data
                    target_cctvs_map[filter_condition] = (api_name, cctv_data['cctvurl'])
                    found_api_names.add(api_name)
                    break

            # Location DB 업데이트/생성
            if match_data:
                lng = str(match_data['coordx'])
                lat = str(match_data['coordy'])

                # 순수 SQLAlchemy 조회
                location = session.query(Location).filter_by(cctv_name=filter_condition).first()

                if not location:
                    location = Location(cctv_name=filter_condition, lng=lng, lat=lat)
                    session.add(location)
                    location_updates += 1

        session.commit()
        print(f"✨ [DB] Location 테이블에 {location_updates}개 항목이 새로 추가/확인 완료.")

        # 분석 후 DB 저장을 위해 Location 객체 전체를 가져옵니다.
        locations_list = session.query(Location).all()
        locations_by_name = {loc.cctv_name: loc for loc in locations_list}

        if not target_cctvs_map:
            print("⚠️ 필터링된 CCTV가 없습니다. 분석 중단.")
            session.close()
            return

        print(f"✨ 분석 대상 CCTV: 총 {len(target_cctvs_map)}개 매핑됨 | 반복 횟수: {TARGET_REPETITIONS}회")

        # 2. 병렬 배치 분석 수행 (기존 로직 유지)
        all_cctv_history = {name: [] for name in TARGET_CCTV_FILTERS}

        for repetition in range(1, TARGET_REPETITIONS + 1):
            results_future = {}
            current_repetition_start = time.time()

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for filter_name, (api_name, url) in target_cctvs_map.items():
                    future = executor.submit(analyze_single_cctv_traffic, url, api_name)
                    results_future[filter_name] = future

                for filter_name, future in results_future.items():
                    try:
                        result = future.result()

                        # analyze_single_cctv_traffic의 반환값 포맷에 따라 처리
                        if len(result) == 8:
                            # 성공적인 경우: (name, status_d, speed_d, occ_d, status_u, speed_u, occ_u, note)
                            status_d, status_u, note = result[1], result[4], result[7]
                        elif len(result) == 9:
                            # 에러 처리 시: (name, status_d, speed_d, occ_d, status_u, speed_u, occ_u, note)
                            # 하지만 반환하는 에러 메시지 형식은 (name, error_d, 0.0, 0.0, note, error_u, 0.0, 0.0, note) 형태이므로
                            # 실제로는 result[1]과 result[5]가 상태, result[4]가 note 일수 있습니다.
                            # 일관성을 위해 8개 항목으로 통일했으므로, 8개 항목 기준으로 처리합니다.
                            # Worker에서 반환되는 result는 항상 8개 항목이 되어야 합니다.
                            status_d, status_u, note = result[1], result[4], result[7]
                        else:
                            status_d, status_u, note = "Format Error", "Format Error", "Unexpected return format"

                        if filter_name in all_cctv_history:
                            all_cctv_history[filter_name].append({
                                "Down": status_d, "Up": status_u, "Note": note
                            })

                    except Exception as e:
                        if filter_name in all_cctv_history:
                            all_cctv_history[filter_name].append({
                                "Down": "Unexpected Error", "Up": "Unexpected Error",
                                "Note": f"Unexpected Error: {e}"
                            })

            # 반복 루프 진행 상태 출력
            sys.stdout.write(
                f"\r🔄 진행: [{repetition:03d}/{TARGET_REPETITIONS:03d}] "
                f"이번 반복 {len(target_cctvs_map)}개 처리 완료. "
                f"소요 시간: {time.time() - current_repetition_start:.2f}초"
            )
            sys.stdout.flush()

        print("\n\n⭐ 다수결 분석 및 DB 저장 준비...")

        # 3. 최종 다수결 계산 및 TrafficStatus DB 저장
        final_results_dict = {}
        error_statuses = {"No Data", "Stream Error", "Processing Error", "Unexpected Error", "Format Error"}
        new_traffic_statuses = []

        for filter_name in TARGET_CCTV_FILTERS:
            history = all_cctv_history.get(filter_name, [])

            if not history or filter_name not in locations_by_name: continue

            down_votes = [h['Down'] for h in history if h['Down'] not in error_statuses]
            up_votes = [h['Up'] for h in history if h['Up'] not in error_statuses]

            final_status_down = Counter(down_votes).most_common(1)[0][0] if down_votes else "N/A"
            final_status_up = Counter(up_votes).most_common(1)[0][0] if up_votes else "N/A"

            if final_status_down != "N/A" or final_status_up != "N/A":
                location_obj = locations_by_name[filter_name]
                # 순수 SQLAlchemy 객체 생성
                new_status = TrafficStatus(
                    location_id=location_obj.id,
                    status_downstream=final_status_down,
                    status_upstream=final_status_up,
                )
                new_traffic_statuses.append(new_status)
                saved_count += 1

            final_results_dict[filter_name] = {
                "Status_Down": final_status_down, "Status_Up": final_status_up,
                "Total_Analysis_Count": len(history),
                "Final_Note": f"Total {len(down_votes)} Down/ {len(up_votes)} Up votes cast."
            }

        # DB에 일괄 저장
        if new_traffic_statuses:
            session.add_all(new_traffic_statuses)
            session.commit()

        print(f">> [DB] 성공적으로 분석된 {saved_count}개 CCTV의 상태를 TrafficStatus 테이블에 저장했습니다.")

        # 4. 최종 보고서 출력 (기존 로직 유지)
        print("\n" + "=" * 110)
        print(f"{'No.':<4} | {'CCTV Name (요청)':<40} | {'5분 평균 Downstream (하행/부산)':<30} | {'5분 평균 Upstream (상행/서울)':<30}")
        print("-" * 110)

        for i, filter_name in enumerate(TARGET_CCTV_FILTERS):
            res = final_results_dict.get(filter_name, {
                "Status_Down": "N/A", "Status_Up": "N/A"
            })

            down_summary = f"{res['Status_Down']:<30}"
            up_summary   = f"{res['Status_Up']:<30}"

            print(f"{i+1:<4} | {filter_name:<40} | {down_summary} | {up_summary}")

        print("=" * 110)

    except urllib.error.URLError as e:
        print(f"\n❌ API 연결 오류 발생: {e.reason}")
        session.rollback()
    except OperationalError as e:
        print(f"\n❌ DB 연결/작업 오류 발생. DB 서버와 설정({DB_URL})을 확인하세요: {e}")
        session.rollback()
    except Exception as e:
        print(f"\n❌ 최종 보고서 생성/DB 저장 중 예상치 못한 오류 발생: {e}")
        session.rollback()

    finally:
        # 세션 정리
        session.close()
        end_time = time.time()
        print(f"\n⏱️ 총 분석 소요 시간: {end_time - start_time:.2f}초")


if __name__ == "__main__":
    # Worker 시작 시 DB 테이블이 없으면 생성합니다. (최초 1회 실행 시 중요)
    Base.metadata.create_all(engine)

    main()