# traffic_analysis/traffic_bp.py

from flask import Blueprint, render_template, Response, request
import urllib.request
import os
import urllib.error
import json
import pandas as pd
import cv2
import numpy as np
import time
from collections import deque
import sys
import urllib.parse # URL 디코딩을 위해 추가

# Blueprint 객체 생성
bp = Blueprint(
    "traffic",
    __name__,
    url_prefix="/traffic",
    template_folder="templates",
    static_folder="static"
)

# ----------------------------------------------------------------------
# 1. 설정 및 상수 정의
# ----------------------------------------------------------------------
key = os.environ.get("CCTV_API_KEY")

# --- [추가] 카메라 이동 감지 설정 ---
CAMERA_MOVE_THRESHOLD = 20.0    # 20px 이상 움직이면 카메라 이동으로 간주
PAUSE_DURATION = 3.0            # 이동 감지 시 3초간 분석 중단

# 🌐 API 검색 범위
MIN_X, MAX_X, MIN_Y, MAX_Y = 126.5, 127.6, 36.8, 37.8

# CCTV 필터링 키워드
TARGET_CCTV_FILTERS = [
    "[경부선] 서초", "[경부선] 양재", "[경부선] 원지동", "[경부선] 상적교",
    "[경부선] 달래내2", "[경부선] 달래내1", "[경부선] 금현동", "[경부선] 금토분기점1",
    "[경부선] 금토분기점2", "[경부선] 판교분기점", "[경부선] 판교3", "[경부선] 삼평터널(서울)",
    "[경부선] 판교2", "[경부선] 판교1", "[경부선] 백현", "[경부선] 서울영업소",
    "[경부선] 서울영업소-광장", "[경부선] 금곡교", "[경부선] 죽전", "[경부선] 죽전휴계소",
    "[경부선] 신갈분기점_경부", "[경부선] 신갈분기점2", "[경부선] 수원", "[경부선] 공세육교",
    "[경부선] 기흥휴계소", "[경부선] 기흥", "[경부선] 기흥동탄",
    "[경부선] 경부동탄터널(입구방음터널)", "[경부선] 경부동탄터널(부산1)", "[경부선] 경부동탄터널(부산2)",
    "[경부선] 경부동탄터널(부산3)", "[경부선] 경부동탄터널(부산4)", "[경부선] 경부동탄터널(부산5)",
    "[경부선] 경부동탄터널(출구방음터널)", "[경부선] 경부동탄터널(출구)",
    "[경부선] 동탄분기점", "[경부선] 동탄JC(동탄)", "[경부선] 부산동", "[경부선] 오산",
    "[경부선] 원동", "[경부선] 남사육교", "[경부선] 외동천교", "[경부선] 진위천교",
    "[경부선] 남사졸음쉼터", "[경부선] 남사정류장", "[경부선] 산하",
    "[경부선] 안성휴게소(서울)", "[경부선] 안성휴계소2", "[경부선] 원곡", "[경부선] 안성분기점1",
    "[경부선] 안성분기점2", "[경부선] 안성휴계소(부산)", "[경부선] 공도",
    "[경부선] 원곡졸음쉼터", "[경부선] 안성"
]

url_cctv_api = (
    f'https://openapi.its.go.kr:9443/cctvInfo?apiKey={key}&type=ex&cctvType=1'
    f'&minX={MIN_X}&maxX={MAX_X}&minY={MIN_Y}&maxY={MAX_Y}&getType=json'
)

ROI_Y_RATIO = 0.35              
PERSPECTIVE_WEIGHT_MAX = 10.0    
HISTORY_LENGTH = 100             
OCCUPANCY_EMPTY_LIMIT = 0.003   
SPEED_CONGESTION = 1.0          
SPEED_SLOW = 2.0                

CCTV_URL_DICT = {}
FILTERED_NAMES = []
IS_INITIALIZED = False

# ----------------------------------------------------------------------
# 2. 헬퍼 함수
# ----------------------------------------------------------------------
def get_status_text_and_color(avg_speed, avg_occupancy):
    if avg_occupancy < OCCUPANCY_EMPTY_LIMIT:
        return "차량 없음 (No Traffic)", (192, 192, 192)
    if avg_speed < SPEED_CONGESTION:
        return "정체 (Congested)", (0, 0, 255)
    if avg_speed < SPEED_SLOW:
        return "서행 (Slow)", (0, 255, 255)
    return "원활 (Clear)", (0, 255, 0)

def draw_text_with_outline(img, text, pos, font_scale, color, thickness):
    x, y = pos
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)

def initialize_cctv_data():
    global CCTV_URL_DICT, FILTERED_NAMES, IS_INITIALIZED
    if IS_INITIALIZED: return
    try:
        response = urllib.request.urlopen(url_cctv_api)
        json_str = response.read().decode('utf-8')
        data_list = json.loads(json_str).get("response", {}).get("data", [])
        cctv_play = pd.json_normalize(data_list, sep=',')
        CCTV_URL_DICT = cctv_play.set_index('cctvname')['cctvurl'].to_dict()
        
        filtered_names = []
        for filter_condition in TARGET_CCTV_FILTERS:
            if filter_condition in CCTV_URL_DICT:
                 filtered_names.append(filter_condition)
            for cctv_name in CCTV_URL_DICT.keys():
                if cctv_name not in filtered_names and filter_condition in cctv_name:
                    filtered_names.append(cctv_name)
        FILTERED_NAMES = filtered_names
        IS_INITIALIZED = True
    except Exception as e:
        print(f"[Error] CCTV 초기화 실패: {e}")

# ----------------------------------------------------------------------
# 3. 비디오 프레임 제너레이터 (이동 감지 로직 추가)
# ----------------------------------------------------------------------
def generate_frames(cctv_url):
    capture = cv2.VideoCapture(cctv_url) 
    if not capture.isOpened(): return

    prev_frame_gray = None
    history_down = deque(maxlen=HISTORY_LENGTH) 
    history_up = deque(maxlen=HISTORY_LENGTH)   
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=40, detectShadows=False)

    # ⭐ [추가] 일시정지 제어 변수
    is_paused = False
    pause_end_time = 0.0
    feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7) 
    lk_params = dict(winSize=(15, 15), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)) 
    
    weight_map = None

    try:
        while capture.isOpened():
            # ⭐ [추가] 일시정지 상태 확인
            if is_paused:
                if time.time() > pause_end_time:
                    is_paused = False
                    prev_frame_gray = None # 상태 초기화
                    history_down.clear()
                    history_up.clear()
                    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=40, detectShadows=False)
                else:
                    run, frame = capture.read()
                    if not run: break
                    draw_text_with_outline(frame, "PAUSED (Camera Moving)", (20, 50), 1, (0, 0, 255), 2)
                    ret, buffer = cv2.imencode('.webp', frame, [int(cv2.IMWRITE_WEBP_QUALITY), 80])
                    yield (b'--frame\r\nContent-Type: image/webp\r\n\r\n' + buffer.tobytes() + b'\r\n')
                    continue

            run, frame = capture.read()
            if not run:
                capture = cv2.VideoCapture(cctv_url)
                continue
            
            annotated_frame = frame.copy()
            frame_blur = cv2.GaussianBlur(frame, (5, 5), 0)
            current_gray_full = cv2.cvtColor(frame_blur, cv2.COLOR_BGR2GRAY)
            H, W = current_gray_full.shape

            if prev_frame_gray is not None:
                # ⭐ [추가] 카메라 이동 감지 로직
                p0 = cv2.goodFeaturesToTrack(prev_frame_gray, mask=None, **feature_params)
                if p0 is not None:
                    p1, st, _ = cv2.calcOpticalFlowPyrLK(prev_frame_gray, current_gray_full, p0, None, **lk_params)
                    if p1 is not None and len(p1[st==1]) > 5:
                        m, _ = cv2.estimateAffine2D(p0[st==1], p1[st==1])
                        if m is not None:
                            move_mag = np.sqrt(m[0, 2]**2 + m[1, 2]**2)
                            if move_mag > CAMERA_MOVE_THRESHOLD:
                                is_paused = True
                                pause_end_time = time.time() + PAUSE_DURATION
                                continue

                # --- 3. ROI 및 분석 로직 (기존 유지) ---
                roi_y_start = int(H * ROI_Y_RATIO)
                roi_h = H - roi_y_start
                if weight_map is None or weight_map.shape[0] != roi_h:
                    weight_map = np.linspace(PERSPECTIVE_WEIGHT_MAX, 1.0, roi_h).reshape(-1, 1).astype(np.float32)

                roi_gray = current_gray_full[roi_y_start:, :]
                roi_prev_gray = prev_frame_gray[roi_y_start:, :]
                
                # 점유율 계산
                fg_mask = bg_subtractor.apply(roi_gray, learningRate=0.005)
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
                occupancy_rate = np.count_nonzero(fg_mask) / fg_mask.size

                # 광학 흐름 계산
                flow = cv2.calcOpticalFlowFarneback(roi_prev_gray, roi_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                weighted_flow_y = flow[..., 1] * weight_map

                # 방향 분리 및 누적
                mask_down = (weighted_flow_y > 0.3) 
                speed_down = np.median(weighted_flow_y[mask_down]) if np.sum(mask_down) > 10 else 0.0
                mask_up = (weighted_flow_y < -0.3)
                speed_up = np.median(np.abs(weighted_flow_y[mask_up])) if np.sum(mask_up) > 10 else 0.0

                history_down.append((speed_down, occupancy_rate))
                history_up.append((speed_up, occupancy_rate))

                if len(history_down) > 10:
                    avg_speed_down = np.mean([s for s, o in history_down])
                    avg_occ_down = np.mean([o for s, o in history_down])
                    avg_speed_up = np.mean([s for s, o in history_up])
                    avg_occ_up = np.mean([o for s, o in history_up])

                    status_down, color_down = get_status_text_and_color(avg_speed_down, avg_occ_down)
                    status_up, color_up = get_status_text_and_color(avg_speed_up, avg_occ_up)
                    
                    cv2.line(annotated_frame, (0, roi_y_start), (W, roi_y_start), (0, 255, 255), 1)
                    draw_text_with_outline(annotated_frame, f"방향 1: {status_down}", (20, 50), 0.8, color_down, 2)
                    draw_text_with_outline(annotated_frame, f"W.Spd:{avg_speed_down:.1f} | 점유율:{avg_occ_down*100:.1f}%", (20, 80), 0.6, (220, 220, 220), 1)
                    draw_text_with_outline(annotated_frame, f"방향 2: {status_up}", (20, 120), 0.8, color_up, 2)
                    draw_text_with_outline(annotated_frame, f"W.Spd:{avg_speed_up:.1f} | 점유율:{avg_occ_up*100:.1f}%", (20, 150), 0.6, (220, 220, 220), 1)
                else:
                    draw_text_with_outline(annotated_frame, f"데이터 수집 중... ({len(history_down)}/{HISTORY_LENGTH})", (20, 50), 1, (255,255,255), 2)

            prev_frame_gray = current_gray_full.copy()

            ret, buffer = cv2.imencode('.jpg', annotated_frame, [int(cv2.IMWRITE_WEBP_QUALITY), 90])
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.03)
    finally:
        capture.release()

# ----------------------------------------------------------------------
# 4. Blueprint 라우트 정의 (기존 유지)
# ----------------------------------------------------------------------
@bp.route('/', methods=['GET', 'POST'])
def index():
    initialize_cctv_data()
    target_name = request.form.get('cctv_name') if request.method == 'POST' else None
    if not target_name and FILTERED_NAMES:
        target_name = FILTERED_NAMES[0]
    target_url = CCTV_URL_DICT.get(target_name)
    return render_template('traffic.html', cctv_names=FILTERED_NAMES, target_name=target_name, target_url=target_url)

@bp.route('/video_feed/<path:cctv_url>')
def video_feed(cctv_url):
    decoded_url = urllib.parse.unquote(cctv_url)
    return Response(generate_frames(decoded_url), mimetype='multipart/x-mixed-replace; boundary=frame')