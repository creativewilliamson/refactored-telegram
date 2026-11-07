/* Results page (/near/). Reads the search from the address bar (shared
   links), from the home page hand-off (sessionStorage) or from the last
   search kept in this browser, then lists nearby places, closest first. */
(function () {
  "use strict";
  var V = window.VEF;
  var $ = function (id) { return document.getElementById(id); };
  var esc = V.esc;
  var PAGE = 50;
  var MIN_PLACES = 10;
  var PLACE_RANGE = 150;
  var ISLANDS = { PR: 1, VI: 1, GU: 1, AS: 1, MP: 1, HI: 1 };

  var S = {
    origin: null, search: null, radius: 25, userRadius: false, widened: 0,
    cat: "", free: false, who: "", offer: null, shown: PAGE,
    nearby: null, failed: 0, data: null, nearCity: null
  };

  var form = $("near-form"), input = $("nq"), msg = $("nq-msg"), statusEl = $("status");
  var results = $("results");

  var box = $("search-box");
  /* Loading and error messages show on screen; the final "Found N places"
     is for screen readers only, because the summary line says it already. */
  function say(text, quiet) {
    statusEl.textContent = text;
    statusEl.className = quiet ? "status sr-only" : "status";
  }
  function doneLoading() { document.documentElement.classList.remove("searching"); }
  function foldSearch(fold) {
    if (fold) { box.classList.add("collapsible"); box.open = false; }
    else { box.open = true; }
  }
  function showMsg(html) { msg.innerHTML = html; msg.hidden = !html; }

  // ---- where the search comes from ------------------------------------
  function initialSearch() {
    var path = location.pathname.replace(/\/+$/, "");
    var m = /^\/near\/(\d{5})$/.exec(path);
    var params = new URLSearchParams(location.search);
    var offer = params.get("offer");
    if (m) { return { q: m[1], shared: true, offer: offer }; }
    if (params.get("city") && params.get("st")) {
      return { q: params.get("city") + ", " + params.get("st"), shared: true, offer: offer };
    }
    if (params.get("zip")) { return { q: params.get("zip"), shared: true, offer: offer }; }
    if (params.get("q")) { return { q: params.get("q"), shared: true, offer: offer }; }
    var pending = V.takePending();
    if (pending) { return pending; }
    var last = V.loadLast();
    if (last) { last.restored = true; return last; }
    return null;
  }

  // ---- running a search -------------------------------------------------
  function run(search) {
    S.search = search;
    S.offer = search.offer || null;
    S.userRadius = !!search.radius;
    S.radius = search.radius || 25;
    $("radius").value = String(S.radius);
    showMsg("");
    if (search.geo && search.lat == null) { return locate(); }
    if (search.geo) {
      return start({ lat: search.lat, lng: search.lng, label: "your location", geo: true }, search);
    }
    input.value = search.q || "";
    var p = V.parseQuery(search.q);
    if (p.type === "state") {
      say("Opening the " + V.STATES[p.st] + " page…");
      location.href = "/state/" + p.st.toLowerCase() + "/";
      return;
    }
    say("Looking up " + search.q + "…");
    return V.resolve(p).then(function (origin) {
      return start(origin, search);
    }).catch(function (e) { fail(e, search.q); });
  }

  function start(origin, search) {
    S.origin = origin;
    S.shown = PAGE;
    S.nearCity = origin.geo ? null : origin.city ? V.titleCase(origin.city) + ", " + origin.st : null;
    if (origin.geo) {
      V.saveLast({ geo: true, lat: origin.lat, lng: origin.lng, offer: S.offer });
    } else {
      V.saveLast({ q: search.q, offer: S.offer });
    }
    say("Finding places near " + origin.label + "…");
    return V.loadOffers().then(function (data) {
      S.data = data;
      return gather();
    }).then(function () {
      render(true);
    }).catch(function (e) { fail(e); });
  }

  /* Load stores for the chosen radius. On a fresh search (default 25 mi)
     widen to 50, then 100, while fewer than 10 places are found. */
  function gather() {
    var steps = S.userRadius ? [S.radius] : [25, 50, 100];
    S.widened = 0;
    function attempt(i) {
      var r = steps[i];
      return V.loadNearby(S.origin, r).then(function (res) {
        var count = res.records.length + placesWithin(r).length;
        var enough = MIN_PLACES;
        if (S.offer && S.data._byId[S.offer]) {
          // "Find the nearest X": widen until at least one X is in range.
          var want = S.data._byId[S.offer].brand;
          count = res.records.filter(function (x) { return x.r.b === want; }).length +
            placesWithin(r).filter(function (x) { return x.p.offer === S.offer; }).length;
          enough = 1;
        }
        if (!S.userRadius && count < enough && i < steps.length - 1) { return attempt(i + 1); }
        S.radius = r;
        S.nearby = res.records;
        S.failed = res.failed;
        S.widened = !S.userRadius && r > 25 ? r : 0;
        $("radius").value = String(r);
        if (!S.nearCity && res.records.length) {
          var first = res.records[0].r;
          if (first.c && first.d < 30) { S.nearCity = first.c + ", " + first.s; }
        }
      });
    }
    return attempt(0);
  }

  function placesWithin(r) {
    var o = S.origin, out = [];
    (S.data.places || []).forEach(function (p) {
      var d = V.miles(o.lat, o.lng, p.la, p.lo);
      if (d <= r) { out.push({ p: p, d: d }); }
    });
    return out;
  }

  // ---- building cards ---------------------------------------------------
  function filters() { return { cat: S.cat, free: S.free, who: S.who, offer: S.offer }; }

  function offersAt(brand) {
    var b = S.data.brands[brand];
    if (!b) { return []; }
    return b.offers.map(function (id) { return S.data._byId[id]; }).filter(Boolean);
  }

  function buildCards() {
    var f = filters(), today = V.today(), cards = [];
    S.nearby.forEach(function (x) {
      var offers = offersAt(x.r.b).filter(function (o) { return V.offerPasses(o, f); });
      if (offers.length) { cards.push(card(x.r, x.d, offers, today, null)); }
    });
    cards.sort(function (a, b) {
      if (a.ended !== b.ended) { return a.ended ? 1 : -1; }
      return a.d - b.d;
    });
    return cards;
  }

  function card(r, d, offers, today, place) {
    var st = offers.map(function (o) { return { o: o, s: V.status(o, today) }; });
    st.sort(function (a, b) { return (a.s.k === "ended") - (b.s.k === "ended"); });
    var ended = st.every(function (x) { return x.s.k === "ended"; });
    return { r: r, d: d, offers: st, ended: ended, place: place };
  }

  function chips(o, s) {
    var h = '<p class="chips">';
    h += '<span class="chip chip-' + s.k + '">' + esc(s.label) + "</span>";
    h += '<span class="chip chip-type">' + esc(S.data.types[o.type]) + "</span>";
    if (s.k === "soon" && o.start !== o.end) { h += '<span class="chip">' + esc(V.dateText(o)) + "</span>"; }
    if (o.tw) { h += '<span class="chip chip-time">' + esc(o.tw) + "</span>"; }
    if (o.redeem_by && s.k !== "voucher" && s.k !== "ended") {
      h += '<span class="chip chip-voucher">Voucher good until ' + esc(V.fmtShortLong(o.redeem_by)) + "</span>";
    }
    return h + "</p>";
  }

  function offerBlock(o, s, name) {
    return '<li class="card-offer' + (s.k === "ended" ? " is-ended" : "") + '">' +
      '<p class="offer-text">' + esc(o.offer) + "</p>" + chips(o, s) +
      '<p class="who"><strong>Who:</strong> ' + esc(o.elig) + "</p>" +
      (o.terms ? '<p class="terms">' + esc(o.terms) + "</p>" : "") +
      '<p class="links"><a href="' + esc(o.src) + '" target="_blank" rel="noopener noreferrer">Offer details' +
      '<span class="sr-only"> for ' + esc(name) + " (opens the business’s page)</span></a></p></li>";
  }

  function renderCard(c, i) {
    var r = c.r, p = c.place;
    var name = p ? p.n : (S.data.brands[r.b] || {}).name || "";
    var id = "card-" + i;
    var h = '<li class="card' + (c.ended ? " is-ended" : "") + '"><article aria-labelledby="' + id + '">';
    h += '<div class="card-head"><h3 id="' + id + '">' + esc(name) + "</h3>" +
      '<span class="miles">' + esc((p && p.approx ? "about " : "") + V.fmtMiles(c.d)) + "</span></div>";
    if (!p && r.n) { h += '<p class="branch">' + esc(r.n) + "</p>"; }
    h += '<ul class="card-offers">';
    c.offers.forEach(function (x) { h += offerBlock(x.o, x.s, name); });
    h += "</ul>";
    var city = [r.c, r.s].filter(Boolean).join(", ") + (r.z ? " " + r.z : "");
    h += '<p class="addr">' + (r.a ? esc(r.a) + "<br>" : "") + esc(city) + "</p>";
    if (p && p.approx) {
      h += '<p class="terms">We don’t have the exact street address. Directions go to the middle of ' +
        esc(r.c) + ". Check the offer details for the exact spot.</p>";
    }
    if (r.h) {
      h += '<p class="hours"><strong>Usual hours:</strong> ' + esc(V.fmtHours(r.h).replace(/\.$/, "")) +
        ". Call ahead on Veterans Day.</p>";
    }
    h += '<p class="actions">';
    if (r.p) {
      h += '<a class="btn btn-call" href="tel:+1' + esc(r.p) + '">Call ' + esc(V.fmtPhone(r.p)) +
        '<span class="sr-only"> ' + esc(name) + "</span></a>";
    } else {
      h += '<span class="no-phone">No phone listed</span>';
    }
    h += '</p><p class="actions"><span class="dir-label">Directions:</span>';
    h += '<a class="btn btn-secondary" href="' + V.googleDir(r.la, r.lo) + '" target="_blank" rel="noopener noreferrer">' +
      'Google Maps<span class="sr-only"> directions to ' + esc(name) + "</span></a>";
    h += '<a class="btn btn-secondary" href="' + V.appleDir(r.la, r.lo) + '" target="_blank" rel="noopener noreferrer">' +
      'Apple Maps<span class="sr-only"> directions to ' + esc(name) + "</span></a>";
    h += "</p></article></li>";
    return h;
  }

  function offerListItem(o, findLink) {
    var s = V.status(o);
    var h = '<li class="offer-row"><h3 class="offer-name">' + esc(o.name) + "</h3>" +
      '<p class="offer-text">' + esc(o.offer) + "</p>" + chips(o, s) +
      '<p class="who"><strong>Who:</strong> ' + esc(o.elig) + "</p>" +
      (o.terms ? '<p class="terms">' + esc(o.terms) + "</p>" : "") + '<p class="links">';
    if (findLink) {
      h += '<a class="btn btn-secondary" href="' + esc(V.findNearest(o.map, S.nearCity)) +
        '" target="_blank" rel="noopener noreferrer">Find nearest<span class="sr-only"> ' + esc(o.name) +
        " on Google Maps</span></a> ";
    }
    h += '<a href="' + esc(o.src) + '" target="_blank" rel="noopener noreferrer">Offer details' +
      '<span class="sr-only"> for ' + esc(o.name) + " (opens the business’s page)</span></a></p></li>";
    return h;
  }

  // ---- render -----------------------------------------------------------
  function render(fresh) {
    var o = S.origin, f = filters();
    var cards = buildCards();
    var shown = cards.slice(0, S.shown);
    var placeLabel = o.label;

    document.title = "Offers near " + placeLabel + " | VetsEatFree";
    $("results-h").textContent = "Offers near " + placeLabel;
    var n = cards.length;
    $("summary").textContent = n
      ? n + (n === 1 ? " store" : " stores") + " with offers within " + S.radius + " miles of " + placeLabel + ", closest first."
      : "No stores with offers within " + S.radius + " miles of " + placeLabel + ".";

    var widen = $("widen-note");
    var islandNote = "";
    if (ISLANDS[o.st] && cards.some(function (c) { return c.r.s && c.r.s !== o.st; })) {
      islandNote = " Some of these places are on another island, across the water.";
    }
    if (S.widened) {
      widen.textContent = "Showing up to " + S.widened + " miles because few places are close by." + islandNote;
      widen.hidden = false;
    } else if (islandNote) {
      widen.textContent = islandNote.trim();
      widen.hidden = false;
    } else if (S.userRadius && n < MIN_PLACES && S.radius < 100) {
      widen.innerHTML = "Only " + n + (n === 1 ? " store" : " stores") + " within " + S.radius +
        ' miles. <button type="button" class="linkish" id="widen-btn">Show up to ' + nextRadius() + " miles</button>";
      widen.hidden = false;
    } else {
      widen.hidden = true;
    }

    var offerNote = $("offer-filter-note");
    if (S.offer && S.data._byId[S.offer]) {
      offerNote.innerHTML = "Showing only " + esc(S.data._byId[S.offer].name) +
        '. <button type="button" class="linkish" id="all-offers">Show all offers</button>';
      offerNote.hidden = false;
    } else {
      offerNote.hidden = true;
    }

    var list = $("cards");
    list.innerHTML = shown.map(renderCard).join("");
    var empty = $("cards-empty");
    if (!n) {
      empty.textContent = anyFilter()
        ? "No places match these filters within " + S.radius + " miles. Try clearing the filters."
        : "We didn’t find stores with Veterans Day offers within " + S.radius + " miles of " + placeLabel +
          ". The offers under Everywhere work anywhere, and the chains listed below may still have a store near you.";
      empty.hidden = false;
    } else {
      empty.hidden = true;
    }
    if (S.failed) {
      empty.hidden = false;
      empty.innerHTML = (n ? "" : esc(empty.textContent) + " ") +
        "Some nearby places didn’t load because the connection dropped, so this list may be missing a few. " +
        '<button type="button" class="linkish" id="retry-tiles">Try again</button>';
    }
    var more = $("more");
    if (cards.length > S.shown) {
      more.hidden = false;
      more.textContent = "Show more places (" + (cards.length - S.shown) + " more)";
    } else {
      more.hidden = true;
    }

    // Single places (museums, zoos...) within 150 miles, whatever the radius.
    var far = [];
    placesWithin(PLACE_RANGE).forEach(function (x) {
      var off = S.data._byId[x.p.offer];
      if (off && V.offerPasses(off, f)) { far.push(card(x.p, x.d, [off], V.today(), x.p)); }
    });
    far.sort(function (a, b) { return a.d - b.d; });
    $("far").hidden = !far.length;
    $("far-cards").innerHTML = far.map(function (c, i) { return renderCard(c, "far-" + i); }).join("");

    // Everywhere: offers with no store.
    var every = S.data.offers.filter(function (x) { return x.kind === "everywhere" && V.offerPasses(x, f); });
    $("everywhere-note").textContent = n
      ? "These offers don’t need a store near you."
      : "Nothing with a store list is close to " + placeLabel + ", so start here: these offers work anywhere.";
    $("everywhere-list").innerHTML = every.map(function (x) { return offerListItem(x, true); }).join("") ||
      "<li>No offers here match your filters.</li>";

    // Chains without a store list (regional ones only in their states).
    var st = o.st;
    var finds = S.data.offers.filter(function (x) {
      if (x.kind !== "find" || !V.offerPasses(x, f)) { return false; }
      return x.scope !== "regional" || !st || (x.states || []).indexOf(st) >= 0;
    });
    $("find").hidden = !finds.length;
    $("find-list").innerHTML = finds.map(function (x) { return offerListItem(x, true); }).join("");

    // Print + share
    $("print-link").setAttribute("href", "/print/#" + printParams());
    $("share").hidden = !!o.geo;
    results.hidden = false;
    var tail = S.failed ? " Some places may be missing." : "";
    say("Found " + n + (n === 1 ? " store" : " stores") + " within " + S.radius + " miles." + tail, true);
    if (fresh) { foldSearch(true); }
    doneLoading();
    if (fresh) { $("results-h").focus(); }
  }

  function nextRadius() { return S.radius < 25 ? 25 : S.radius < 50 ? 50 : 100; }
  function anyFilter() { return !!(S.cat || S.free || S.who); }

  function printParams() {
    var o = S.origin, q = [];
    if (o.zip) { q.push("zip=" + o.zip); }
    else if (o.cityKey) { q.push("city=" + encodeURIComponent(o.cityKey), "st=" + o.st); }
    else { q.push("lat=" + o.lat.toFixed(4), "lng=" + o.lng.toFixed(4)); }
    q.push("r=" + S.radius);
    if (S.cat) { q.push("cat=" + S.cat); }
    if (S.free) { q.push("free=1"); }
    if (S.who) { q.push("who=" + S.who); }
    if (S.offer) { q.push("offer=" + S.offer); }
    return q.join("&");
  }

  function shareUrl() {
    var o = S.origin;
    if (o.zip) { return location.origin + "/near/" + o.zip; }
    if (o.cityKey) { return location.origin + "/near/?city=" + encodeURIComponent(o.cityKey) + "&st=" + o.st; }
    return null;
  }

  // ---- errors -----------------------------------------------------------
  function fail(e, q) {
    var code = e && e.code;
    var text;
    if (code === "unknown_zip") {
      text = "We couldn’t find ZIP code " + esc(e.zip) + ". Check the numbers, or type your city and state, like Lebanon, IN.";
    } else if (code === "military") {
      text = "ZIP " + esc(e.zip) + " is for military mail (APO or FPO), not a place on the map. Type the ZIP code or town where you are now.";
    } else if (code === "unknown_city") {
      text = "We couldn’t find “" + esc(e.city) + "” in " + esc(V.STATES[e.st]) + ".";
      if (e.suggestions && e.suggestions.length) {
        text += " Did you mean: " + e.suggestions.map(function (s) {
          return '<button type="button" class="linkish" data-suggest="' + esc(s + ", " + e.st) + '">' + esc(s + ", " + e.st) + "</button>";
        }).join(" ") + "?";
      } else {
        text += " Check the spelling, or type your ZIP code.";
      }
    } else if (code === "nostate") {
      text = "Please add the state, like “" + esc(q || "Lebanon") + ", IN”, or type your ZIP code.";
    } else if (code === "badzip") {
      text = "A ZIP code has 5 numbers, like 46052. Please check it and try again.";
    } else if (code === "empty") {
      text = "Please type a ZIP code, like 46052, or a city and state, like Lebanon, IN.";
    } else if (code === "geo_denied") {
      text = "Your phone didn’t share your location. That’s OK: type your ZIP code instead.";
    } else if (code === "geo_unavailable") {
      text = "We couldn’t get your location. Please type your ZIP code instead.";
    } else if (code === "network" || code === "missing") {
      text = (navigator.onLine === false ? "You seem to be offline. " : "We couldn’t load the offer list. ") +
        'Check your signal and try again. <button type="button" class="linkish" id="retry-search">Try again</button>';
    } else {
      text = "Something went wrong. Please try again, or type your ZIP code.";
    }
    say("");
    foldSearch(false);
    doneLoading();
    showMsg(text);
    if (!S.origin) { results.hidden = true; }
    input.focus();
  }

  // ---- location ---------------------------------------------------------
  function locate() {
    if (!navigator.geolocation) { fail({ code: "geo_unavailable" }); return; }
    say("Asking your phone for your location…");
    navigator.geolocation.getCurrentPosition(function (pos) {
      var lat = Math.round(pos.coords.latitude * 10000) / 10000;
      var lng = Math.round(pos.coords.longitude * 10000) / 10000;
      input.value = "";
      start({ lat: lat, lng: lng, label: "your location", geo: true }, { geo: true, lat: lat, lng: lng });
    }, function (err) {
      fail({ code: err && err.code === 1 ? "geo_denied" : "geo_unavailable" });
    }, { enableHighAccuracy: false, timeout: 20000, maximumAge: 600000 });
  }

  // ---- events -----------------------------------------------------------
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var q = (input.value || "").replace(/\s+/g, " ").trim();
    if (!q) { fail({ code: "empty" }); return; }
    run({ q: q, offer: S.offer });
  });
  $("near-locate").addEventListener("click", function () { run({ geo: true, offer: S.offer }); });

  $("radius").addEventListener("change", function () {
    if (!S.origin) { return; }
    S.userRadius = true;
    S.radius = +this.value;
    S.shown = PAGE;
    say("Loading places within " + S.radius + " miles…");
    gather().then(function () { render(false); }).catch(function (e) { fail(e); });
  });

  Array.prototype.forEach.call(document.querySelectorAll("#cat-buttons .seg-btn"), function (b) {
    b.addEventListener("click", function () {
      S.cat = b.getAttribute("data-cat");
      Array.prototype.forEach.call(document.querySelectorAll("#cat-buttons .seg-btn"), function (x) {
        x.setAttribute("aria-pressed", x === b ? "true" : "false");
      });
      S.shown = PAGE;
      if (S.origin) { render(false); }
    });
  });
  $("free-only").addEventListener("click", function () {
    S.free = this.getAttribute("aria-pressed") !== "true";
    this.setAttribute("aria-pressed", S.free ? "true" : "false");
    S.shown = PAGE;
    if (S.origin) { render(false); }
  });
  $("who").addEventListener("change", function () { S.who = this.value; S.shown = PAGE; if (S.origin) { render(false); } });
  $("clear-filters").addEventListener("click", function () {
    S.cat = ""; S.free = false; S.who = "";
    $("free-only").setAttribute("aria-pressed", "false"); $("who").value = "";
    Array.prototype.forEach.call(document.querySelectorAll("#cat-buttons .seg-btn"), function (x) {
      x.setAttribute("aria-pressed", x.getAttribute("data-cat") === "" ? "true" : "false");
    });
    if (S.origin) { render(false); }
  });
  $("more").addEventListener("click", function () {
    var first = S.shown;
    S.shown += PAGE;
    render(false);
    var next = document.querySelectorAll("#cards > li")[first];
    if (next) { var h = next.querySelector("h3"); if (h) { h.setAttribute("tabindex", "-1"); h.focus(); } }
  });

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t || !t.closest) { return; }
    if (t.closest("#widen-btn")) {
      S.userRadius = true; S.radius = nextRadius(); $("radius").value = String(S.radius);
      gather().then(function () { render(false); }).catch(function (e) { fail(e); });
    } else if (t.closest("#all-offers")) {
      S.offer = null; V.saveLast(S.origin.geo ? { geo: true, lat: S.origin.lat, lng: S.origin.lng } : { q: S.search.q });
      render(false);
    } else if (t.closest("#retry-tiles")) {
      gather().then(function () { render(false); }).catch(function (e) { fail(e); });
    } else if (t.closest("#retry-search")) {
      if (S.search) { run(S.search); }
    } else if (t.closest("[data-suggest]")) {
      var q = t.closest("[data-suggest]").getAttribute("data-suggest");
      input.value = q;
      run({ q: q, offer: S.offer });
    }
  });

  $("share").addEventListener("click", function () {
    var url = shareUrl();
    var out = $("share-msg");
    if (!url) { return; }
    if (navigator.share) {
      navigator.share({ title: "Veterans Day offers near " + S.origin.label, url: url }).catch(function () {});
      return;
    }
    var done = function () { out.textContent = "Link copied: " + url; out.hidden = false; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done, function () { out.textContent = "Copy this link: " + url; out.hidden = false; });
    } else {
      out.textContent = "Copy this link: " + url;
      out.hidden = false;
    }
  });

  // ---- go ---------------------------------------------------------------
  var first = initialSearch();
  if (first) {
    run(first);
  } else {
    say("");
    input.focus();
  }
})();
