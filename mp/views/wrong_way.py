from flask import Blueprint, render_template, Response, request, jsonify
import cv2
import numpy as np
from ultralytics import YOLO
import time
import os
import threading

# Blueprint 객체 생성
bp = Blueprint(
    "wrong_way",
    __name__,
    url_prefix="/wrong_way",
    template_folder="templates",
    static_folder="static"
)

# ------------------------------------------------------------
# 1. 설정 및 초기화
# ------------------------------------------------------------
VIDEO_PATH = "mp/static/videos/wrongway.mp4" 
MODEL_PATH = "yolo11n.pt"
VEHICLE_CLASSES = [2, 3, 5, 7]

# 글로벌 상태 관리
IS_RUNNING = False
IS_DETECTED = False
latest_frame = None
background_thread = None

# 학습 관련 변수
is_trained = False
init_counter = 0
INIT_FRAMES = 45 
lane_direction_map = {}
violation_history = {} # 오탐지 방지용 ID별 위반 카운트

model = YOLO(MODEL_PATH)

# ------------------------------------------------------------
# 2. 백그라운드 분석 로직
# ------------------------------------------------------------
def process_wrong_way_background(video_source):
    global IS_RUNNING, IS_DETECTED, latest_frame, is_trained, init_counter, lane_direction_map, violation_history
    
    cap = cv2.VideoCapture(video_source)
    prev_gray = None
    
    # 분석 시작 시 변수 초기화
    is_trained = False
    init_counter = 0
    lane_direction_map = {}
    violation_history = {}

    print(f"[INFO] 역주행 감지 스레드 시작: {video_source}")

    try:
        while IS_RUNNING and cap.isOpened():
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # 무한 반복
                continue
            
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            annotated_frame = frame.copy()

            # YOLOv11 추적(Tracking) 모드 사용
            results = model.track(frame, persist=True, classes=VEHICLE_CLASSES, conf=0.3, verbose=False)

            if prev_gray is not None:
                # 광학 흐름(Optical Flow) 계산
                flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                
                any_wrong_way = False # 현재 프레임에 역주행이 한 대라도 있는지 확인

                for r in results:
                    if r.boxes is None or r.boxes.id is None: continue
                    
                    for box in r.boxes:
                        obj_id = int(box.id[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        center_x = (x1 + x2) // 2
                        
                        roi_flow_y = flow[y1:y2, x1:x2, 1]
                        if roi_flow_y.size == 0: continue
                        v_y = np.median(roi_flow_y)

                        # --- [STEP 1] 학습 단계 ---
                        if not is_trained:
                            section = center_x // (w // 10)
                            if section not in lane_direction_map: lane_direction_map[section] = []
                            lane_direction_map[section].append(v_y)
                            cv2.putText(annotated_frame, f"Learning Flow... {init_counter}/{INIT_FRAMES}", 
                                        (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

                        # --- [STEP 2] 감지 단계 ---
                        else:
                            section = center_x // (w // 10)
                            if section in lane_direction_map:
                                normal_dir = lane_direction_map[section]
                                
                                # 역주행 의심 조건 (방향 반대 및 속도 임계값)
                                if normal_dir * v_y < -2.0:
                                    violation_history[obj_id] = violation_history.get(obj_id, 0) + 1
                                else:
                                    violation_history[obj_id] = max(0, violation_history.get(obj_id, 0) - 1)

                                # 10프레임 이상 연속 위반 시 최종 판단
                                if violation_history.get(obj_id, 0) > 10:
                                    any_wrong_way = True
                                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                                    cv2.putText(annotated_frame, f"WRONG WAY! ID:{obj_id}", (x1, y1-10), 
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                else:
                                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 1)

                IS_DETECTED = any_wrong_way # 글로벌 상태 업데이트

                # 학습 카운터 관리
                if not is_trained:
                    init_counter += 1
                    if init_counter >= INIT_FRAMES:
                        for s in lane_direction_map:
                            lane_direction_map[s] = np.mean(lane_direction_map[s])
                        is_trained = True
                        print("[INFO] 학습 완료: 도로 방향 맵핑 성공")

            latest_frame = annotated_frame
            prev_gray = gray.copy()
            time.sleep(0.01) # CPU 부하 조절

    finally:
        cap.release()
        IS_RUNNING = False
        print("[INFO] 역주행 감지 스레드 종료")

# ------------------------------------------------------------
# 3. 라우트 정의
# ------------------------------------------------------------
def generate_frames():
    global latest_frame
    while IS_RUNNING:
        if latest_frame is not None:
            ret, buffer = cv2.imencode('.jpg', latest_frame)
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + 
                       buffer.tobytes() + b'\r\n')
        time.sleep(0.03)

@bp.route('/')
def index():
    return render_template('wrong_way.html')

@bp.route('/toggle_wrong_way', methods=['POST'])
def toggle_wrong_way():
    global IS_RUNNING, background_thread
    IS_RUNNING = not IS_RUNNING
    
    if IS_RUNNING:
        if background_thread is None or not background_thread.is_alive():
            background_thread = threading.Thread(
                target=process_wrong_way_background, 
                args=(VIDEO_PATH,),
                daemon=True
            )
            background_thread.start()
    
    return jsonify({'status': 'ON' if IS_RUNNING else 'OFF'})

@bp.route('/check_status')
def check_status():
    return jsonify({
        'is_running': IS_RUNNING,
        'is_detected': IS_DETECTED,
        'is_trained': is_trained
    })

@bp.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')