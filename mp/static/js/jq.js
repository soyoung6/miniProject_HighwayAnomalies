function initializeToggleBar() {
  const $content = $(".map_toggleBtn .content");
  const $button = $(".map_toggleBtn .toggle_button");

  $content.hide();

  $button.on("click", function () {
    $content.slideToggle(300, function () {
      if ($content.is(":visible")) {
        $button.text("접기");
      } else {
        $button.text("펼치기");
      }
    });
  });
}

fetch("../components/header.html")
  .then((res) => res.text())
  .then((data) => (document.querySelector("#header").innerHTML = data));

fetch("../components/sidebar.html")
  .then((res) => res.text())
  .then((data) => (document.querySelector("#sidebar").innerHTML = data));

fetch("../components/map_toggleBtn.html")
  .then((res) => res.text())
  .then((data) => {
    document.querySelector("#map_toggle").innerHTML = data;

    initializeToggleBar();
  });
