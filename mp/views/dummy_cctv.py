# mp/views/dummy_analysis/dummy_bp.py
import os, cv2, time, random, threading
from flask import Blueprint, render_template, Response, jsonify
from ultralytics import YOLO

bp = Blueprint("dummy", __name__, url_prefix="/dummy")

DUMMY_DIR = os.path.join(os.getcwd(), "mp", "static", "videos")
fire_model = YOLO("mp/ml_models/fire.pt")

# 상태 관리 변수
dummy_config = {
    "is_running": False,   # FireLoad 버튼 클릭 여부
    "fire_detected": False,
    "active_video": ""     # 화재가 감지된 비디오 파일명
}

def run_fire_detection():
    global dummy_config
    while True:
        # 버튼이 눌린 상태(is_running == True)일 때만 분석 작동
        if not dummy_config["is_running"]:
            dummy_config["fire_detected"] = False
            time.sleep(1)
            continue

        files = [f for f in os.listdir(DUMMY_DIR) if f.endswith(('.mp4', '.avi'))]
        if not files:
            time.sleep(2)
            continue

        video_name = random.choice(files)
        cap = cv2.VideoCapture(os.path.join(DUMMY_DIR, video_name))
        
        while cap.isOpened() and dummy_config["is_running"]:
            success, frame = cap.read()
            if not success: break

            results = fire_model(frame, stream=True, verbose=False)
            detected = False
            for r in results:
                if len(r.boxes) > 0:
                    for box in r.boxes:
                        if float(box.conf[0]) > 0.6:
                            detected = True
                            break
            
            dummy_config["fire_detected"] = detected
            dummy_config["active_video"] = video_name if detected else ""
            
            # CPU 부하 방지
            time.sleep(0.01)
        cap.release()

# 서버 시작 시 스레드는 대기 상태로 실행 (is_running이 False라 루프만 돔)
def start_fire_thread():
    thread = threading.Thread(target=run_fire_detection, daemon=True)
    thread.start()

# --- API 엔드포인트 ---

@bp.route('/toggle_fireload', methods=['POST'])
def toggle_fireload():
    """FireLoad 버튼 클릭 시 호출"""
    dummy_config["is_running"] = not dummy_config["is_running"]
    status = "ON" if dummy_config["is_running"] else "OFF"
    return jsonify({"status": status})

@bp.route('/check_fire')
def check_status():
    """프론트엔드에서 주기적으로 감지 여부 확인"""
    return jsonify(dummy_config)

@bp.route('/video_feed/<filename>')
def video_feed(filename):
    video_path = os.path.join(DUMMY_DIR, filename)
    
    def generate():
        cap = cv2.VideoCapture(video_path)
        while cap.isOpened():
            # 사용자가 FireLoad를 껐거나, 화재 감지 상태가 아니면 즉시 중단
            if not dummy_config["is_running"] or not dummy_config["fire_detected"]:
                break
                
            ret, frame = cap.read()
            if not ret: break

            # 여기서 한 번 더 검증: 실제로 불이 있는지 확인
            results = fire_model(frame, verbose=False)
            boxes = results[0].boxes
            
            # 🔍 상자가 하나라도 발견되었을 때만 영상을 인코딩해서 보냄
            if len(boxes) > 0 and float(boxes[0].conf[0]) > 0.5:
                annotated_frame = results[0].plot() # 바운딩 박스 그리기
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            else:
                # 불이 없으면 영상을 보내지 않고 아주 짧게 대기 (루프 유지)
                time.sleep(0.1)
                
        cap.release()
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')