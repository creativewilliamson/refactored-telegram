/* Large-print list: /print/?zip=46052&r=25 (or /print/#zip=46052&r=25 from
   the results page, which keeps the ZIP out of any request). One column,
   big type, no images: name, offer, address, phone, distance. */
(function () {
  "use strict";
  var V = window.VDD;
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
  // Like the results page: the default 25 miles widens to 50, then 100,
  // while fewer than 10 places are found. A radius the visitor picked on the
  // results page comes with fixed=1 and is kept as it is.
  var MIN_PLACES = 10;
  var ISLANDS = { PR: 1, VI: 1, GU: 1, AS: 1, MP: 1, HI: 1 };
  var autoWiden = radius === 25 && P.get("fixed") !== "1";
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

  function placesWithin(data, o, r) {
    return (data.places || []).filter(function (p) { return V.miles(o.lat, o.lng, p.la, p.lo) <= r; });
  }

  /* Same rule as the results page: count every store and place in range
     (or, for "find the nearest X", only X and stop at one). */
  function gather(o, data, first) {
    var only = f.offer && data._byId[f.offer];
    // No store list for X: nothing to count, so never widen.
    var steps = autoWiden && !(only && only.kind === "find") ? [25, 50, 100] : [radius];
    function check(i, near) {
      var r = steps[i];
      var count = near.records.length + placesWithin(data, o, r).length, enough = MIN_PLACES;
      if (f.offer && data._byId[f.offer]) {
        var want = data._byId[f.offer].brand;
        count = near.records.filter(function (x) { return x.r.b === want; }).length +
          placesWithin(data, o, r).filter(function (p) { return p.offer === f.offer; }).length;
        enough = 1;
      }
      if (count < enough && i < steps.length - 1) {
        return V.loadNearby(o, steps[i + 1]).then(function (next) { return check(i + 1, next); });
      }
      radius = r;
      // w=1: the results page already widened to this radius.
      return { near: near, widened: r > steps[0] || P.get("w") === "1" };
    }
    return Promise.resolve(check(0, first));
  }

  $("print-status").textContent = "Loading the list…";
  origin().then(function (o) {
    return Promise.all([V.loadOffers(), V.loadNearby(o, radius)]).then(function (res) {
      return gather(o, res[0], res[1]).then(function (g) { return [res[0], g.near, g.widened]; });
    }).then(function (res) {
      var data = res[0], near = res[1], widened = res[2], today = V.today(), rows = [];
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

      // "Find the nearest X" prints only X, and says so.
      var only = f.offer && data._byId[f.offer];
      var b = only && data.brands[only.brand] || {};
      var xname = only ? (b.name || only.name) : "";
      var count = rows.length + (rows.length === 1 ? " place" : " places") + " within " + radius + " miles, closest first.";
      var sub;
      if (only && only.kind === "find") {
        sub = "We don’t have a store list for " + xname + ", so we can’t say how far the nearest one is. " +
          "Search a map for “" + (only.map || xname) + " near " + o.label + "”.";
      } else if (only) {
        sub = rows.length ? "Only " + xname + ": " + count
          : "The nearest " + xname + " is more than " + radius + " miles from " + o.label + "." +
            (b.st && b.st.length ? " " + xname + " has stores in " + V.stateList(b.st) + "." : "");
      } else {
        sub = rows.length ? count : "No places within " + radius + " miles.";
      }
      document.title = "Large-print list: " + (only ? xname : "offers") + " near " + o.label + " | Vet Day Deals";
      $("print-h").textContent = (only ? xname : "Veterans Day offers") + " near " + o.label;
      $("print-sub").textContent = sub + " Printed " + V.fmtLong(today) + ".";
      var island = ISLANDS[o.st] && rows.some(function (row) { return row.r.s && row.r.s !== o.st; })
        ? " Some of these places are on another island, across the water." : "";
      $("print-widen").textContent = widened && only && rows.length
        ? "Showing up to " + radius + " miles to look for the nearest " + xname + "." + island
        : widened && !only
        ? "Showing up to " + radius + " miles because few places are close by." + island
        : island.trim();
      $("print-widen").hidden = !$("print-widen").textContent;
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
      if (only && only.kind === "find") {
        // No store list: still print the offer, with what to search for.
        var st0 = V.status(only, today);
        $("print-list").innerHTML = '<li class="print-item"><h2>' + esc(xname) + "</h2>" +
          '<p class="print-offer">' + esc(only.offer) + "</p>" +
          '<p class="print-when">' + esc(st0.label) + (only.tw ? " · " + esc(only.tw) : "") + " · For: " + esc(only.elig) + "</p>" +
          '<p class="print-addr">No store list: search a map for “' + esc((only.map || xname) + " near " + o.label) +
          "”, and call ahead.</p></li>";
      }
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
