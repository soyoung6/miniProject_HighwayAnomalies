from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# ======================================================================
# Flask 앱 및 DB 설정
# ======================================================================

app = Flask(__name__)
CORS(app)

# DB 연결 설정 (traffic_analyzer.py와 동일하게)
DB_URL = "mysql+pymysql://root:1234@localhost:3306/flask_db?charset=utf8mb4"

Base = declarative_base()
engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(bind=engine)


# ======================================================================
# DB 모델 정의 (traffic_analyzer.py와 동일)
# ======================================================================

class Location(Base):
    __tablename__ = 'location'
    id = Column(Integer, primary_key=True)
    cctv_name = Column(String(255), unique=True, nullable=False)
    lng = Column(String(50), nullable=False)
    lat = Column(String(50), nullable=False)
    statuses = relationship("TrafficStatus", back_populates="location")


class TrafficStatus(Base):
    __tablename__ = 'traffic_status'
    id = Column(Integer, primary_key=True)
    location_id = Column(Integer, ForeignKey('location.id'), nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    status_upstream = Column(String(50), nullable=False)
    status_downstream = Column(String(50), nullable=False)

    location = relationship("Location", back_populates="statuses")


# ======================================================================
# API 엔드포인트
# ======================================================================

@app.route('/api/traffic')
def get_traffic_data():
    """
    최신 교통 데이터를 반환하는 API
    DB에서 각 location의 최신 status를 조회하여 JavaScript 형식으로 변환
    """
    session = Session()
    try:
        result = []

        # 모든 location 조회
        locations = session.query(Location).all()

        for loc in locations:
            # 해당 location의 가장 최근 status 조회
            latest_status = session.query(TrafficStatus) \
                .filter(TrafficStatus.location_id == loc.id) \
                .order_by(TrafficStatus.timestamp.desc()) \
                .first()

            if latest_status:
                # Python 상태값 -> JavaScript 상태값 매핑
                status_map = {
                    'Clear': 'smooth',
                    'Slow': 'slow',
                    'Congested': 'congested',
                    'No Traffic': 'smooth',
                    'N/A': 'smooth'
                }

                # downstream(하행/부산 방향) 기준으로 사용
                js_status = status_map.get(latest_status.status_downstream, 'smooth')

                result.append({
                    'name': loc.cctv_name,
                    'status': js_status,
                    'status_downstream': latest_status.status_downstream,
                    'status_upstream': latest_status.status_upstream,
                    'timestamp': latest_status.timestamp.isoformat(),
                    'lng': loc.lng,
                    'lat': loc.lat
                })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/')
def index():
    """
    카카오맵 페이지 (기존 HTML 코드 그대로 사용)
    """
    html_content = '''<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>다음 지도 API</title>
  </head>
  <body>
    <div id="map"></div>
    <div id="status-panel">
      <h3>경부선 교통상태</h3>
      <div class="legend-item">
        <div class="legend-color" style="background: #00aa00"></div>
        <span>원활</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #ffa500"></div>
        <span>서행</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #ff0000"></div>
        <span>정체</span>
      </div>
      <div id="last-update">마지막 업데이트: -</div>
    </div>

    <script src="//dapi.kakao.com/v2/maps/sdk.js?appkey=453cf90a4b340fce52c05b0d3fb5f7a6"></script>
    <script>
      var mapContainer = document.getElementById("map"),
        mapOption = {
          center: new kakao.maps.LatLng(37.26, 127.1),
          level: 8,
          mapTypeId: kakao.maps.MapTypeId.HYBRID,
        };

      var map = new kakao.maps.Map(mapContainer, mapOption);

      map.addOverlayMapTypeId(kakao.maps.MapTypeId.TERRAIN);

      var mapTypeControl = new kakao.maps.MapTypeControl();
      map.addControl(mapTypeControl, kakao.maps.ControlPosition.TOPRIGHT);

      var zoomControl = new kakao.maps.ZoomControl();
      map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);

      // CCTV 데이터
      var cctvData = [
        { name: "[경부선] 서초", lng: 127.02583, lat: 37.48306 },
        { name: "[경부선] 양재", lng: 127.042004, lat: 37.461626 },
        { name: "[경부선] 원지동", lng: 127.060749, lat: 37.440057 },
        { name: "[경부선] 상적교", lng: 127.060888, lat: 37.439058 },
        { name: "[경부선] 달래내2", lng: 127.069449, lat: 37.430381 },
        { name: "[경부선] 달래내1", lng: 127.07639, lat: 37.42444 },
        { name: "[경부선] 금현동", lng: 127.084731, lat: 37.415971 },
        { name: "[경부선] 금토분기점1", lng: 127.08472, lat: 37.4153 },
        { name: "[경부선] 금토분기점2", lng: 127.0861359, lat: 37.41418457 },
        { name: "[경부선] 판교분기점", lng: 127.094315, lat: 37.406538 },
        { name: "[경부선] 판교3", lng: 127.095, lat: 37.4052778 },
        { name: "[경부선] 삼평터널(서울)", lng: 127.097582, lat: 37.403541 },
        { name: "[경부선] 판교2", lng: 127.100437, lat: 37.399693 },
        { name: "[경부선] 판교1", lng: 127.100437, lat: 37.399693 },
        { name: "[경부선] 백현", lng: 127.103568, lat: 37.376041 },
        { name: "[경부선] 서울영업소", lng: 127.1025, lat: 37.36556 },
        {
          name: "[경부선] 서울영업소-광장",
          lng: 127.1033173,
          lat: 37.35879517,
        },
        { name: "[경부선] 금곡교", lng: 127.103224, lat: 37.34675865 },
        { name: "[경부선] 죽전", lng: 127.103746, lat: 37.314971 },
        { name: "[경부선] 신갈분기점2", lng: 127.1058333, lat: 37.28 },
        { name: "[경부선] 수원", lng: 127.103583, lat: 37.26395 },
        { name: "[경부선] 공세육교", lng: 127.1038833, lat: 37.24564199 },
        { name: "[경부선] 기흥", lng: 127.104398, lat: 37.226449 },
        { name: "[경부선] 기흥동탄", lng: 127.101335, lat: 37.222297 },
        { name: "[경부선] 동탄분기점", lng: 127.0958333, lat: 37.18194444 },
        { name: "[경부선] 부산동", lng: 127.086496, lat: 37.155528 },
        { name: "[경부선] 오산", lng: 127.08417, lat: 37.14222 },
        { name: "[경부선] 원동", lng: 127.090648, lat: 37.131212 },
        { name: "[경부선] 남사육교", lng: 127.09806, lat: 37.12583 },
        { name: "[경부선] 외동천교", lng: 127.109972, lat: 37.118007 },
        { name: "[경부선] 진위천교", lng: 127.11528, lat: 37.10806 },
        { name: "[경부선] 남사졸음쉼터", lng: 127.122673, lat: 37.09196472 },
        { name: "[경부선] 남사정류장", lng: 127.125675, lat: 37.085919 },
        { name: "[경부선] 산하", lng: 127.1280441, lat: 37.08012009 },
        { name: "[경부선] 안성휴게소(서울)", lng: 127.135, lat: 37.06972 },
        { name: "[경부선] 원곡", lng: 127.135994, lat: 37.05147533 },
        { name: "[경부선] 안성분기점1", lng: 127.13806, lat: 37.04028 },
        { name: "[경부선] 안성분기점2", lng: 127.1380556, lat: 37.04027778 },
        { name: "[경부선] 공도", lng: 127.1511613, lat: 37.002476 },
        { name: "[경부선] 원곡졸음쉼터", lng: 127.1522293, lat: 36.99951172 },
        { name: "[경부선] 안성", lng: 127.15583, lat: 36.99083 },
      ];

      // 마커 이미지 설정
      var markerImageUrl =
          "https://t1.daumcdn.net/localimg/localimages/07/2012/img/marker_p.png",
        markerImageSize = new kakao.maps.Size(35, 42),
        markerImageOptions = {
          offset: new kakao.maps.Point(20, 42),
        };

      var markerImage = new kakao.maps.MarkerImage(
        markerImageUrl,
        markerImageSize,
        markerImageOptions
      );

      var polylines = [];

      // 상태별 색상
      function getColorByStatus(status) {
        switch (status) {
          case "congested":
            return "#FF0000"; // 정체
          case "slow":
            return "#FFA500"; // 서행
          case "smooth":
            return "#00AA00"; // 원활
          default:
            return "#999999"; // 기타
        }
      }

      // ⭐⭐⭐ DB에서 실제 교통 데이터 로드 ⭐⭐⭐
      async function loadTrafficData() {
        try {
          console.log("📡 교통 데이터 API 호출 중...");

          // Flask API 호출
          const response = await fetch("/api/traffic");

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }

          const apiData = await response.json();

          console.log("✅ API 응답 받음:", apiData.length + "개 데이터");

          // API에서 에러 메시지를 반환한 경우
          if (apiData.error) {
            throw new Error(apiData.error);
          }

          // API 데이터와 cctvData 매핑
          var trafficData = cctvData.map((cctv) => {
            // API에서 해당 CCTV 찾기
            const apiCctv = apiData.find((item) => item.name === cctv.name);

            return {
              ...cctv,
              status: apiCctv ? apiCctv.status : "smooth", // API 데이터 없으면 기본값
            };
          });

          // 기존 폴리라인 제거
          polylines.forEach((p) => p.setMap(null));
          polylines = [];

          // 구간별로 색상 다른 폴리라인 그리기
          for (let i = 0; i < trafficData.length - 1; i++) {
            var start = new kakao.maps.LatLng(
              trafficData[i].lat,
              trafficData[i].lng
            );
            var end = new kakao.maps.LatLng(
              trafficData[i + 1].lat,
              trafficData[i + 1].lng
            );
            var color = getColorByStatus(trafficData[i].status);

            var polyline = new kakao.maps.Polyline({
              map: map,
              path: [start, end],
              strokeWeight: 15,
              strokeColor: color,
              strokeOpacity: 0.5,
              strokeStyle: "solid",
            });

            polylines.push(polyline);
          }

          // 업데이트 시간 표시
          var now = new Date();
          var timeStr =
            now.getHours().toString().padStart(2, "0") +
            ":" +
            now.getMinutes().toString().padStart(2, "0");
          document.getElementById("last-update").textContent =
            "마지막 업데이트: " + timeStr;

          console.log("✅ 교통 데이터 로드 완료:", trafficData.length + "개 구간");

          return trafficData;
        } catch (error) {
          console.error("❌ 교통 데이터 로드 실패:", error);

          // 오류 발생 시 회색으로 표시
          var trafficData = cctvData.map((cctv) => ({
            ...cctv,
            status: "unknown",
          }));

          // 기존 폴리라인 제거
          polylines.forEach((p) => p.setMap(null));
          polylines = [];

          // 구간별로 회색 폴리라인 그리기
          for (let i = 0; i < trafficData.length - 1; i++) {
            var start = new kakao.maps.LatLng(
              trafficData[i].lat,
              trafficData[i].lng
            );
            var end = new kakao.maps.LatLng(
              trafficData[i + 1].lat,
              trafficData[i + 1].lng
            );
            var color = "#999999"; // 회색

            var polyline = new kakao.maps.Polyline({
              map: map,
              path: [start, end],
              strokeWeight: 15,
              strokeColor: color,
              strokeOpacity: 0.5,
              strokeStyle: "solid",
            });

            polylines.push(polyline);
          }

          // 에러 메시지 표시
          document.getElementById("last-update").textContent =
            "⚠️ 데이터 로드 실패: " + error.message;

          return trafficData;
        }
      }
      // ⭐⭐⭐ 수정 끝 ⭐⭐⭐

      // 풋터 날씨 위젯 업데이트 함수
      async function updateFooterWeather(cctvName, lat, lon) {
        const widget = document.getElementById("weather-widget-footer");

        if (!widget) {
          console.error("weather-widget-footer 요소를 찾을 수 없습니다");
          return;
        }

        widget.innerHTML = `<p>${cctvName} 날씨 불러오는 중...</p>`;

        try {
          const apiUrl = `/api/weather?latitude=${lat}&longitude=${lon}`;
          const resp = await fetch(apiUrl);

          if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
          }

          const data = await resp.json();

          if (data.error) {
            throw new Error(data.error);
          }

          // 날씨 상태 판단
          let weatherText = "";
          if (data.rainType && data.rainType != 0) {
            switch (data.rainType) {
              case 1:
                weatherText = "비";
                break;
              case 2:
                weatherText = "비/눈";
                break;
              case 3:
                weatherText = "눈";
                break;
              case 4:
                weatherText = "소나기";
                break;
              default:
                weatherText = "강수";
                break;
            }
          } else {
            switch (data.sky) {
              case 1:
                weatherText = "맑음";
                break;
              case 3:
                weatherText = "구름많음";
                break;
              case 4:
                weatherText = "흐림";
                break;
              default:
                weatherText = "정보 없음";
                break;
            }
          }

          widget.innerHTML = `
          <div class="weather-widget">
            <div class="location-name"> ${cctvName}</div>
            <div class="temp">${data.temp}°C</div>
            <div class="sky">${weatherText}</div>
            <div class="humidity">습도: ${data.humidity}%</div>
            <div class="wind">풍속: ${data.wind} m/s</div>
            <div class="rain">강수량: ${data.rain} mm</div>
            <div class="location">위치: ${lat.toFixed(5)}, ${lon.toFixed(
            5
          )}</div>

          `;
        } catch (e) {
          console.error("날씨 정보 오류:", e);
          widget.innerHTML = `<p>${cctvName}<br>날씨 정보를 불러올 수 없습니다. (${e.message})</p>`;
        }
      }

      // 초기 교통 데이터 로드
      var currentTrafficData = loadTrafficData();

      // 모든 CCTV 위치에 마커 생성 (원본 기능 유지)
      cctvData.forEach(function (cctv, index) {
        var position = new kakao.maps.LatLng(cctv.lat, cctv.lng);

        var marker = new kakao.maps.Marker({
          position: position,
          image: markerImage,
          map: map,
        });

        // 커스텀 오버레이 생성
        var customOverlay = new kakao.maps.CustomOverlay({
          map: map,
          clickable: true,
          content:
            '<div style="padding:1px 4px;background:rgba(255,255,255,0.7);border-radius:15px;font-size:12px;white-space:nowrap;box-shadow:0 0px 2px rgba(0,0,0);">' +
            cctv.name +
            "</div>",
          position: position,
          yAnchor: 1.5,
        });

        // 마커 클릭 이벤트 - CCTV 모달 열기 + 날씨 업데이트
        kakao.maps.event.addListener(marker, "click", function () {
          // 풋터 날씨 업데이트 추가
          updateFooterWeather(cctv.name, cctv.lat, cctv.lng);

          // 현재 교통 상태 가져오기
          currentTrafficData.then((data) => {
            var currentStatus = data[index].status;
            var statusText =
              currentStatus === "congested"
                ? "정체"
                : currentStatus === "slow"
                ? "서행"
                : "원활";

            // openCCTVModal 함수가 존재하는지 확인
            if (typeof openCCTVModal === "function") {
              openCCTVModal(cctv.name);
            } else {
              alert(
                cctv.name +
                  "\\n교통상태: " +
                  statusText +
                  "\\n위도: " +
                  cctv.lat +
                  "\\n경도: " +
                  cctv.lng
              );
            }
          });
        });
      });

      // 5분마다 교통 상태 자동 갱신
      setInterval(function () {
        console.log("🔄 5분 주기 자동 갱신 시작...");
        currentTrafficData = loadTrafficData();
      }, 5 * 60 * 1000);

      // 키워드로 장소를 검색합니다
      // searchPlaces();

      // 키워드 검색을 요청하는 함수입니다
      function searchPlaces() {
        var keyword = document.getElementById("keyword").value;

        if (!keyword.replace(/^\\s+|\\s+$/g, "")) {
          alert("키워드를 입력해주세요!");
          return false;
        }

        // 장소검색 객체를 통해 키워드로 장소검색을 요청합니다
        ps.keywordSearch(keyword, placesSearchCB);
      }

      // 장소검색이 완료됐을 때 호출되는 콜백함수 입니다
      function placesSearchCB(data, status, pagination) {
        if (status === kakao.maps.services.Status.OK) {
          // 정상적으로 검색이 완료됐으면
          // 검색 목록과 마커를 표출합니다
          displayPlaces(data);

          // 페이지 번호를 표출합니다
          displayPagination(pagination);
        } else if (status === kakao.maps.services.Status.ZERO_RESULT) {
          alert("검색 결과가 존재하지 않습니다.");
          return;
        } else if (status === kakao.maps.services.Status.ERROR) {
          alert("검색 결과 중 오류가 발생했습니다.");
          return;
        }
      }

      // 데모용: 30초마다 갱신 (테스트용 - 필요시 주석 해제)
      // setInterval(function() {
      //   currentTrafficData = loadTrafficData();
      // }, 30 * 1000);
    </script>
  </body>
</html>'''

    return render_template_string(html_content)


# ======================================================================
# 서버 실행
# ======================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("🚀 Flask API 서버 시작")
    print(f"📍 DB URL: {DB_URL}")
    print("🌐 서버 주소: http://localhost:5000")
    print("🗺️  카카오맵: http://localhost:5000/")
    print("📊 API 엔드포인트: http://localhost:5000/api/traffic")
    print("=" * 70)

    app.run(debug=True, host='0.0.0.0', port=5000)