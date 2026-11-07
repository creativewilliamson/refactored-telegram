/* VetsEatFree shared code. Everything here runs on the visitor's device:
   ZIP and city lookups read static files by index (first 3 ZIP digits,
   state code, map square), and all distance math happens in this file.
   Nothing the visitor types is ever sent anywhere. */
(function () {
  "use strict";

  var VEF = {};
  var cache = {};

  var STATES = {
    AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California",
    CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "District of Columbia",
    FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois",
    IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana",
    ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan",
    MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana",
    NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey",
    NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota",
    OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania",
    RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee",
    TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington",
    WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming", PR: "Puerto Rico",
    GU: "Guam", VI: "U.S. Virgin Islands", AS: "American Samoa",
    MP: "Northern Mariana Islands"
  };
  VEF.STATES = STATES;

  var STATE_ALIASES = {
    "virgin islands": "VI", "us virgin islands": "VI", "u s virgin islands": "VI",
    "d c": "DC",   // "Washington, DC" stays a city search: it isn't an alias
    "northern marianas": "MP", "cnmi": "MP", "samoa": "AS"
  };

  // ---- small helpers ----------------------------------------------------
  VEF.esc = function (s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  };

  function Err(code, extra) {
    var e = new Error(code);
    e.code = code;
    if (extra) { for (var k in extra) { e[k] = extra[k]; } }
    return e;
  }
  VEF.Err = Err;

  VEF.getJSON = function (url) {
    if (cache[url]) { return cache[url]; }
    var pre = window.VEF_PRE && window.VEF_PRE[url];
    if (pre) {
      // Started early by the small script at the top of the results page.
      delete window.VEF_PRE[url];
      var early = pre.catch(function (status) { throw Err(status === 404 ? "missing" : "network"); });
      cache[url] = early;
      early.catch(function () { delete cache[url]; });
      return early;
    }
    var p = fetch(url, { credentials: "omit" }).then(function (r) {
      if (r.status === 404) { throw Err("missing"); }
      if (!r.ok) { throw Err("network"); }
      return r.json();
    }, function () {
      throw Err("network");
    });
    cache[url] = p;
    p.catch(function () { delete cache[url]; });
    return p;
  };

  // Mirrors pipeline/geo.py norm_name().
  var FIRST = { st: "saint", ste: "sainte", ft: "fort", mt: "mount", pt: "point" };
  VEF.normName = function (s) {
    s = String(s || "");
    if (s.normalize) { s = s.normalize("NFKD").replace(/[̀-ͯ]/g, ""); }
    s = s.toLowerCase().replace(/&/g, " and ").replace(/['’]/g, "").replace(/\./g, " ");
    s = s.replace(/[^a-z0-9]+/g, " ").trim();
    var t = s ? s.split(" ") : [];
    if (t.length && FIRST[t[0]]) { t[0] = FIRST[t[0]]; }
    return t.join(" ");
  };

  var STATE_BY_NAME = (function () {
    var m = {};
    Object.keys(STATES).forEach(function (c) { m[VEF.normName(STATES[c])] = c; });
    Object.keys(STATE_ALIASES).forEach(function (k) { m[k] = STATE_ALIASES[k]; });
    return m;
  })();
  var STATE_NAMES_LONGEST = Object.keys(STATE_BY_NAME).sort(function (a, b) { return b.length - a.length; });

  // ---- dates (visitor's own time zone) ---------------------------------
  var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var FULL = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function parseISO(iso) {
    var p = iso.split("-");
    return new Date(+p[0], +p[1] - 1, +p[2]);
  }
  VEF.today = function () {
    var d = new Date();
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  };
  VEF.fmtDay = function (iso) {
    var d = parseISO(iso);
    return DAYS[d.getDay()] + ", " + MONTHS[d.getMonth()] + " " + d.getDate();
  };
  VEF.fmtLong = function (iso) {
    var d = parseISO(iso);
    return FULL[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear();
  };
  VEF.fmtShortLong = function (iso) {
    var d = parseISO(iso);
    return MONTHS[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear();
  };
  /* Status of an offer on the visitor's local date:
     soon ("Starts Tue, Nov 10"), today, voucher (after the giveaway, voucher
     still good), ended. */
  VEF.status = function (o, today) {
    today = today || VEF.today();
    if (today < o.start) { return { k: "soon", label: "Starts " + VEF.fmtDay(o.start) }; }
    if (today <= o.end) {
      return { k: "today", label: o.end > today ? "Today, through " + VEF.fmtDay(o.end) : "Today" };
    }
    if (o.redeem_by && today <= o.redeem_by) {
      return { k: "voucher", label: "Voucher good until " + VEF.fmtShortLong(o.redeem_by) };
    }
    return { k: "ended", label: "Ended" };
  };
  VEF.dateText = function (o) {
    if (o.start === o.end) { return VEF.fmtDay(o.start); }
    return VEF.fmtDay(o.start) + " to " + VEF.fmtDay(o.end);
  };

  // ---- formatting -------------------------------------------------------
  VEF.fmtPhone = function (p) {
    return p && p.length === 10 ? "(" + p.slice(0, 3) + ") " + p.slice(3, 6) + "-" + p.slice(6) : "";
  };
  VEF.fmtMiles = function (d) {
    if (d < 0.1) { return "less than 0.1 miles"; }
    var v = d < 10 ? d.toFixed(1) : String(Math.round(d));
    return v + (v === "1.0" ? " mile" : " miles");
  };
  var DAYMAP = { Mo: "Mon", Tu: "Tue", We: "Wed", Th: "Thu", Fr: "Fri", Sa: "Sat", Su: "Sun", PH: "holidays" };
  function fmtTime(t) {
    var m = /^(\d{1,2}):(\d{2})$/.exec(t);
    if (!m) { return t; }
    var h = +m[1], min = m[2];
    if ((h === 0 || h === 24) && min === "00") { return "midnight"; }
    if (h === 12 && min === "00") { return "noon"; }
    var suffix = h >= 12 && h < 24 ? "p.m." : "a.m.";
    var h12 = h % 12 === 0 ? 12 : h % 12;
    return h12 + (min === "00" ? "" : ":" + min) + " " + suffix;
  }
  VEF.fmtHours = function (h) {
    if (!h) { return ""; }
    if (/^(24\/7|Mo-Su 00:00-24:00|Mo-Su 00:00-23:59)$/.test(h)) { return "Open 24 hours"; }
    return h.split(/;\s*/).map(function (part) {
      return part
        .replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b/g, function (d) { return DAYMAP[d]; })
        .replace(/(\d{1,2}:\d{2})-(\d{1,2}:\d{2})/g, function (_, a, b) { return fmtTime(a) + "–" + fmtTime(b); })
        .replace(/(Mon|Tue|Wed|Thu|Fri|Sat|Sun)-(Mon|Tue|Wed|Thu|Fri|Sat|Sun)/g, "$1–$2")
        .replace(/\boff\b|\bclosed\b/g, "closed");
    }).join("; ");
  };

  // ---- distance ---------------------------------------------------------
  VEF.miles = function (lat1, lng1, lat2, lng2) {
    var r = 3958.8, rad = Math.PI / 180;
    var dp = (lat2 - lat1) * rad, dl = (lng2 - lng1) * rad;
    var a = Math.sin(dp / 2) * Math.sin(dp / 2) +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * r * Math.asin(Math.min(1, Math.sqrt(a)));
  };

  // ---- data -------------------------------------------------------------
  VEF.loadOffers = function () {
    return VEF.getJSON("/data/offers.json").then(function (data) {
      if (!data._byId) {
        data._byId = {};
        data.offers.forEach(function (o) { data._byId[o.id] = o; });
      }
      return data;
    });
  };

  /* Turn what the visitor typed into a search. */
  VEF.parseQuery = function (q) {
    q = String(q || "").replace(/\s+/g, " ").trim();
    var m = /^(\d{5})(-\d{4})?$/.exec(q);
    if (m) { return { type: "zip", zip: m[1] }; }
    if (/^\d+$/.test(q.replace(/[\s-]/g, ""))) { return { type: "badzip", text: q }; }
    var n = VEF.normName(q);
    if (!n) { return { type: "empty" }; }
    if (STATE_BY_NAME[n]) { return { type: "state", st: STATE_BY_NAME[n] }; }
    if (n.length === 2 && STATES[n.toUpperCase()]) { return { type: "state", st: n.toUpperCase() }; }
    var parts = q.split(",");
    if (parts.length >= 2) {
      var stPart = VEF.normName(parts[parts.length - 1]);
      var cityPart = parts.slice(0, -1).join(",");
      var st = STATE_BY_NAME[stPart] || (stPart.length === 2 && STATES[stPart.toUpperCase()] ? stPart.toUpperCase() : null);
      if (st && VEF.normName(cityPart)) { return { type: "city", city: VEF.normName(cityPart), raw: cityPart.trim(), st: st }; }
    }
    // "Lebanon IN" or "Lebanon Indiana"
    for (var i = 0; i < STATE_NAMES_LONGEST.length; i++) {
      var name = STATE_NAMES_LONGEST[i];
      if (n.length > name.length + 1 && n.slice(-(name.length + 1)) === " " + name) {
        return { type: "city", city: n.slice(0, -(name.length + 1)), raw: q.slice(0, q.length - name.length).trim(), st: STATE_BY_NAME[name] };
      }
    }
    var toks = n.split(" ");
    var last = toks[toks.length - 1];
    if (toks.length > 1 && last.length === 2 && STATES[last.toUpperCase()]) {
      return { type: "city", city: toks.slice(0, -1).join(" "), raw: q.slice(0, -2).trim(), st: last.toUpperCase() };
    }
    return { type: "nostate", city: n, raw: q };
  };

  function editDistance(a, b) {
    if (Math.abs(a.length - b.length) > 2) { return 3; }
    var prev = [], cur, i, j;
    for (j = 0; j <= b.length; j++) { prev[j] = j; }
    for (i = 1; i <= a.length; i++) {
      cur = [i];
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
      prev = cur;
    }
    return prev[b.length];
  }

  /* Resolve a parsed query to an origin {lat, lng, label, st, zip?, cityKey?}. */
  VEF.resolve = function (p) {
    if (p.type === "zip") {
      return VEF.getJSON("/data/zip/" + p.zip.slice(0, 3) + ".json").then(function (shard) {
        var v = shard[p.zip];
        if (v === "M") { throw Err("military", { zip: p.zip }); }
        if (!v) { throw Err("unknown_zip", { zip: p.zip }); }
        return { lat: v[0], lng: v[1], st: v[3], zip: p.zip, city: v[2],
          label: (v[2] ? titleCase(v[2]) + ", " : "") + v[3] + " " + p.zip };
      }, function (e) {
        if (e.code === "missing") { throw Err("unknown_zip", { zip: p.zip }); }
        throw e;
      });
    }
    if (p.type === "city") {
      return VEF.getJSON("/data/city/" + p.st.toLowerCase() + ".json").then(function (shard) {
        var v = shard[p.city];
        if (v) {
          return { lat: v[0], lng: v[1], st: p.st, cityKey: p.city, city: v[2], label: v[2] + ", " + p.st };
        }
        var near = Object.keys(shard).filter(function (k) {
          return k.indexOf(p.city) === 0 || editDistance(k, p.city) <= 2;
        }).slice(0, 4).map(function (k) { return shard[k][2]; });
        throw Err("unknown_city", { city: p.raw, st: p.st, suggestions: near });
      });
    }
    return Promise.reject(Err(p.type));
  };

  function titleCase(s) {
    if (s !== s.toUpperCase()) { return s; }
    return s.toLowerCase().replace(/\b[a-z]/g, function (c) { return c.toUpperCase(); });
  }
  VEF.titleCase = titleCase;

  // ---- tiles ------------------------------------------------------------
  VEF.loadTileIndex = function () { return VEF.getJSON("/data/tiles/index.json"); };

  function leafIds(id, node, out) {
    if (node === 1) { out.push(id); return; }
    Object.keys(node).forEach(function (q) { leafIds(id + "_" + q, node[q], out); });
  }

  VEF.tilesFor = function (index, lat, lng, radius) {
    var deg = index.deg;
    var dLat = radius / 69.0;
    var dLng = radius / (69.17 * Math.max(0.05, Math.cos(lat * Math.PI / 180)));
    var ids = [];
    for (var i = Math.floor((lat - dLat) / deg); i <= Math.floor((lat + dLat) / deg); i++) {
      for (var j = Math.floor((lng - dLng) / deg); j <= Math.floor((lng + dLng) / deg); j++) {
        var id = i + "_" + j;
        if (index.tiles[id]) { leafIds(id, index.tiles[id], ids); }
      }
    }
    return ids;
  };

  /* Load every store within `radius` miles. Resolves to
     {records: [...each with .d miles], failed: number of tiles that failed}. */
  VEF.loadNearby = function (origin, radius) {
    return VEF.loadTileIndex().then(function (index) {
      var ids = VEF.tilesFor(index, origin.lat, origin.lng, radius);
      var failed = 0;
      return Promise.all(ids.map(function (id) {
        return VEF.getJSON("/data/tiles/" + id + ".json").catch(function () { failed++; return []; });
      })).then(function (lists) {
        var out = [];
        lists.forEach(function (list) {
          for (var k = 0; k < list.length; k++) {
            var r = list[k];
            var d = VEF.miles(origin.lat, origin.lng, r.la, r.lo);
            if (d <= radius) { out.push({ r: r, d: d }); }
          }
        });
        out.sort(function (a, b) { return a.d - b.d; });
        return { records: out, failed: failed, tiles: ids.length };
      });
    });
  };

  // ---- links ------------------------------------------------------------
  VEF.googleDir = function (lat, lng) {
    return "https://www.google.com/maps/dir/?api=1&destination=" + lat + "," + lng;
  };
  VEF.appleDir = function (lat, lng) {
    return "https://maps.apple.com/?daddr=" + lat + "," + lng;
  };
  VEF.findNearest = function (mapQuery, near) {
    return "https://www.google.com/maps/search/?api=1&query=" +
      encodeURIComponent(mapQuery + (near ? " near " + near : " near me"));
  };

  // ---- offer filters ----------------------------------------------------
  VEF.offerPasses = function (o, f) {
    if (f.offer && o.id !== f.offer) { return false; }
    if (f.cat && o.cat !== f.cat) { return false; }
    if (f.free && o.type !== "free") { return false; }
    if (f.who && o.tags.indexOf(f.who) < 0 && o.tags.indexOf("everyone") < 0) { return false; }
    return true;
  };

  // ---- remembered search (this browser only) ----------------------------
  VEF.saveLast = function (s) {
    try { localStorage.setItem("vef-last", JSON.stringify(s)); } catch (e) { /* ignore */ }
  };
  VEF.loadLast = function () {
    try { return JSON.parse(localStorage.getItem("vef-last") || "null"); } catch (e) { return null; }
  };
  VEF.takePending = function () {
    try {
      var v = sessionStorage.getItem("vef-pending");
      sessionStorage.removeItem("vef-pending");
      return v ? JSON.parse(v) : null;
    } catch (e) { return null; }
  };


  // Offline helper: keeps this site's own pages and data on the phone so a
  // reload works on a weak signal. Sends nothing anywhere.
  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () { /* optional */ });
    });
  }

  window.VEF = VEF;
})();
