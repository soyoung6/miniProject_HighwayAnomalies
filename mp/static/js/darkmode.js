$(document).ready(function () {
  // 페이지 로드 시 저장된 설정 불러옴
  const isDarkMode = localStorage.getItem("darkMode") === "enabled";

  if (isDarkMode) {
    $("body").addClass("dark-mode");
    updateToggleButton(true);
    applySidebarDarkMode(true);
    applyModalDarkMode(true);
    applyFooterDarkMode(true);
    applyMapDarkMode(true);
    applyCCTVModalDarkMode(true);
    applyRegisterFormDarkMode(true);
  } else {
    // ✅ 이 부분 추가 - 라이트모드일 때도 버튼 아이콘 초기화
    updateToggleButton(false);
  }

  // 토글 버튼 클릭 이벤트
  $(".dark-mode-toggle").on("click", function () {
    $("body").toggleClass("dark-mode");

    const isDarkMode = $("body").hasClass("dark-mode");

    // localStorage에 설정 저장
    if (isDarkMode) {
      localStorage.setItem("darkMode", "enabled");
    } else {
      localStorage.setItem("darkMode", "disabled");
    }

    // 즉시 모든 요소 업데이트 (애니메이션 없음)
    updateToggleButton(isDarkMode);
    applySidebarDarkMode(isDarkMode);
    applyModalDarkMode(isDarkMode);
    applyFooterDarkMode(isDarkMode);
    applyMapDarkMode(isDarkMode);
    applyCCTVModalDarkMode(isDarkMode);
    applyRegisterFormDarkMode(isDarkMode);
    console.log("✅ 다크모드 전환 완료:", isDarkMode);
  });

  // ========= 1. 버튼 UI 업데이트 =========
  function updateToggleButton(isDarkMode) {
    const $toggle = $(".dark-mode-toggle");

    if (isDarkMode) {
      // 다크모드일 때 - 해 아이콘 (라이트모드로 전환)
      $toggle.html("<i class='bx bx-sun'></i>");
    } else {
      // 라이트모드일 때 - 달 아이콘 (다크모드로 전환)
      $toggle.html("<i class='bx bx-moon'></i>");
    }
  }

  // ========= 2. 사이드바 즉시 적용 =========
  function applySidebarDarkMode(isDarkMode) {
    const $sidebar = $("aside");
    const $sideLinks = $sidebar.find(".side-menu li a");
    const $weatherWidget = $sidebar.find(".weather-widget-sb");
    const $owlHead = $sidebar.find(".owl_head a");

    if (isDarkMode) {
      $sidebar.css({
        background: "#2d2d2d",
        color: "#e9ecef",
      });
      $sideLinks.css("color", "#e9ecef");
      $owlHead.css("color", "#e9ecef");
      $weatherWidget.css({
        background: "#1a1a1a",
        color: "#e9ecef",
      });
    } else {
      $sidebar.css({
        background: "#171f36",
        color: "white",
      });
      $sideLinks.css("color", "white");
      $owlHead.css("color", "#fff");
      $weatherWidget.css({
        background: "#f5f5f5",
        color: "#333",
      });
    }
  }

  // ========= 3. 로그인 모달 즉시 적용 =========
  function applyModalDarkMode(isDarkMode) {
    const $modal = $(".login-modal");
    if ($modal.length === 0) return;

    const $modalInputs = $modal.find("input");
    const $modalButtons = $modal.find("button");

    if (isDarkMode) {
      $modal.css({
        backgroundColor: "#1a1a1a",
        color: "#e9ecef",
      });
      $modalInputs.css({
        backgroundColor: "#1a1a1a",
        color: "#e9ecef",
        borderColor: "#dee2e6",
      });
      $modalButtons.css({
        backgroundColor: "#2d2d2d",
        color: "#e9ecef",
      });
    } else {
      $modal.css({
        backgroundColor: "#ffffff",
        color: "#000000",
      });
      $modalInputs.css({
        backgroundColor: "#ffffff",
        color: "#000000",
        borderColor: "#dee2e6",
      });
      $modalButtons.css({
        backgroundColor: "#ffffff",
        color: "#000000",
      });
    }
  }

  // ===== 4. 푸터 즉시 적용 =====
  function applyFooterDarkMode(isDarkMode) {
    const $footer = $(".footer");
    const $weatherWidget = $("#weather-widget-footer");

    if (isDarkMode) {
      $footer.css({
        background: "#2d2d2d",
        color: "#e9ecef",
      });
      // ✅ 추가: 모든 하위 요소에도 색상 적용
      $weatherWidget.css("color", "#e9ecef");
      $weatherWidget.find("*").css("color", "#e9ecef");
      $weatherWidget.find("div").css("color", "#e9ecef"); // div 태그 명시적 적용
    } else {
      $footer.css({
        background: "#ffffff",
        color: "#000000",
      });
      $weatherWidget.css("color", "#000000");
      $weatherWidget.find("*").css("color", "#000000");
    }
  }

  // ===== 5. 카카오맵 즉시 적용 =====
  function applyMapDarkMode(isDarkMode) {
    // 맵 타입 전환
    if (typeof map !== "undefined" && map) {
      if (isDarkMode) {
        // 다크모드 -> 스카이뷰
        map.setMapTypeId(kakao.maps.MapTypeId.SKYVIEW);
      } else {
        //라이트모드 -> 일반 지도
        map.setMapTypeId(kakao.maps.MapTypeId.ROADMAP);
      }
    }

    // 카카오맵 오버레이 업데이트
    if (typeof window.updateMapOverlays === "function") {
      window.updateMapOverlays(isDarkMode);
    }

    // 상태 패널 업데이트
    const $statusPanel = $("#status-panel");
    if ($statusPanel.length > 0) {
      if (isDarkMode) {
        $statusPanel.css({
          background: "#1a1a1a",
          color: "#e9ecef",
        });
        $statusPanel.find("*").css("color", "#e9ecef");
        $statusPanel
          .find("h3, .legend-item, .legend-item span, #last-update")
          .css("color", "#e9ecef");
      } else {
        $statusPanel.css({
          background: "rgba(255, 255, 255, 0.897)",
          color: "#000000",
        });
        $statusPanel
          .find("h3, .legend-item, .legend-item span, #last-update")
          .css("color", "#000000");
      }
    }
  }

  // ===== 6. CCTV 모달 즉시 적용 =====
  function applyCCTVModalDarkMode(isDarkMode) {
    const $cctvWidget = $(".cctv-widget");
    if ($cctvWidget.length === 0) return;

    const $cctvBody = $cctvWidget.find(".cctv-widget-body");
    const $cctvLabels = $cctvWidget.find(
      ".cctv-selector-label, .cctv-current-name"
    );
    const $cctvSelector = $cctvWidget.find(".cctv-selector");

    if (isDarkMode) {
      $cctvWidget.css({
        background: "#2d2d2d",
        color: "#e9ecef",
      });
      $cctvBody.css("background", "#2d2d2d");
      $cctvLabels.css("color", "#e9ecef");
      $cctvSelector.css({
        background: "#2d2d2d",
        color: "#e9ecef",
        borderColor: "#dee2e6",
      });
    } else {
      $cctvWidget.css({
        background: "white",
        color: "#000000",
      });
      $cctvBody.css("background", "white");
      $cctvLabels.css("color", "#374151");
      $cctvSelector.css({
        background: "white",
        color: "#1f2937",
        borderColor: "#e5e7eb",
      });
    }
  }
});

// ===== 카카오맵 오버레이 업데이트 함수 (전역) =====
window.updateMapOverlays = function (isDarkMode) {
  if (typeof cctvOverlays === "undefined" || cctvOverlays.length === 0) {
    console.warn("카카오맵 오버레이가 초기화되지 않았습니다.");
    return;
  }

  cctvOverlays.forEach((overlay, index) => {
    const cctv = cctvData[index];
    const position = new kakao.maps.LatLng(cctv.lat, cctv.lng);

    // 기존 오버레이 제거
    overlay.setMap(null);

    // 새로운 스타일로 오버레이 재생성
    const overlayStyle = isDarkMode
      ? "padding:1px 4px;background:rgba(255,255,255,0.7);color:#000;border-radius:15px;font-size:12px;white-space:nowrap;box-shadow:0 0px 2px rgba(0,0,0,0.3);"
      : "padding:1px 4px;background:rgba(255,255,255,0.7);color:#000;border-radius:15px;font-size:12px;white-space:nowrap;box-shadow:0 0px 2px rgba(0,0,0,0.3);";

    cctvOverlays[index] = new kakao.maps.CustomOverlay({
      map: map,
      clickable: true,
      content: `<div style="${overlayStyle}">${cctv.name}</div>`,
      position: position,
      yAnchor: 1.5,
    });
  });

  console.log("✅ 카카오맵 오버레이 업데이트 완료");
};

// ===== 7. 회원가입 폼 즉시 적용 ===== ✅ 새로 추가
function applyRegisterFormDarkMode(isDarkMode) {
  const $mainForm = $(".mainForm");
  if ($mainForm.length === 0) return;

  const $icons = $mainForm.find("i");
  const $inputs = $mainForm.find("input");
  const $selects = $(".phoneForm select");

  if (isDarkMode) {
    $icons.css("color", "#e9ecef");
    $inputs.css({
      backgroundColor: "#1a1a1a",
      color: "#e9ecef",
    });
    $selects.css({
      backgroundColor: "#1a1a1a",
      color: "#e9ecef",
    });
  } else {
    $icons.css("color", "#000000");
    $inputs.css({
      backgroundColor: "#ffffff",
      color: "#000000",
    });
    $selects.css({
      backgroundColor: "#ffffff",
      color: "#000000",
    });
  }
}
