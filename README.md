# 🛣️ 경부선 고속도로 스마트 통합 모니터링 시스템

> **Flask 기반 실시간 CCTV 영상 분석 / 이상 상황 감지 / 교통량 예측 / 카카오맵 시각화 통합 플랫폼**

---
## 시연 영상
https://www.youtube.com/playlist?list=PLFvX6ZDAWK0XpmTk89g_MoCdo6KozRtwz
---
## 📋 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [핵심 기능 요약](#2-핵심-기능-요약)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [기술 스택](#4-기술-스택)
5. [데이터베이스 설계](#5-데이터베이스-설계)
6. [주요 모듈 상세 설명 (코드 포함)](#6-주요-모듈-상세-설명-코드-포함)
   - 6-1. 교통 상태 분석 (CCTV 스트림)
   - 6-2. 역주행 감지
   - 6-3. 불법 주정차 감지
   - 6-4. 화재 감지
   - 6-5. 교통량 예측 (XGBoost)
   - 6-6. 교통 관리 & 카카오맵 연동
   - 6-7. 기상 정보 연동
7. [주요 개발 히스토리](#7-주요-개발-히스토리)
8. [설치 및 실행](#8-설치-및-실행)
9. [환경 변수](#9-환경-변수)
10. [프로젝트 구조](#10-프로젝트-구조)
11. [결론 및 향후 과제](#11-결론-및-향후-과제)

---

## 1. 프로젝트 개요

본 프로젝트는 경부선 고속도로(서울 ↔ 안성 구간)를 대상으로, 실시간 CCTV 스트림 영상을 AI/컴퓨터 비전 기술로 분석하여 **교통 혼잡도**, **역주행**, **불법 주정차**, **화재** 등 다양한 이상 상황을 자동으로 감지하고, 예측 모델을 통해 미래 교통량을 예보하는 **스마트 고속도로 통합 모니터링 웹 시스템**입니다.

### 주요 목표

| 목표 | 설명 |
|------|------|
| 🎥 실시간 CCTV 분석 | ITS 공공 API로 경부선 약 55개 지점의 Live 스트림 분석 |
| 🚨 이상 상황 자동 감지 | 역주행·불법주정차·화재를 AI로 즉시 감지 |
| 📈 교통량 예측 | 시계열 ML 모델(XGBoost)로 시간대별 교통량 예측 |
| 🗺️ 지도 시각화 | 카카오맵 API로 구간별 교통 상태를 직관적으로 표시 |
| 🌤️ 기상 연동 | 기상청 초단기실황 API와 연동하여 날씨 정보 제공 |

---

## 2. 핵심 기능 요약

```
경부선 CCTV 스트림 (ITS API)
        │
        ├─ ① 교통 혼잡도 분석  ──→ 원활 / 서행 / 정체 / 차량없음
        ├─ ② 역주행 감지       ──→ YOLO + Optical Flow (학습→감지)
        ├─ ③ 불법 주정차 감지  ──→ YOLO + 다각형 ROI + 타이머
        ├─ ④ 화재 감지         ──→ 전용 학습 fire.pt 모델
        ├─ ⑤ 교통량 예측       ──→ XGBoost (LAG/롤링 피처)
        ├─ ⑥ 카카오맵 연동     ──→ DB 기반 마커 표시
        └─ ⑦ 기상 연동         ──→ 기상청 초단기실황 API
```

---

## 3. 시스템 아키텍처

```
┌────────────────────────────────────────────────────────┐
│                    사용자 브라우저                     │
│         Jinja2 템플릿 / MJPEG 스트림 / REST API        │
└──────────────────────┬─────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼────────────────────────────────┐
│              Flask Application (run.py)               │
│                                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  /traffic│ │/wrong_way│ │/shoulder │ │ /dummy   │  │
│  │(혼잡분석)│ │(역주행)  │  │_parking │  │ (화재)   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │/traffic_ │ │  /api/   │ │  /api/   │               │
│  │ predict  │ │  traffic │ │  weather │               │
│  └──────────┘ └──────────┘ └──────────┘               │
│                                                       │
│  ┌────────────────────────────────────────────────┐   │
│  │         Background Threads (APScheduler)        │  │
│  │  - start_fire_thread()   (화재 감지 상시 대기)  │   │
│  │  - start_cone_thread()   (교통콘 감지 상시 대기)│   │
│  │  - sync_traffic_to_db()  (서버 시작 시 DB 동기화)│  │
│  └────────────────────────────────────────────────┘    │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │        ML 모델 (Ultralytics YOLO / XGBoost)      │  │
│  │  yolo11n.pt  /  cone.pt  /  fire.pt  /  XGB      │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────┬─────────────────────────────────┘
                       │ SQLAlchemy
┌──────────────────────▼─────────────────────────────────┐
│          MySQL DB (flask_db)                           │
│   user / role / user_roles / location / traffic_status │
└────────────────────────────────────────────────────────┘
```

---

## 4. 기술 스택

| 분류 | 기술 |
|------|------|
| **Backend** | Python 3.x, Flask, Flask-Security, Flask-SQLAlchemy, Flask-APScheduler |
| **ML / CV** | OpenCV, Ultralytics YOLOv11, XGBoost, scikit-learn, NumPy, pandas |
| **Database** | MySQL 8.x, SQLAlchemy ORM (Flask 통합 + 순수 SQLAlchemy 이중 사용) |
| **외부 API** | ITS 국가교통정보 CCTV API, 기상청 초단기실황 API, 한국도로공사 OpenAPI, 카카오맵 API |
| **프론트엔드** | Jinja2 템플릿, Vanilla JS, MJPEG Streaming |
| **기타** | python-dotenv, geopy, PyMySQL, openpyxl |

---

## 5. 데이터베이스 설계

### ERD 요약

```
User ──(M:N)──> Role          (Flask-Security 인증)
     user_roles (중간 테이블)

Location ──(1:N)──> TrafficStatus
  · id, cctv_name, lng, lat
                      · id, location_id (FK), timestamp
                      · status_upstream (상행/서울방향 상태)
                      · status_downstream (하행/부산방향 상태)
```

### 핵심 모델 코드 (`mp/models.py`)

```python
class Location(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    cctv_name = db.Column(db.String(255), unique=True, nullable=False)
    lng       = db.Column(db.String(50), nullable=False)
    lat       = db.Column(db.String(50), nullable=False)

class TrafficStatus(db.Model):
    __tablename__ = 'traffic_status'
    id               = db.Column(db.Integer, primary_key=True)
    location_id      = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    timestamp        = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    status_upstream  = db.Column(db.String(50), nullable=False)  # 상행 (서울방향)
    status_downstream= db.Column(db.String(50), nullable=False)  # 하행 (부산방향)

    location = db.relationship(
        'Location',
        backref=db.backref('statuses', lazy='dynamic', order_by=timestamp.desc())
    )
```

> **설계 포인트:** `Location`은 CCTV 지점 마스터 데이터이며, `TrafficStatus`는 분석 결과의 시계열 이력입니다. 카카오맵은 각 Location의 최신 TrafficStatus를 조회하여 마커 색상을 결정합니다.

---

## 6. 주요 모듈 상세 설명 (코드 포함)

---

### 6-1. 교통 혼잡도 분석 (`mp/views/cctv.py` + `mp/services/traffic_analyzer.py`)

**[원리]** ITS 공공 API에서 경부선 CCTV 스트림 URL을 수집한 뒤, OpenCV로 실시간 영상을 프레임 단위로 분석합니다.

#### 분석 파이프라인

```
CCTV 스트림 URL
    │
    ├─ [1] MaxCorners LK 광학 흐름 → 카메라 이동 감지
    │       이동 감지 시 3초 분석 중단 (오탐지 방지)
    │
    ├─ [2] MOG2 배경 차분 → 움직이는 픽셀 마스크 (점유율)
    │
    ├─ [3] Farneback 광학 흐름 → 전체 흐름 벡터 계산
    │       원근 가중치(PERSPECTIVE_WEIGHT_MAX=10) 적용
    │
    ├─ [4] Y축 흐름 방향별 분리
    │       flow_y > 0.3  → 하행 (부산 방향)
    │       flow_y < -0.3 → 상행 (서울 방향)
    │
    └─ [5] 상태 판정 (점유율 우선)
            점유율 < 0.005 → "차량 없음 (No Traffic)"
            가중속도 < 1.0  → "정체 (Congested)"
            가중속도 < 2.0  → "서행 (Slow)"
            그 외           → "원활 (Clear)"
```

#### 핵심 코드

```python
# 상태 판정 함수 (점유율 우선 → 오탐지 방지)
OCCUPANCY_EMPTY_LIMIT = 0.005

def get_status_text_and_color(avg_speed, avg_occupancy):
    if avg_occupancy < OCCUPANCY_EMPTY_LIMIT:
        return "차량 없음 (No Traffic)", (192, 192, 192)
    if avg_speed < SPEED_CONGESTION:           # 1.0
        return "정체 (Congested)", (0, 0, 255)
    if avg_speed < SPEED_SLOW:                 # 2.0
        return "서행 (Slow)", (0, 255, 255)
    return "원활 (Clear)", (0, 255, 0)
```

```python
# 광학 흐름 기반 방향 분리 및 가중 속도 계산
flow = cv2.calcOpticalFlowFarneback(roi_prev_gray, roi_gray,
                                     None, 0.5, 3, 15, 3, 5, 1.2, 0)
weighted_flow_y = flow[..., 1] * weight_map   # 원근 가중치 적용

mask_down = (weighted_flow_y > 0.3)
speed_down = np.median(weighted_flow_y[mask_down]) if np.sum(mask_down) > 10 else 0.0

mask_up = (weighted_flow_y < -0.3)
speed_up = np.median(np.abs(weighted_flow_y[mask_up])) if np.sum(mask_up) > 10 else 0.0
```

#### Batch 분석기 (`traffic_analyzer.py`)

웹 스트리밍 외에도 **일괄 배치 분석 워커**가 존재합니다. 경부선 전체 CCTV를 `ThreadPoolExecutor(max_workers=8)`로 병렬 처리하고, 동일 CCTV를 10회 반복 분석한 뒤 **다수결(Most Voted)** 방식으로 최종 상태를 결정하여 DB에 저장합니다.

```python
# 다수결 최종 상태 결정 후 DB 저장
final_status_down = Counter(down_votes).most_common(1)[0][0] if down_votes else "N/A"
final_status_up   = Counter(up_votes).most_common(1)[0][0]   if up_votes   else "N/A"

new_status = TrafficStatus(
    location_id=location_obj.id,
    status_downstream=final_status_down,
    status_upstream=final_status_up,
)
session.add(new_status)
session.commit()
```

---

### 6-2. 역주행 감지 (`mp/views/wrong_way.py`)

**[원리]** YOLOv11 객체 추적(Track) + Farneback 광학 흐름의 **2단계 학습→감지** 구조입니다.

#### 알고리즘 흐름

```
[STEP 1: 학습 단계 (초기 45 프레임)]
  - YOLO로 차량 추적 (ID 부여)
  - X 좌표를 10개 섹션으로 분할
  - 각 섹션에서 광학 흐름 Y값 누적 → 평균 → "정상 방향 맵" 완성

[STEP 2: 감지 단계]
  - 실시간으로 각 차량의 흐름 방향과 정상 방향 비교
  - normal_dir * v_y < -2.0  → 역주행 의심 (violation_history++)
  - 10 프레임 이상 연속 위반  → 최종 "WRONG WAY" 경보
```

```python
# 역주행 판정 핵심 로직
if normal_dir * v_y < -2.0:
    violation_history[obj_id] = violation_history.get(obj_id, 0) + 1
else:
    violation_history[obj_id] = max(0, violation_history.get(obj_id, 0) - 1)

if violation_history.get(obj_id, 0) > 10:
    cv2.rectangle(annotated_frame, (x1,y1),(x2,y2),(0,0,255), 3)
    cv2.putText(annotated_frame, f"WRONG WAY! ID:{obj_id}", ...)
```

> **설계 포인트:** 단순 방향 비교 대신 `violation_history` 카운터를 두어 일시적 오탐을 필터링합니다. 학습 단계는 최초 45 프레임으로 자동 완료되며, 이후 감지 모드로 자동 전환됩니다.

---

### 6-3. 불법 주정차 감지 (`mp/views/shoulder_parking.py`)

**[원리]** YOLOv11 + 사전 정의된 **다각형 ROI(갓길 영역)** + **타이머** 조합으로 불법 주정차를 판별합니다.

#### 판정 기준

| 조건 | 임계값 |
|------|--------|
| 정차 판단 이동 거리 | 3픽셀 미만 이동 |
| 경고 발령 시간 | 5초 이상 정차 |
| 대상 ROI | 미리 정의된 2개 갓길 다각형 영역 |

```python
# 갓길 영역 정의
pts1 = np.array([[182, 719], [228, 740], [354, 657], [319, 632]])
pts2 = np.array([[746, 348], [783, 359], [886, 283], [860, 273]])

# 영역 내 진입 + 정차 여부 확인
is_inside  = cv2.pointPolygonTest(pts1, center_point, False)
is_inside2 = cv2.pointPolygonTest(pts2, center_point, False)

if is_inside >= 0 or is_inside2 >= 0:
    dist = math.sqrt((center_point[0] - prev_p[0])**2 +
                     (center_point[1] - prev_p[1])**2)
    if dist < STOP_DISTANCE_THRESHOLD:  # 3px 미만 이동 = 정차
        elapsed_time = time.time() - parking_timer[track_id]
        if elapsed_time >= PARKING_THRESHOLD:   # 5초 이상 = 불법주정차
            IS_PARKING_DETECTED = True
            cv2.rectangle(frame, (x1,y1),(x2,y2),(0,0,255), 3)
```

> **백그라운드 처리:** 감지 로직은 별도 `threading.Thread`에서 실행되어 웹 스트리밍이 블로킹되지 않습니다. 최신 분석 프레임은 `latest_frame` 전역 변수를 통해 MJPEG 스트리밍 엔드포인트로 전달됩니다.

---

### 6-4. 화재 감지 (`mp/views/dummy_cctv.py`)

**[원리]** 화재 감지 전용으로 학습된 `fire.pt` YOLO 모델을 사용하여, 비디오 디렉토리 내 파일을 순환 분석합니다.

```python
fire_model = YOLO("mp/ml_models/fire.pt")

def run_fire_detection():
    while True:
        if not dummy_config["is_running"]:
            time.sleep(1); continue

        video_name = random.choice(files)   # 비디오 파일 랜덤 선택
        cap = cv2.VideoCapture(os.path.join(DUMMY_DIR, video_name))

        while cap.isOpened() and dummy_config["is_running"]:
            success, frame = cap.read()
            results = fire_model(frame, stream=True, verbose=False)

            detected = any(float(box.conf[0]) > 0.6
                           for r in results for box in r.boxes)

            dummy_config["fire_detected"] = detected
            dummy_config["active_video"]  = video_name if detected else ""
```

> **신뢰도 임계값:** `conf > 0.6`으로 설정하여 오탐을 줄이고, 화재 감지 시에만 바운딩 박스가 그려진 MJPEG 스트림을 프론트엔드에 전송합니다.

---

### 6-5. 교통량 예측 (`mp/models.py` - TrafficPredictor + `mp/views/traffic_predict.py`)

**[원리]** 과거 시간별 교통량 CSV 데이터를 이용해 XGBoost 모델을 학습하고, 사용자가 지정한 구간과 기간에 대해 미래 교통량을 시간 단위로 예측합니다.

#### 피처 엔지니어링

| 피처 유형 | 항목 |
|-----------|------|
| **시간 피처** | 요일, 시간, 일, 월, 주 |
| **Lag 피처** | lag_1, lag_24, lag_48, lag_72, lag_168 (1주) |
| **롤링 평균** | roll_24 (24시간), roll_168 (1주) |

```python
# 피처 엔지니어링 핵심
for l in [1, 24, 48, 72, 168]:
    df_sec[f'lag_{l}'] = df_sec['y'].shift(l)

df_sec['roll_24']  = df_sec['y'].rolling(24).mean()
df_sec['roll_168'] = df_sec['y'].rolling(168).mean()
```

```python
# XGBoost 학습 설정
XGBOOST_PARAMS = {
    'n_estimators': 800,
    'learning_rate': 0.03,
    'max_depth': 8,
    'subsample': 0.9,
    'colsample_bytree': 0.9,
    'tree_method': 'hist'
}
```

#### 미래 예측 (Auto-Regressive)

```python
def predict_future(self, start_date, end_date):
    future_dates = pd.date_range(start=start_date, end=end_date, freq='H')
    history = self.history.copy()
    preds = []

    for t in future_dates:
        # 시간 피처 + Lag(이전 예측값 재활용) + 롤링 계산
        row = {'요일': t.dayofweek, '시간': t.hour, ...}
        for l in LAG_LIST:
            row[f'lag_{l}'] = history.iloc[-l]
        row['roll_24']  = history.iloc[-24:].mean()
        row['roll_168'] = history.iloc[-168:].mean()

        y_hat = max(0, self.model.predict(X)[0])
        preds.append(y_hat)
        history.loc[t] = y_hat   # 예측값을 다시 히스토리에 추가 (자기회귀)

    return pd.DataFrame({'ds': future_dates, 'pred': preds})
```

> **모델 캐싱:** 동일 구간의 예측 요청이 반복될 경우 재학습을 방지하기 위해 `_models_cache` 딕셔너리에 학습된 모델을 캐싱합니다.

---

### 6-6. 교통 관리 & 카카오맵 연동 (`mp/views/traffic_mgmt.py`)

**[원리]** 한국도로공사 실시간 교통량 API를 호출하여 경부선 구간의 상·하행 평균 속도를 DB에 저장하고, 카카오맵 API로 지도에 마커를 표시합니다.

```python
def get_stat(s):
    """속도를 한글 상태로 변환"""
    if s is None: return "정보없음"
    return "원활" if s >= 80 else "서행" if s >= 40 else "정체"

# 속도 기준
# ≥ 80 km/h → 원활
# ≥ 40 km/h → 서행
# < 40 km/h → 정체
```

```python
# 카카오맵용 API 엔드포인트 (/api/traffic)
@bp.route('/api/traffic')
def get_traffic_for_map():
    locations = Location.query.all()
    for loc in locations:
        latest = TrafficStatus.query.filter_by(location_id=loc.id) \
                    .order_by(TrafficStatus.timestamp.desc()).first()
        status = "smooth"
        if latest:
            if "정체" in (latest.status_upstream or "") or \
               "정체" in (latest.status_downstream or ""):
                status = "congested"
            elif "서행" in (latest.status_upstream or "") or \
                 "서행" in (latest.status_downstream or ""):
                status = "slow"
        results.append({"name": loc.cctv_name, "lat": lat,
                         "lng": lng, "status": status, ...})
    return jsonify(results)
```

> **서버 시작 시 자동 동기화:** `create_app()` 내부에서 `sync_traffic_to_db()`를 호출하여 서버가 시작될 때 즉시 최신 교통 데이터를 DB에 적재합니다.

---

### 6-7. 기상 정보 연동 (`mp/views/weather.py`)

**[원리]** 카카오맵의 클릭 좌표(위경도)를 받아 기상청 격자 좌표로 변환한 뒤, **초단기실황** + **초단기예보** 두 API를 병행 호출하여 기온, 습도, 강수량, 하늘 상태 등을 반환합니다.

```python
# 위경도 → 기상청 격자 변환 (Excel 룩업 테이블 사용)
location_data = pd.read_excel('mp/static/nxny.xlsx')[
    ['격자 X', '격자 Y', '경도(초/100)', '위도(초/100)']
]

def find_nearest_grid_coordinates(latitude, longitude):
    """geodesic 거리 기반 최근접 격자 탐색"""
    for _, row in location_data.iterrows():
        distance = geodesic((latitude, longitude),
                            (row['위도(초/100)'], row['경도(초/100)'])).meters
        ...
```

---

## 7. 주요 개발 히스토리

### Phase 1 — 프로젝트 초기 설계
- Flask Application Factory 패턴 적용 (`create_app()`)
- Flask-Security 기반 사용자 인증 구축 (UUID `fs_uniquifier` 사용)
- Blueprint 구조화로 기능별 모듈 분리

### Phase 2 — DB 스키마 설계 변경
초기에는 CCTV 위치 정보와 교통 상태를 단일 테이블에 저장했으나, **데이터 중복 및 갱신 이상** 문제가 발생하여 다음과 같이 정규화하였습니다.

| 변경 전 | 변경 후 |
|---------|---------|
| 단일 CCTV 통합 테이블 (위치 + 상태) | `Location` (마스터) + `TrafficStatus` (이력) 분리 |
| 위치 정보 매 분석마다 중복 저장 | 위치는 1회 저장, 상태만 시계열 누적 |
| 카카오맵 좌표 조회 비효율 | location.lat/lng 단일 조회로 최적화 |

이 변경에 맞춰 `traffic_analyzer.py`를 **순수 SQLAlchemy** 방식으로 재작성하여 Flask 앱 컨텍스트 밖에서도 독립 실행이 가능하도록 개선하였습니다.

### Phase 3 — 분석 알고리즘 개선
- **OCCUPANCY_EMPTY_LIMIT** 도입으로 차량 없는 도로에서 '정체' 오판 문제 해결
- Python bool 마스크 → uint8 변환으로 OpenCV `bitwise_and` 호환성 확보
- **방향별 점유율**(Directional Occupancy) 분리 계산 구현
- 카메라 물리적 이동 감지 + 일시 분석 중단 로직 추가

### Phase 4 — 이상 감지 기능 추가
- 역주행: 학습→감지 2단계 구조 + `violation_history` 카운터 오탐 필터
- 불법 주정차: 다각형 ROI + 5초 타이머 + 백그라운드 스레드 분리
- 화재: fire.pt 전용 모델 + 신뢰도 0.6 임계값 적용

### Phase 5 — 교통량 예측 모델 개발
- XGBoost 기반 시계열 예측 모델 구현 (MAE, MAPE, R² 평가)
- 자기회귀(Auto-Regressive) 예측으로 장기 예보 지원
- 모델 캐싱으로 동일 구간 재요청 시 응답 속도 향상

---

## 8. 설치 및 실행

### 사전 요구사항
- Python 3.10+
- MySQL 8.x
- 가상환경 권장 (`.venv`)

### 설치

```bash
# 1. 프로젝트 클론
git clone <repository-url>
cd miniProject-main

# 2. 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. 의존성 설치
pip install -r requirements.txt
```

### 환경 변수 설정

프로젝트 루트에 `.env` 파일 생성:

```env
CCTV_API_KEY=<ITS 국가교통정보 API 키>
WEATHER_SERVICE_KEY=<기상청 API 키>
KAKAO_APP_KEY=<카카오 JavaScript API 키>
```

### DB 초기화

```bash
# MySQL에서 데이터베이스 생성
mysql -u root -p -e "CREATE DATABASE flask_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 서버 실행

```bash
python run.py
```

서버 시작 시 자동으로:
1. `db.create_all()` — 전체 테이블 자동 생성
2. `sync_traffic_to_db()` — 도로공사 API에서 최신 교통 데이터 DB 적재
3. `start_fire_thread()` — 화재 감지 백그라운드 스레드 대기 상태 시작
4. `start_cone_thread()` — 교통콘 감지 백그라운드 스레드 대기 상태 시작

---

## 9. 환경 변수

| 변수명 | 설명 |
|--------|------|
| `CCTV_API_KEY` | ITS 국가교통정보 CCTV API 인증키 |
| `WEATHER_SERVICE_KEY` | 기상청 데이터포털 서비스 키 |
| `KAKAO_APP_KEY` | 카카오맵 JavaScript SDK 키 |

---

## 10. 프로젝트 구조

```
miniProject-main/
├── run.py                    # Flask 앱 진입점
├── config.py                 # 전역 설정 (DB, XGBoost 파라미터 등)
├── requirements.txt
├── .env                      # 환경 변수 (gitignore 대상)
├── data/
│   └── traffic_data.csv      # 교통량 예측 학습 데이터
├── mp/
│   ├── __init__.py           # Application Factory (create_app)
│   ├── models.py             # DB 모델 + TrafficPredictor 클래스
│   ├── services/
│   │   └── traffic_analyzer.py   # 배치 CCTV 분석 워커 (순수 SQLAlchemy)
│   ├── ml_models/
│   │   ├── yolo11n.pt            # 기본 YOLO 모델
│   │   ├── cone.pt               # 교통콘 감지 모델
│   │   └── fire.pt               # 화재 감지 전용 모델
│   ├── views/
│   │   ├── auth.py               # 회원가입 / 로그인
│   │   ├── cctv.py               # 실시간 CCTV 스트리밍 + 교통 분석
│   │   ├── wrong_way.py          # 역주행 감지
│   │   ├── shoulder_parking.py   # 불법 주정차 감지
│   │   ├── dummy_cctv.py         # 화재 감지
│   │   ├── traffic_cone.py       # 교통콘 감지
│   │   ├── traffic_predict.py    # 교통량 예측 API
│   │   ├── traffic_mgmt.py       # 교통 관리 + 카카오맵 API
│   │   ├── traffic_scenario.py   # 교통 시나리오
│   │   ├── weather.py            # 기상 정보 연동
│   │   └── index.py              # 메인 페이지
│   ├── templates/                # Jinja2 HTML 템플릿
│   └── static/
│       ├── videos/               # 테스트용 영상 (wrongway.mp4, suwon1.mp4 등)
│       └── nxny.xlsx             # 기상청 격자 좌표 룩업 테이블
└── README.md
```

---

## 11. 결론 및 향후 과제

### 달성 결과

본 프로젝트는 Python Flask 단일 프레임워크 안에서 **실시간 컴퓨터 비전 분석**, **딥러닝 객체 탐지**, **시계열 머신러닝 예측**, **공공 API 연동**, **카카오맵 시각화**를 통합하였습니다.

특히 다음 기술적 성과를 달성하였습니다:

- **광학 흐름 기반 방향별 독립 분석**: 상행/하행 교통 상태를 동시에 판별
- **2단계 자가 학습 역주행 감지**: 별도 정답 라벨 없이 초기 프레임에서 정상 방향을 스스로 학습
- **다수결 Ensemble 분석**: 10회 반복 분석 후 최빈 상태로 노이즈 억제
- **순수 SQLAlchemy 분리 배포**: Flask 앱 컨텍스트 없이도 배치 워커 독립 실행 가능

### 향후 개선 방향

| 항목 | 내용 |
|------|------|
| 🔔 알림 시스템 | 역주행·화재 감지 시 SMS / 푸시 알림 발송 |
| ⏰ 스케줄러 고도화 | APScheduler로 교통 분석 주기적 자동 실행 |
| 📊 대시보드 | 교통 상태 추이 그래프 및 통계 대시보드 페이지 추가 |
| 🔐 보안 강화 | 환경 변수 기반 DB 비밀번호 분리, HTTPS 적용 |
| 🐳 컨테이너화 | Docker Compose 기반 배포 환경 구성 |
| 📡 스트리밍 최적화 | WebRTC 또는 HLS 방식으로 MJPEG 스트리밍 대체 |

---

*본 보고서는 경부선 고속도로 스마트 통합 모니터링 시스템 미니 프로젝트의 최종 결과물입니다.*
