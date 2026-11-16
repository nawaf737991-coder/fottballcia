(function () {
  "use strict";

  var CFG = Object.assign(
    { siteName: "Fottballcia", liveEndpoint: "", refreshMs: 15000, timeZone: "Asia/Riyadh" },
    window.FB_CONFIG || {}
  );
  var app = document.getElementById("app");
  var timer = null;
  var token = 0;

  var LIVE = { "1H": 1, "2H": 1, HT: 1, ET: 1, BT: 1, P: 1, LIVE: 1, INT: 1 };
  var FIN = { FT: 1, AET: 1, PEN: 1 };
  var LABEL = {
    NS: "لم تبدأ", TBD: "موعد غير محدد", HT: "استراحة", BT: "استراحة",
    FT: "انتهت", AET: "انتهت (إضافي)", PEN: "انتهت (ترجيح)", P: "ركلات ترجيح",
    PST: "تأجلت", CANC: "أُلغيت", SUSP: "أُوقفت", INT: "توقف مؤقت", ABD: "أُلغيت",
    AWD: "فوز إداري", WO: "انسحاب", LIVE: "مباشر",
    "1H": "الشوط الأول", "2H": "الشوط الثاني", ET: "وقت إضافي"
  };

  /* ---------- أدوات ---------- */
  function h(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v == null || v === false) return;
        if (k === "class") e.className = v;
        else if (k === "text") e.textContent = v;
        else e.setAttribute(k, v);
      });
    }
    (children || []).forEach(function (c) {
      if (c == null) return;
      e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return e;
  }

  function safeUrl(u) {
    return typeof u === "string" && /^https?:\/\//i.test(u) ? u : null;
  }

  function getJSON(url, bust) {
    var u = url + (bust ? (url.indexOf("?") < 0 ? "?" : "&") + "t=" + Date.now() : "");
    return fetch(u, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function safe(url) {
    return getJSON(url, true).catch(function () { return null; });
  }
  function getLive() {
    if (CFG.liveEndpoint) {
      return getJSON(CFG.liveEndpoint, true).catch(function () { return safe("data/live.json"); });
    }
    return safe("data/live.json");
  }

  function fmtTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString("ar-SA-u-nu-latn", {
        hour: "2-digit", minute: "2-digit", hour12: false, timeZone: CFG.timeZone
      });
    } catch (e) { return "--:--"; }
  }
  function fmtDay(ymd) {
    try {
      return new Date(ymd + "T12:00:00").toLocaleDateString("ar-SA-u-nu-latn", {
        weekday: "long", day: "numeric", month: "long"
      });
    } catch (e) { return ymd; }
  }
  function fmtStamp(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("ar-SA-u-nu-latn", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: CFG.timeZone
      });
    } catch (e) { return ""; }
  }

  /* ---------- مكونات ---------- */
  function logoImg(url) {
    var u = safeUrl(url);
    if (!u) return h("span", { class: "logo-ph" });
    return h("img", { class: "logo", src: u, alt: "", loading: "lazy", width: "28", height: "28" });
  }

  function statusLabel(m) {
    if ((m.status === "1H" || m.status === "2H" || m.status === "ET") && m.minute) return m.minute + "'";
    return LABEL[m.status] || m.status || "";
  }

  function matchRow(m) {
    var live = !!LIVE[m.status];
    var played = live || !!FIN[m.status];
    var mid;
    if (played) {
      mid = [
        h("div", { class: "score" }, [
          h("span", { text: m.gh == null ? "-" : String(m.gh) }),
          h("span", { class: "sep", text: "-" }),
          h("span", { text: m.ga == null ? "-" : String(m.ga) })
        ]),
        h("small", { class: live ? "live" : "", text: statusLabel(m) })
      ];
    } else {
      mid = [
        h("div", { class: "time", text: m.time ? fmtTime(m.time) : "--:--" }),
        h("small", { text: LABEL[m.status] || "لم تبدأ" })
      ];
    }
    return h("div", { class: "match" + (live ? " is-live" : "") }, [
      h("div", { class: "team home" }, [h("span", { class: "tname", text: m.home || "" }), logoImg(m.hl)]),
      h("div", { class: "mid" }, mid),
      h("div", { class: "team away" }, [logoImg(m.al), h("span", { class: "tname", text: m.away || "" })])
    ]);
  }

  function leagues(matches) {
    var groups = {}, order = [];
    matches.forEach(function (m) {
      var k = m.league || "أخرى";
      if (!groups[k]) { groups[k] = []; order.push(k); }
      groups[k].push(m);
    });
    var wrap = h("div");
    order.forEach(function (k) {
      wrap.appendChild(h("div", { class: "league" }, [
        h("div", { class: "league-name", text: k }),
        h("div", { class: "card" }, groups[k].map(matchRow))
      ]));
    });
    return wrap;
  }

  function empty(msg) { return h("div", { class: "empty", text: msg }); }

  function section(title, link, body) {
    return h("section", { class: "sec" }, [
      h("div", { class: "sec-head" }, [
        h("h2", { text: title }),
        link ? h("a", { href: link, text: "عرض الكل" }) : null
      ]),
      body
    ]);
  }

  function excerpt(t, n) {
    t = (t || "").replace(/\s+/g, " ").trim();
    return t.length > n ? t.slice(0, n).trim() + "…" : t;
  }

  function newsGrid(items) {
    return h("div", { class: "grid" }, items.map(function (it) {
      return h("a", { class: "news-card", href: "#/news/" + encodeURIComponent(it.id) }, [
        h("h3", { text: it.title || "" }),
        h("p", { text: excerpt(it.body, 130) }),
        h("div", { class: "meta", text: [fmtStamp(it.date), it.source].filter(Boolean).join(" • ") })
      ]);
    }));
  }

  function loading() {
    return h("div", null, [h("div", { class: "shimmer" }), h("div", { class: "shimmer" }), h("div", { class: "shimmer" })]);
  }

  /* ---------- الصفحات (كل صفحة تُرجع Promise<Node>) ---------- */
  function viewHome() {
    return Promise.all([getLive(), safe("data/today.json"), safe("data/news.json"), safe("data/results.json")])
      .then(function (r) {
        var live = (r[0] && r[0].matches) || [];
        var today = (r[1] && r[1].matches) || [];
        var news = (r[2] && r[2].items) || [];
        var days = (r[3] && r[3].days) || [];
        var upcoming = today.filter(function (m) { return !LIVE[m.status] && !FIN[m.status]; });
        var root = h("div");

        root.appendChild(h("div", { class: "hero" }, [
          h("h1", { text: "نتائج كرة القدم لحظة بلحظة" }),
          h("p", { text: "مباريات مباشرة، نتائج اليوم، وآخر الأخبار من الدوري السعودي والدوريات العالمية." }),
          h("span", { class: "pill" + (live.length ? " live" : "") }, [
            live.length ? h("i", { class: "dot" }) : null,
            live.length ? live.length + " مباراة جارية الآن" : "لا توجد مباريات جارية الآن"
          ])
        ]));

        root.appendChild(section("مباشر الآن", "#/live",
          live.length ? leagues(live.slice(0, 8)) : empty("لا توجد مباريات جارية حاليًا.")));
        root.appendChild(section("مباريات اليوم", "#/today",
          upcoming.length ? leagues(upcoming.slice(0, 8)) : empty("لا توجد مباريات قادمة اليوم.")));
        root.appendChild(section("آخر الأخبار", "#/news",
          news.length ? newsGrid(news.slice(0, 6)) : empty("لا توجد أخبار بعد.")));
        root.appendChild(section("آخر النتائج", "#/results",
          days.length && days[0].matches && days[0].matches.length
            ? leagues(days[0].matches.slice(0, 10))
            : empty("لا توجد نتائج منتهية بعد.")));
        return root;
      });
  }

  function viewLive() {
    return getLive().then(function (d) {
      var live = (d && d.matches) || [];
      var root = h("div");
      root.appendChild(h("h1", { class: "page-title", text: "المباريات المباشرة" }));
      root.appendChild(h("div", { class: "stamp", text: d && d.updated ? "آخر تحديث: " + fmtStamp(d.updated) : "" }));
      root.appendChild(live.length ? leagues(live) : empty("لا توجد مباريات جارية الآن."));
      return root;
    });
  }

  function viewToday() {
    return safe("data/today.json").then(function (d) {
      var ms = (d && d.matches) || [];
      var root = h("div");
      root.appendChild(h("h1", { class: "page-title", text: "مباريات اليوم" }));
      root.appendChild(h("div", { class: "stamp", text: d && d.updated ? "آخر تحديث: " + fmtStamp(d.updated) : "" }));
      root.appendChild(ms.length ? leagues(ms) : empty("لا توجد بيانات لمباريات اليوم بعد."));
      return root;
    });
  }

  function viewResults() {
    return safe("data/results.json").then(function (d) {
      var days = (d && d.days) || [];
      var root = h("div");
      root.appendChild(h("h1", { class: "page-title", text: "النتائج" }));
      if (!days.length) { root.appendChild(empty("لا توجد نتائج بعد.")); return root; }
      days.forEach(function (day) {
        root.appendChild(h("section", { class: "day" }, [
          h("h2", { text: fmtDay(day.date) }),
          day.intro ? h("p", { class: "intro", text: day.intro }) : null,
          leagues(day.matches || [])
        ]));
      });
      return root;
    });
  }

  function viewNews() {
    return safe("data/news.json").then(function (d) {
      var items = (d && d.items) || [];
      var root = h("div");
      root.appendChild(h("h1", { class: "page-title", text: "آخر الأخبار" }));
      root.appendChild(items.length ? newsGrid(items) : empty("لا توجد أخبار بعد."));
      return root;
    });
  }

  function viewArticle(id) {
    id = decodeURIComponent(id);
    return safe("data/news.json").then(function (d) {
      var it = ((d && d.items) || []).filter(function (x) { return x.id === id; })[0];
      var root = h("div", { class: "article" });
      root.appendChild(h("a", { class: "back", href: "#/news", text: "← كل الأخبار" }));
      if (!it) { root.appendChild(empty("الخبر غير موجود.")); return root; }
      document.title = it.title + " | " + CFG.siteName;
      root.appendChild(h("h1", { text: it.title }));
      root.appendChild(h("div", { class: "stamp", text: fmtStamp(it.date) }));
      var body = h("div", { class: "body" });
      String(it.body || "").split(/\n+/).forEach(function (p) {
        if (p.trim()) body.appendChild(h("p", { text: p.trim() }));
      });
      root.appendChild(body);
      var link = safeUrl(it.link);
      if (link) {
        root.appendChild(h("div", { class: "src" }, [
          "المصدر الأصلي: ",
          h("a", { href: link, target: "_blank", rel: "nofollow noopener noreferrer", text: it.source || link })
        ]));
      }
      return root;
    });
  }

  /* ---------- التوجيه ---------- */
  var ROUTES = [
    { re: /^(#\/?)?$/, title: "الرئيسية", nav: "home", view: viewHome, auto: true },
    { re: /^#\/live$/, title: "مباشر", nav: "live", view: viewLive, auto: true },
    { re: /^#\/today$/, title: "مباريات اليوم", nav: "today", view: viewToday, auto: true },
    { re: /^#\/results$/, title: "النتائج", nav: "results", view: viewResults },
    { re: /^#\/news$/, title: "الأخبار", nav: "news", view: viewNews },
    { re: /^#\/news\/(.+)$/, title: "خبر", nav: "news", view: function (m) { return viewArticle(m[1]); } }
  ];

  function route() {
    clearInterval(timer);
    var hash = location.hash || "#/";
    var r = null, m = null;
    for (var i = 0; i < ROUTES.length; i++) {
      m = hash.match(ROUTES[i].re);
      if (m) { r = ROUTES[i]; break; }
    }
    if (!r) { r = ROUTES[0]; m = []; }

    var my = ++token;
    document.title = r.title + " | " + CFG.siteName;
    Array.prototype.forEach.call(document.querySelectorAll(".nav a"), function (a) {
      a.classList.toggle("on", a.getAttribute("data-nav") === r.nav);
    });

    app.replaceChildren(loading());
    window.scrollTo(0, 0);
    r.view(m).then(function (node) {
      if (my === token) app.replaceChildren(node);
    }).catch(function () {
      if (my === token) app.replaceChildren(empty("تعذر تحميل البيانات. حاول مرة أخرى بعد قليل."));
    });

    if (r.auto) {
      timer = setInterval(function () {
        r.view(m).then(function (node) {
          if (my === token) app.replaceChildren(node);
        }).catch(function () {});
      }, Math.max(5000, CFG.refreshMs));
    }
  }

  window.addEventListener("hashchange", route);
  route();
})();
