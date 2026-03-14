from flask import Blueprint, render_template, Response, request, jsonify
import cv2
from ultralytics import YOLO
import numpy as np
import time
import math
import urllib.parse
import os
import threading

# Blueprint 객체 생성
bp = Blueprint(
    "shoulder_parking",
    __name__,
    url_prefix="/shoulder_parking",
    template_folder="templates",
    static_folder="static"
)

# ----------------------------------------------------------------------
# 1. 설정 및 상수 정의
# ----------------------------------------------------------------------
WARNING_COLOR = (0, 0, 255)
PARKING_THRESHOLD = 5.0  # 5초 이상 머물면 경고
STOP_DISTANCE_THRESHOLD = 3.0  # 정차로 간주할 이동 거리 (3픽셀 미만 이동 시 정차)

# YOLO 모델
model = YOLO("yolo11n.pt")
IS_MODEL_LOADED = True

# 주정차 감지 상태 관리
IS_PARKING_RUNNING = False
IS_PARKING_DETECTED = False
ACTIVE_PARKING_VIDEO = ""
background_thread = None
latest_frame = None  # 최신 프레임 저장

# 영역 좌표 정의
pts1 = np.array([[182, 719], [228, 740], [354, 657], [319, 632]])
pts2 = np.array([[746, 348], [783, 359], [886, 283], [860, 273]])

# ----------------------------------------------------------------------
# 2. 헬퍼 함수
# ----------------------------------------------------------------------
def create_error_frame(message, width=640, height=480):
    """에러 메시지를 표시하는 프레임 생성"""
    error_frame = np.zeros((height, width, 3), dtype=np.uint8)
    error_frame[:] = (40, 40, 40)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    color = (0, 0, 255)
    text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
    text_x = (width - text_size[0]) // 2
    text_y = (height + text_size[1]) // 2
    cv2.putText(error_frame, message, (text_x, text_y),
                font, font_scale, color, thickness, cv2.LINE_AA)
    return error_frame

# ----------------------------------------------------------------------
# 3. 백그라운드 비디오 처리
# ----------------------------------------------------------------------
def process_video_background(video_source):
    """백그라운드에서 비디오 처리 및 감지"""
    global IS_PARKING_DETECTED, IS_PARKING_RUNNING, latest_frame
    
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        print(f"[Error] 비디오 소스를 열 수 없습니다: {video_source}")
        return
    
    track_history = {}
    parking_timer = {}
    
    print("[INFO] 백그라운드 비디오 처리 시작")
    
    try:
        while IS_PARKING_RUNNING and cap.isOpened():
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            # 객체 추적
            results = model.track(frame, persist=True, verbose=False, classes=[2])
            
            # 라인 및 영역 그리기
            cv2.polylines(frame, [pts1], True, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.polylines(frame, [pts2], True, (0, 255, 0), 2, cv2.LINE_AA)
            
            warning_list = []
            fill_pts1 = False
            fill_pts2 = False
            
            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xywh.cpu()
                track_ids = results[0].boxes.id.int().cpu().tolist()
                
                for box, track_id in zip(boxes, track_ids):
                    x, y, w, h = box
                    center_point = (int(x), int(y))
                    
                    is_inside = cv2.pointPolygonTest(pts1, center_point, False)
                    is_inside2 = cv2.pointPolygonTest(pts2, center_point, False)
                    
                    if is_inside >= 0 or is_inside2 >= 0:
                        is_stopped = False
                        if track_id in track_history:
                            prev_p = track_history[track_id]
                            dist = math.sqrt((center_point[0] - prev_p[0])**2 + 
                                        (center_point[1] - prev_p[1])**2)
                            
                            if dist < STOP_DISTANCE_THRESHOLD:
                                is_stopped = True
                        
                        if is_stopped:
                            if track_id not in parking_timer:
                                parking_timer[track_id] = time.time()
                            
                            elapsed_time = time.time() - parking_timer[track_id]
                            
                            if elapsed_time < PARKING_THRESHOLD:
                                cv2.putText(frame, f" {int(elapsed_time)}s", 
                                        (int(x), int(y)-10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                            else:
                                IS_PARKING_DETECTED = True
                                # print(f"[INFO] 불법 주정차 감지! ID:{track_id}, {int(elapsed_time)}초")
                                
                                warning_list.append((track_id, int(elapsed_time)))
                                
                                x1, y1 = int(x - w/2), int(y - h/2)
                                x2, y2 = int(x + w/2), int(y + h/2)
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                                
                                if is_inside >= 0:
                                    fill_pts1 = True
                                if is_inside2 >= 0:
                                    fill_pts2 = True
                        else:
                            if track_id in parking_timer:
                                del parking_timer[track_id]
                    else:
                        if track_id in parking_timer:
                            del parking_timer[track_id]
                        if track_id in track_history:
                            del track_history[track_id]
                    
                    track_history[track_id] = center_point
                    cv2.circle(frame, center_point, 5, (0, 255, 0), -1)
            
            if len(warning_list) == 0:
                IS_PARKING_DETECTED = False
            
            if fill_pts1 or fill_pts2:
                overlay = frame.copy()
                if fill_pts1:
                    cv2.fillPoly(overlay, [pts1], WARNING_COLOR)
                if fill_pts2:
                    cv2.fillPoly(overlay, [pts2], WARNING_COLOR)
                cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
            
            for i, (id_num, sec) in enumerate(warning_list):
                cv2.putText(frame, f"WARNING! ID:{id_num} PARKING ({sec}s)", 
                          (30, 50 + (i * 40)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            
            # 최신 프레임 저장
            latest_frame = frame.copy()
            
            time.sleep(0.03)
            
    finally:
        cap.release()
        print("[INFO] 백그라운드 비디오 처리 종료")

# ----------------------------------------------------------------------
# 4. 비디오 프레임 스트리밍 (모달용)
# ----------------------------------------------------------------------
def generate_frames():
    """최신 프레임을 스트리밍"""
    global latest_frame
    
    while IS_PARKING_RUNNING:
        if latest_frame is not None:
            ret, buffer = cv2.imencode('.jpg', latest_frame, 
                                    [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if ret:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + 
                    buffer.tobytes() + b'\r\n')
        
        time.sleep(0.03)

# ----------------------------------------------------------------------
# 5. Blueprint 라우트 정의
# ----------------------------------------------------------------------
@bp.route('/', methods=['GET', 'POST'])
def index():
    """메인 페이지"""
    video_source = request.form.get('video_source') if request.method == 'POST' else None
    error_message = None
    
    if not video_source:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        default_video = os.path.join(base_dir, "mp", "static", "videos", "suwon1.mp4")
        
        if os.path.exists(default_video):
            video_source = default_video
            print(f"[DEBUG] 비디오 파일 찾음: {video_source}")
        else:
            video_source = "mp/static/videos/suwon1.mp4"
            error_message = f"기본 비디오 파일을 찾을 수 없습니다: {default_video}"
            print(f"[ERROR] {error_message}")
    
    return render_template('shoulder_parking.html', 
                        video_source=video_source,
                        error=error_message)

@bp.route('/toggle_parking', methods=['POST'])
def toggle_parking():
    """주정차 감지 ON/OFF"""
    global IS_PARKING_RUNNING, IS_PARKING_DETECTED, ACTIVE_PARKING_VIDEO, background_thread
    
    IS_PARKING_RUNNING = not IS_PARKING_RUNNING
    
    if not IS_PARKING_RUNNING:
        IS_PARKING_DETECTED = False
        ACTIVE_PARKING_VIDEO = ""
        print("[INFO] 주정차 감지 OFF")
    else:
        # 기본 비디오 소스 설정
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        default_video = os.path.join(base_dir, "mp", "static", "videos", "suwon1.mp4")
        if os.path.exists(default_video):
            ACTIVE_PARKING_VIDEO = "mp/static/videos/suwon1.mp4"
            
            # 백그라운드 스레드 시작
            if background_thread is None or not background_thread.is_alive():
                background_thread = threading.Thread(
                    target=process_video_background, 
                    args=(default_video,),
                    daemon=True
                )
                background_thread.start()
                print("[INFO] 백그라운드 처리 스레드 시작")
    
    return jsonify({
        'status': 'ON' if IS_PARKING_RUNNING else 'OFF'
    })

@bp.route('/check_parking', methods=['GET'])
def check_parking():
    """주정차 감지 상태 확인"""
    return jsonify({
        'is_running': IS_PARKING_RUNNING,
        'parking_detected': IS_PARKING_DETECTED,
        'active_video': ACTIVE_PARKING_VIDEO
    })

@bp.route('/video_feed')
def video_feed():
    """비디오 스트림 엔드포인트 (모달용)"""
    return Response(generate_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame')