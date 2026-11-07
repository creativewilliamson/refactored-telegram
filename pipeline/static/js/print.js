/* Large-print list: /print/?zip=46052&r=25 (or /print/#zip=46052&r=25 from
   the results page, which keeps the ZIP out of any request). One column,
   big type, no images: name, offer, address, phone, distance. */
(function () {
  "use strict";
  var V = window.VEF;
  var $ = function (id) { return document.getElementById(id); };
  var esc = V.esc;

  function params() {
    var p = new URLSearchParams(location.search);
    var h = new URLSearchParams(location.hash.replace(/^#/, ""));
    h.forEach(function (v, k) { if (!p.has(k)) { p.set(k, v); } });
    return p;
  }

  var P = params();
  var radius = [10, 25, 50, 100].indexOf(+P.get("r")) >= 0 ? +P.get("r") : 25;
  var f = { cat: P.get("cat") || "", free: P.get("free") === "1", who: P.get("who") || "", offer: P.get("offer") || "" };

  $("do-print").addEventListener("click", function () { window.print(); });

  function origin() {
    if (P.get("zip")) { return V.resolve(V.parseQuery(P.get("zip"))); }
    if (P.get("city") && P.get("st")) { return V.resolve(V.parseQuery(P.get("city") + ", " + P.get("st"))); }
    if (P.get("lat") && P.get("lng")) {
      return Promise.resolve({ lat: +P.get("lat"), lng: +P.get("lng"), label: "your location" });
    }
    var last = V.loadLast();
    if (last && last.q) { return V.resolve(V.parseQuery(last.q)); }
    if (last && last.geo) { return Promise.resolve({ lat: last.lat, lng: last.lng, label: "your location" }); }
    return Promise.reject(V.Err("none"));
  }

  $("print-status").textContent = "Loading the list…";
  origin().then(function (o) {
    return Promise.all([V.loadOffers(), V.loadNearby(o, radius)]).then(function (res) {
      var data = res[0], near = res[1], today = V.today(), rows = [];
      near.records.forEach(function (x) {
        var b = data.brands[x.r.b];
        if (!b) { return; }
        var offers = b.offers.map(function (id) { return data._byId[id]; }).filter(function (off) {
          return off && V.offerPasses(off, f) && V.status(off, today).k !== "ended";
        });
        if (offers.length) { rows.push({ name: b.name, r: x.r, d: x.d, offers: offers }); }
      });
      (data.places || []).forEach(function (p) {
        var off = data._byId[p.offer];
        var d = V.miles(o.lat, o.lng, p.la, p.lo);
        if (off && d <= radius && V.offerPasses(off, f) && V.status(off, today).k !== "ended") {
          rows.push({ name: p.n, r: p, d: d, offers: [off], approx: p.approx });
        }
      });
      rows.sort(function (a, b) { return a.d - b.d; });

      document.title = "Large-print list: offers near " + o.label + " | Vet Day Deals";
      $("print-h").textContent = "Veterans Day offers near " + o.label;
      $("print-sub").textContent = (rows.length
        ? rows.length + (rows.length === 1 ? " place" : " places") + " within " + radius + " miles, closest first."
        : "No places within " + radius + " miles.") + " Printed " + V.fmtLong(today) + ".";
      $("print-list").innerHTML = rows.map(function (row) {
        var r = row.r;
        var addr = (r.a ? r.a + ", " : "") + [r.c, r.s].filter(Boolean).join(", ") + (r.z ? " " + r.z : "");
        return '<li class="print-item"><h2>' + esc(row.name) + ' <span class="print-miles">' +
          esc((row.approx ? "about " : "") + V.fmtMiles(row.d)) + "</span></h2>" +
          row.offers.map(function (off) {
            var s = V.status(off, today);
            return '<p class="print-offer">' + esc(off.offer) + "</p>" +
              '<p class="print-when">' + esc(s.label) + (off.tw ? " · " + esc(off.tw) : "") +
              (off.redeem_by && s.k !== "voucher" ? " · Voucher good until " + esc(V.fmtShortLong(off.redeem_by)) : "") +
              " · For: " + esc(off.elig) + "</p>";
          }).join("") +
          '<p class="print-addr">' + esc(addr) + "</p>" +
          '<p class="print-phone">' + (r.p ? "Phone: " + esc(V.fmtPhone(r.p)) : "No phone listed") + "</p></li>";
      }).join("");
      var every = data.offers.filter(function (x) { return x.kind === "everywhere" && V.offerPasses(x, f); });
      $("print-everywhere").hidden = !every.length;
      $("print-everywhere-list").innerHTML = every.map(function (x) {
        return '<li class="print-item"><h3>' + esc(x.name) + '</h3><p class="print-offer">' + esc(x.offer) +
          '</p><p class="print-when">' + esc(V.status(x, today).label) + " · For: " + esc(x.elig) + "</p></li>";
      }).join("");
      $("print-status").textContent = near.failed
        ? "Some places didn’t load because the connection dropped. Reload to try again."
        : "";
    });
  }).catch(function (e) {
    var code = e && e.code;
    $("print-status").innerHTML = code === "unknown_zip"
      ? "We couldn’t find that ZIP code. <a href=\"/\">Search again</a>."
      : code === "none"
        ? "No search yet. <a href=\"/\">Search for a ZIP code first</a>, then tap Large-print list."
        : "We couldn’t load the list. Check your signal and reload the page.";
  });
})();
