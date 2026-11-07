/* Home page: hand the search to /near/ without putting it in any request.
   The query is kept in this browser (sessionStorage) and /near/ reads it. */
(function () {
  "use strict";
  var form = document.getElementById("search-form");
  if (!form) return;
  var input = document.getElementById("q");
  var msg = document.getElementById("search-msg");
  var locate = document.getElementById("locate");

  function show(text) {
    msg.textContent = text;
    msg.hidden = !text;
  }

  function go(search) {
    try {
      sessionStorage.setItem("vef-pending", JSON.stringify(search));
    } catch (e) { /* storage blocked: /near/ falls back to its own box */ }
    window.location.href = "/near/";
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var q = (input.value || "").trim();
    if (!q) {
      show("Please type a ZIP code, like 46052, or a city and state, like Lebanon, IN.");
      input.focus();
      return;
    }
    show("");
    go({ q: q });
  });

  locate.addEventListener("click", function () {
    go({ geo: true });
  });
})();
