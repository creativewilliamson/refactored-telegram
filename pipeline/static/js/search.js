/* Search boxes on the home, state and offer pages.
   The search is handed to /near/ through sessionStorage, so the ZIP, city
   or location never goes into a URL or any request. */
(function () {
  "use strict";

  function go(search) {
    try {
      sessionStorage.setItem("vef-pending", JSON.stringify(search));
    } catch (e) { /* storage blocked: /near/ shows its own search box */ }
    window.location.href = "/near/";
  }

  // Offline helper: keeps this site's own pages and data on the phone so a
  // reload works on a weak signal. Sends nothing anywhere.
  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () { /* optional */ });
    });
  }

  var forms = document.querySelectorAll("form[data-search]");
  Array.prototype.forEach.call(forms, function (form) {
    // The box has no name attribute on purpose: if this script ever fails to
    // load, a plain form submit sends nothing, never the ZIP.
    var input = form.querySelector("input[type=text]");
    var msg = form.querySelector(".msg");
    var brand = form.getAttribute("data-brand") || null;

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var q = (input.value || "").replace(/\s+/g, " ").trim();
      if (!q) {
        msg.textContent = "Please type a ZIP code, like 46052, or a city and state, like Lebanon, IN.";
        msg.hidden = false;
        input.focus();
        return;
      }
      msg.hidden = true;
      go({ q: q, offer: brand });
    });

    var locate = form.querySelector("[data-locate]");
    if (locate) {
      locate.addEventListener("click", function () {
        go({ geo: true, offer: brand });
      });
    }
  });
})();
