/* مركز المباراة - عالم المستديرة. يُحمَّل داخل صفحة /p/match.html?id=FIXTURE_ID */
(function () {
  "use strict";
  var SERVER = "https://178-62-45-69.sslip.io";
  var SITE = "https://www.fottballcia.com";
  var NAMES_URL = "https://nawaf737991-coder.github.io/fottballcia/data/names_cache.json";
  var TW_URL = "https://nawaf737991-coder.github.io/fottballcia/data/embed_tweets.json";
  var tweets = [], videos = [], lastKey = "";
  var VID_URL = "https://nawaf737991-coder.github.io/fottballcia/data/embed_videos.json";
  var TW_RE = /^https:\/\/(x|twitter)\.com\/[A-Za-z0-9_]{1,15}\/status\/\d+$/;
  function twBlock(t) {
    return "<div class='mc-tw'><blockquote class='twitter-tweet' data-lang='ar' data-dnt='true'><a href='" + esc(t.u) + "'></a></blockquote></div>";
  }
  var DISQUS = ""; // ضع اسم موقعك في Disqus هنا لتفعيل قسم النقاش، مثال: "fottballcia"
  var TABLES = {307: "saudi-league-table", 39: "premier-league-table", 140: "laliga-table", 135: "serie-table",
    78: "bundesliga-table", 61: "ligue1-table", 2: "champions-league-table", 12: "caf-champions-league-table",
    17: "afc-champions-league-table"};
  var LG = {307: "الدوري السعودي للمحترفين", 39: "الدوري الإنجليزي الممتاز", 140: "الدوري الإسباني", 135: "الدوري الإيطالي", 78: "الدوري الألماني", 61: "الدوري الفرنسي", 2: "دوري أبطال أوروبا", 3: "الدوري الأوروبي", 848: "دوري المؤتمر الأوروبي", 17: "دوري أبطال آسيا للنخبة", 12: "دوري أبطال أفريقيا", 1: "كأس العالم", 32: "تصفيات كأس العالم - أوروبا", 30: "تصفيات كأس العالم - آسيا", 29: "تصفيات كأس العالم - أفريقيا", 143: "كأس ملك إسبانيا", 45: "كأس الاتحاد الإنجليزي", 48: "كأس الرابطة الإنجليزية", 556: "كأس السوبر الإسباني", 480: "الدوري المغربي"};
  var REASON = [[/Knee/i, "الركبة"], [/Ankle/i, "الكاحل"], [/Hamstring/i, "أوتار الركبة"], [/Muscle/i, "عضلية"], [/Calf/i, "السمانة"], [/Thigh/i, "الفخذ"], [/Groin/i, "الأربية"], [/Foot/i, "القدم"], [/Back/i, "الظهر"], [/Shoulder/i, "الكتف"], [/Achilles/i, "وتر أخيل"], [/Illness/i, "مرض"], [/Suspended/i, "إيقاف"], [/Red Card/i, "طرد"], [/Yellow Card/i, "إنذارات"], [/Off the roster|Not in squad/i, "خارج القائمة"], [/Injury|Injured/i, "إصابة"]];
  function reasonAr(r) { if (!r) return ""; var out = []; REASON.forEach(function (x) { if (x[0].test(r) && out.indexOf(x[1]) < 0) out.push(x[1]); }); return out.length ? out.join(" · ") : ""; }
  function lgName(d) { return LG[d.league.id] || names[d.league.name] || d.league.name; }
  var root = document.getElementById("mc-root");
  if (!root) return;
  var id = (new URLSearchParams(location.search).get("id") || "").replace(/\D/g, "");
  var names = {}, data = null, tab = "sum", timer = null, lastOk = 0;

  var css = "" +
    "#mc-root{direction:rtl;font-family:inherit;color:#142a43;max-width:820px;margin:0 auto;line-height:1.6}" +
    "#mc-root *{box-sizing:border-box}" +
    ".mc-head{background:linear-gradient(160deg,#153a5b,#0d2740);color:#fff;border-radius:16px;padding:16px 12px 12px;text-align:center}" +
    ".mc-lg{display:flex;align-items:center;justify-content:center;gap:8px;font-size:14px;opacity:.92}" +
    ".mc-lg img{width:22px;height:22px;background:#fff;border-radius:50%;padding:2px}" +
    ".mc-date{font-size:12.5px;opacity:.75;margin-top:2px}" +
    ".mc-row{display:grid;grid-template-columns:1fr auto 1fr;align-items:start;gap:6px;margin:14px 0 6px}" +
    ".mc-team img{width:60px;height:60px;object-fit:contain;background:#fff;border-radius:50%;padding:6px}" +
    ".mc-team b{display:block;font-size:15px;margin-top:6px}" +
    ".mc-score{font-size:38px;font-weight:900;letter-spacing:2px;direction:ltr;padding-top:10px;white-space:nowrap}" +
    ".mc-st{display:inline-block;font-size:12.5px;font-weight:800;border-radius:20px;padding:2px 12px;background:rgba(255,255,255,.16)}" +
    ".mc-st.live{background:#e5253b;animation:mcp 1.4s infinite}" +
    "@keyframes mcp{50%{opacity:.55}}" +
    ".mc-sc{font-size:12.5px;opacity:.9;margin-top:6px;text-align:center}" +
    ".mc-sc div{margin:1px 0}" +
    ".mc-tabs{display:flex;gap:6px;overflow-x:auto;position:sticky;top:0;z-index:5;background:#f4f7fb;padding:10px 2px;margin:10px 0;-webkit-overflow-scrolling:touch}" +
    ".mc-tabs button{flex:0 0 auto;border:0;background:#fff;color:#153a5b;font:inherit;font-weight:800;font-size:14px;padding:8px 16px;border-radius:20px;box-shadow:0 1px 3px rgba(0,0,0,.12);cursor:pointer}" +
    ".mc-tabs button.on{background:#153a5b;color:#fff}" +
    ".mc-card{background:#fff;border:1px solid #e6ebf1;border-radius:14px;padding:12px 14px;margin:0 0 12px}" +
    ".mc-card h2{font-size:17px;margin:0 0 8px;color:#153a5b}" +
    ".mc-yt{position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:10px;margin:6px 0;background:#000}.mc-yt iframe{position:absolute;top:0;left:0;width:100%;height:100%;border:0}" +
    ".mc-tw{margin:8px auto;max-width:550px;min-height:60px}.mc-tw .twitter-tweet{margin:0 auto!important}" +
    ".mc-ev{display:grid;grid-template-columns:1fr 46px 1fr;gap:4px;align-items:center;padding:6px 0;border-bottom:1px dashed #e6ebf1;font-size:14px}" +
    ".mc-ev:last-child{border:0}.mc-ev .m{text-align:center;font-weight:800;color:#5b6b7c;font-size:13px}" +
    ".mc-ev .h{text-align:right}.mc-ev .a{text-align:left}.mc-ev small{display:block;color:#7a8a99;font-size:12px}" +
    ".mc-pitch{position:relative;background:repeating-linear-gradient(0deg,#2e8b4e 0,#2e8b4e 10%,#2a8148 10%,#2a8148 20%);border-radius:12px;height:430px;border:2px solid #fff;outline:1px solid #cfe3d5;margin:6px 0}" +
    ".mc-pitch:before{content:'';position:absolute;left:8%;right:8%;top:50%;border-top:2px solid rgba(255,255,255,.55)}" +
    ".mc-pl{position:absolute;transform:translate(-50%,-50%);text-align:center;width:64px}" +
    ".mc-pl i{display:block;margin:0 auto;width:30px;height:30px;line-height:30px;border-radius:50%;background:#fff;color:#153a5b;font-style:normal;font-weight:900;font-size:13px;border:2px solid #153a5b}" +
    ".mc-pl span{display:block;color:#fff;font-size:10.5px;font-weight:700;text-shadow:0 1px 2px #000;line-height:1.15;margin-top:2px}" +
    ".mc-list{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;font-size:13.5px}" +
    ".mc-list div{padding:3px 0;border-bottom:1px solid #f0f3f7}.mc-list b{color:#153a5b;display:inline-block;min-width:24px}" +
    ".mc-bar{margin:10px 0}.mc-bar .t{display:flex;justify-content:space-between;font-size:13.5px;font-weight:700}" +
    ".mc-bar .b{display:flex;height:8px;border-radius:5px;overflow:hidden;background:#e6ebf1;margin-top:3px;direction:ltr}" +
    ".mc-bar .b i{display:block;height:100%}" +
    ".mc-tb{width:100%;border-collapse:collapse;font-size:13.5px}.mc-tb td,.mc-tb th{padding:6px 3px;text-align:center;border-bottom:1px solid #eef1f5}" +
    ".mc-tb th{background:#153a5b;color:#fff}.mc-tb td:nth-child(2){text-align:right;font-weight:700}.mc-tb img{width:18px;height:18px;vertical-align:middle;margin-left:5px}" +
    ".mc-tb tr.me{background:#fff4cc}" +
    ".mc-pr{display:flex;height:26px;border-radius:8px;overflow:hidden;direction:ltr;font-size:12.5px;font-weight:800;color:#fff}" +
    ".mc-pr div{display:flex;align-items:center;justify-content:center;min-width:8%}" +
    ".mc-mini{font-size:13.5px;padding:5px 0;border-bottom:1px dashed #e6ebf1}" +
    ".mc-lk{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}.mc-lk a{background:#153a5b;color:#fff;text-decoration:none;padding:7px 14px;border-radius:18px;font-size:13.5px;font-weight:700}" +
    ".mc-note{font-size:12.5px;color:#6b7a89;margin:6px 0}.mc-err{text-align:center;padding:40px 10px;color:#5b6b7c}" +
    "@media(max-width:520px){.mc-score{font-size:32px}.mc-list{grid-template-columns:1fr}.mc-pitch{height:400px}}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
  function ar(n) { return esc(names[n] || n || ""); }
  function fmtDate(iso) {
    try { return new Intl.DateTimeFormat("ar-SA-u-nu-latn", {timeZone: "Asia/Riyadh", weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit"}).format(new Date(iso)) + " بتوقيت السعودية"; } catch (e) { return ""; }
  }
  function statusOf(d) {
    var s = d.status, m = d.elapsed ? d.elapsed + (d.extra ? "+" + d.extra : "") + "'" : "";
    if (s === "NS" || s === "TBD") return ["لم تبدأ", ""];
    if (s === "HT") return ["استراحة", "live"];
    if (s === "1H" || s === "2H" || s === "ET" || s === "LIVE" || s === "BT") return ["مباشر " + m, "live"];
    if (s === "P") return ["ركلات الترجيح", "live"];
    if (s === "FT") return ["انتهت", ""]; if (s === "AET") return ["انتهت بعد وقت إضافي", ""]; if (s === "PEN") return ["انتهت بركلات الترجيح", ""];
    if (s === "PST") return ["تأجلت", ""]; if (s === "CANC") return ["أُلغيت", ""]; if (s === "SUSP" || s === "INT") return ["متوقفة", "live"];
    return [d.label || s, ""];
  }
  function isLive(d) { return ["1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"].indexOf(d.status) >= 0; }
  function min(e) { return e.m + (e.x ? "+" + e.x : "") + "'"; }
  function icon(e) {
    var t = e.type, dt = e.detail || "";
    if (t === "Goal") return dt === "Own Goal" ? "⚽🔴" : dt === "Missed Penalty" ? "❌" : dt === "Penalty" ? "⚽(ج)" : "⚽";
    if (t === "Card") return dt.indexOf("Red") >= 0 || dt === "Second Yellow card" ? "🟥" : "🟨";
    if (t === "subst") return "🔁";
    if (t === "Var") return "📺";
    return "•";
  }
  function evText(e) {
    var t = e.type, dt = e.detail || "", p = ar(e.p), a = e.a ? ar(e.a) : "";
    if (t === "Goal") return "<b>" + p + "</b>" + (dt === "Own Goal" ? " <small>(هدف عكسي)</small>" : dt === "Penalty" ? " <small>(ركلة جزاء)</small>" : dt === "Missed Penalty" ? " <small>(ركلة جزاء ضائعة)</small>" : (a ? "<small>تمريرة: " + a + "</small>" : ""));
    if (t === "Card") return "<b>" + p + "</b><small>" + (dt.indexOf("Red") >= 0 ? "بطاقة حمراء" : dt === "Second Yellow card" ? "إنذار ثانٍ وطرد" : "بطاقة صفراء") + "</small>";
    if (t === "subst") return "<b>" + a + "</b> <small>يدخل بدلًا من " + p + "</small>";
    if (t === "Var") return "<b>" + p + "</b><small>حكم الفيديو: " + (dt === "Goal cancelled" ? "إلغاء هدف" : dt === "Penalty confirmed" ? "تأكيد ركلة جزاء" : esc(dt)) + "</small>";
    return esc(dt);
  }
  function scorers(d, side) {
    var tid = d[side].id, out = [];
    (d.events || []).forEach(function (e) {
      if (e.type !== "Goal" || e.detail === "Missed Penalty") return;
      var own = e.detail === "Own Goal";
      if ((e.team === tid) !== own) out.push("<div>" + ar(e.p) + " " + min(e) + (own ? " (ع)" : e.detail === "Penalty" ? " (ج)" : "") + "</div>");
    });
    return out.join("");
  }

  function head(d) {
    var s = statusOf(d), g = d.goals || {}, show = d.status !== "NS" && d.status !== "TBD" && g.home != null;
    var pen = d.score && d.score.penalty && d.score.penalty.home != null ? "<div class='mc-date'>ركلات الترجيح: " + d.score.penalty.home + " - " + d.score.penalty.away + "</div>" : "";
    return "<div class='mc-head'><div class='mc-lg'><img src='" + esc(d.league.logo) + "' alt=''><span>" + esc(lgName(d)) + (d.league.round ? " · " + esc(String(d.league.round).replace("Regular Season - ", "الجولة ")) : "") + "</span></div>" +
      "<div class='mc-date'>" + esc(fmtDate(d.kickoff)) + "</div>" +
      "<div class='mc-row'><div class='mc-team'><img src='" + esc(d.home.logo) + "' alt=''><b>" + ar(d.home.name) + "</b></div>" +
      "<div><div class='mc-score'>" + (show ? g.home + " - " + g.away : "VS") + "</div><span class='mc-st " + s[1] + "'>" + esc(s[0]) + "</span></div>" +
      "<div class='mc-team'><img src='" + esc(d.away.logo) + "' alt=''><b>" + ar(d.away.name) + "</b></div></div>" + pen +
      "<div class='mc-row' style='margin:2px 0 0'><div class='mc-sc'>" + scorers(d, "home") + "</div><div></div><div class='mc-sc'>" + scorers(d, "away") + "</div></div></div>";
  }

  function summary(d) {
    var h = "";
    var ev = (d.events || []).slice().sort(function (a, b) { return (a.m + (a.x || 0) / 100) - (b.m + (b.x || 0) / 100); });
    if (ev.length) {
      h += "<div class='mc-card'><h2>أحداث المباراة</h2>";
      ev.forEach(function (e) {
        var home = e.team === d.home.id, cell = "<span>" + icon(e) + "</span> " + evText(e);
        h += "<div class='mc-ev'><div class='h'>" + (home ? cell : "") + "</div><div class='m'>" + min(e) + "</div><div class='a'>" + (home ? "" : cell) + "</div></div>";
        tweets.forEach(function (t) { if (!t.used && t.m != null && Number(t.m) === Number(e.m)) { t.used = 1; h += twBlock(t); } });
      });
      h += "</div>";
    } else if (d.status === "NS" || d.status === "TBD") {
      h += "<div class='mc-card'><h2>معلومات المباراة</h2><div class='mc-mini'>الموعد: " + esc(fmtDate(d.kickoff)) + "</div>" +
        (d.venue ? "<div class='mc-mini'>الملعب: " + esc(d.venue) + (d.city ? " - " + esc(d.city) : "") + "</div>" : "") +
        (d.referee ? "<div class='mc-mini'>الحكم: " + esc(d.referee) + "</div>" : "") + "</div>";
    } else h += "<div class='mc-card'><div class='mc-note'>لا توجد أحداث مسجلة حتى الآن.</div></div>";
    if (videos.length && (d.status === "FT" || d.status === "AET" || d.status === "PEN")) {
      h += "<div class='mc-card'><h2>ملخص المباراة بالفيديو</h2>" + videos.map(function (v) {
        return "<div class='mc-yt'><iframe src='https://www.youtube.com/embed/" + v.v + "' allowfullscreen loading='lazy' title='ملخص المباراة'></iframe></div><div class='mc-note'>المصدر: قناة " + esc(v.c) + " الرسمية على يوتيوب.</div>";
      }).join("") + "</div>";
    }
    var rest = tweets.filter(function (t) { return !t.used; });
    if (rest.length) h += "<div class='mc-card'><h2>مقاطع المباراة</h2>" + rest.map(twBlock).join("") + "<div class='mc-note'>مقاطع مضمّنة من حسابات رسمية على X.</div></div>";
    if (d.prediction && d.prediction.home) {
      var p = d.prediction, n = function (x) { return parseFloat(x) || 0; };
      h += "<div class='mc-card'><h2>توقع الفائز</h2><div class='mc-pr'><div style='background:#153a5b;flex:" + Math.max(n(p.home), 8) + "'>" + esc(p.home) + "</div><div style='background:#8a97a6;flex:" + Math.max(n(p.draw), 8) + "'>" + esc(p.draw) + "</div><div style='background:#c9902b;flex:" + Math.max(n(p.away), 8) + "'>" + esc(p.away) + "</div></div>" +
        "<div class='mc-note'>" + ar(d.home.name) + " · تعادل · " + ar(d.away.name) + " — توقع إحصائي من API-Football وليس نتيجة مضمونة.</div></div>";
    }
    [["form_h", d.home], ["form_a", d.away]].forEach(function (x) {
      var arr = d[x[0]]; if (!arr || !arr.length) return;
      h += "<div class='mc-card'><h2>آخر 5 مباريات: " + ar(x[1].name) + "</h2>" + arr.map(function (m) { return "<div class='mc-mini'>" + ar(m.home) + " <b>" + m.gh + " - " + m.ga + "</b> " + ar(m.away) + "</div>"; }).join("") + "</div>";
    });
    if (d.h2h && d.h2h.length) h += "<div class='mc-card'><h2>المواجهات السابقة</h2>" + d.h2h.map(function (m) { return "<div class='mc-mini'>" + esc(m.date.slice(0, 10)) + " · " + ar(m.home) + " <b>" + m.gh + " - " + m.ga + "</b> " + ar(m.away) + "</div>"; }).join("") + "</div>";
    var inj = d.injuries || [];
    h += "<div class='mc-card'><h2>الإصابات والإيقافات</h2>";
    [d.home, d.away].forEach(function (t) {
      var l = inj.filter(function (i) { return i.team === t.id; });
      h += "<div class='mc-mini'><b>" + ar(t.name) + ":</b> " + (l.length ? l.map(function (i) { return ar(i.n) + " (" + esc(i.type === "Missing Fixture" ? "غائب" : i.type === "Questionable" ? "مشكوك" : i.type || "") + (reasonAr(i.reason) ? " - " + esc(reasonAr(i.reason)) : "") + ")"; }).join("، ") : "لا توجد حالات مسجلة") + "</div>";
    });
    h += "</div>";
    h += "<div class='mc-card'><h2>مفتاح الرموز</h2><div class='mc-note'>⚽ هدف · ⚽(ج) ركلة جزاء · ⚽🔴 هدف عكسي · ❌ ركلة جزاء ضائعة · 🟨 بطاقة صفراء · 🟥 بطاقة حمراء · 🔁 تبديل · 📺 حكم الفيديو (VAR)</div></div>";
    return h;
  }

  function marks(d, name) {
    var s = "";
    (d.events || []).forEach(function (e) {
      if (e.p === name || (e.type === "subst" && e.a === name)) {
        if (e.type === "Goal" && e.p === name && e.detail !== "Own Goal" && e.detail !== "Missed Penalty") s += "⚽";
        if (e.type === "Card" && e.p === name) s += e.detail.indexOf("Red") >= 0 ? "🟥" : "🟨";
        if (e.type === "subst") s += e.p === name ? " <span dir='ltr'>⬇" + e.m + "′</span>" : " <span dir='ltr'>⬆" + e.m + "′</span>";
      }
    });
    return s;
  }
  function pitch(d, l, team) {
    var rows = {}, R = 0;
    l.xi.forEach(function (p) { if (!p.grid) return; var a = p.grid.split(":"), r = +a[0], c = +a[1]; (rows[r] = rows[r] || []).push([c, p]); R = Math.max(R, r); });
    var h = "<div class='mc-pitch'>";
    Object.keys(rows).forEach(function (r) {
      var arr = rows[r].sort(function (a, b) { return a[0] - b[0]; }), n = arr.length;
      arr.forEach(function (x, i) {
        var y = R > 1 ? 93 - (r - 1) / (R - 1) * 82 : 50, xx = (i + 1) / (n + 1) * 100, p = x[1];
        h += "<div class='mc-pl' style='left:" + xx + "%;top:" + y + "%'><i>" + esc(p.num) + "</i><span>" + ar((p.n || "").split(" ").slice(-1)[0] === p.n ? p.n : p.n) + "</span></div>";
      });
    });
    return h + "</div>";
  }
  function lineups(d) {
    if (!d.lineups || !d.lineups.length) return "<div class='mc-card'><div class='mc-note'>التشكيلة غير متاحة بعد. تُنشر عادةً قبل المباراة بنحو ساعة.</div></div>";
    var h = "";
    d.lineups.forEach(function (l) {
      var t = l.team === d.home.id ? d.home : d.away;
      h += "<div class='mc-card'><h2>" + ar(t.name) + (l.formation ? " · " + esc(l.formation) : "") + "</h2>" + pitch(d, l, t) +
        "<div class='mc-list'>" + l.xi.map(function (p) { return "<div><b>" + esc(p.num) + "</b>" + ar(p.n) + " " + marks(d, p.n) + (d.ratings && d.ratings[p.id] ? " <small>(" + esc(d.ratings[p.id]) + ")</small>" : "") + "</div>"; }).join("") + "</div>" +
        (l.subs && l.subs.length ? "<h2 style='margin-top:12px'>البدلاء</h2><div class='mc-list'>" + l.subs.map(function (p) { return "<div><b>" + esc(p.num) + "</b>" + ar(p.n) + " " + marks(d, p.n) + "</div>"; }).join("") + "</div>" : "") +
        (l.coach ? "<div class='mc-mini'>المدرب: <b>" + ar(l.coach) + "</b></div>" : "") + "</div>";
    });
    return h;
  }
  var STAT = {"Ball Possession": "الاستحواذ", "Total Shots": "التسديدات", "Shots on Goal": "تسديدات على المرمى", "Corner Kicks": "الركنيات", "Fouls": "الأخطاء", "Offsides": "التسلل", "Yellow Cards": "بطاقات صفراء", "Red Cards": "بطاقات حمراء", "Goalkeeper Saves": "تصديات الحارس", "Passes %": "دقة التمرير %", "Total passes": "التمريرات", "Shots off Goal": "تسديدات خارج المرمى", "Blocked Shots": "تسديدات مصدودة", "expected_goals": "الأهداف المتوقعة (xG)"};
  function stats(d) {
    if (!d.stats || !d.stats.length) return "<div class='mc-card'><div class='mc-note'>الإحصائيات تظهر بعد انطلاق المباراة.</div></div>";
    var order = ["Ball Possession", "Total Shots", "Shots on Goal", "Corner Kicks", "Fouls", "Offsides"];
    var list = d.stats.filter(function (s) { return STAT[s.t]; }).sort(function (a, b) { var i = order.indexOf(a.t), j = order.indexOf(b.t); return (i < 0 ? 99 : i) - (j < 0 ? 99 : j); });
    return "<div class='mc-card'><h2>إحصائيات المباراة</h2>" + list.map(function (s) {
      var tot = (s.h + s.a) || 1, pct = s.t === "Ball Possession" || s.t === "Passes %", fh = Math.round(s.h / tot * 100);
      return "<div class='mc-bar'><div class='t'><span>" + (pct ? s.h + "%" : s.h) + "</span><span>" + STAT[s.t] + "</span><span>" + (pct ? s.a + "%" : s.a) + "</span></div><div class='b'><i style='width:" + fh + "%;background:#153a5b'></i><i style='width:" + (100 - fh) + "%;background:#c9902b'></i></div></div>";
    }).join("") + "<div class='mc-note'>الأزرق: " + ar(d.home.name) + " · الذهبي: " + ar(d.away.name) + "</div></div>";
  }
  function table(d) {
    if (!d.table || !d.table.length) return "<div class='mc-card'><div class='mc-note'>الترتيب غير متاح لهذه البطولة.</div></div>";
    var rows = "", g = null;
    d.table.forEach(function (r) {
      if (r.g && r.g !== g) { rows += "<tr><td colspan='6' style='background:#e6ebf1;font-weight:800'>" + esc(r.g) + "</td></tr>"; g = r.g; }
      var me = r.id === d.home.id || r.id === d.away.id;
      rows += "<tr class='" + (me ? "me" : "") + "'><td>" + r.r + "</td><td><img src='" + esc(r.l) + "' alt=''>" + ar(r.t) + "</td><td>" + r.p + "</td><td dir='ltr'>" + (r.gd > 0 ? "+" : "") + r.gd + "</td><td><b>" + r.pts + "</b></td></tr>";
    });
    var tp = TABLES[d.league.id];
    return "<div class='mc-card'><h2>ترتيب " + esc(lgName(d)) + "</h2><div style='overflow-x:auto'><table class='mc-tb'><thead><tr><th>#</th><th>الفريق</th><th>لعب</th><th>+/-</th><th>نقاط</th></tr></thead><tbody>" + rows + "</tbody></table></div>" +
      (tp ? "<div class='mc-lk'><a href='" + SITE + "/p/" + tp + ".html'>الترتيب الكامل والهدافون</a></div>" : "") + "</div>";
  }
  function links(d) {
    var q = encodeURIComponent((names[d.home.name] || d.home.name) + " " + (names[d.away.name] || d.away.name));
    return "<div class='mc-card'><h2>روابط مفيدة</h2><div class='mc-lk'><a href='" + SITE + "/p/matches-today.html'>مباريات اليوم</a>" +
      (TABLES[d.league.id] ? "<a href='" + SITE + "/p/" + TABLES[d.league.id] + ".html'>جدول الترتيب</a>" : "") +
      "<a href='" + SITE + "/search?q=" + q + "'>تقرير المباراة</a></div></div>";
  }
  function discuss() {
    if (!DISQUS) return "";
    return "<div class='mc-card'><h2>النقاش</h2><div id='disqus_thread'></div></div>";
  }

  function render() {
    tweets.forEach(function (t) { t.used = 0; });
    var d = data, body = tab === "sum" ? summary(d) : tab === "lu" ? lineups(d) : tab === "st" ? stats(d) : table(d);
    var tabs = [["sum", "الملخص"], ["lu", "التشكيلة"], ["st", "الإحصائيات"], ["tb", "الترتيب"]];
    root.innerHTML = head(d) + "<div class='mc-tabs'>" + tabs.map(function (t) { return "<button data-t='" + t[0] + "' class='" + (t[0] === tab ? "on" : "") + "'>" + t[1] + "</button>"; }).join("") + "</div>" + body + links(d) +
      "<div class='mc-note'>" + (isLive(d) ? "المباراة مباشرة: تتحدث الصفحة تلقائيًا كل 60 ثانية. " : "") + "المصدر: API-Football. جميع المواعيد بتوقيت السعودية.</div>" + discuss();
    root.querySelectorAll(".mc-tabs button").forEach(function (b) { b.onclick = function () { tab = b.getAttribute("data-t"); render(); }; });
    if (tab === "sum" && tweets.length) {
      if (window.twttr && window.twttr.widgets) window.twttr.widgets.load(root);
      else if (!window.TW_LOADING) { window.TW_LOADING = 1; var ws = document.createElement("script"); ws.async = true; ws.src = "https://platform.twitter.com/widgets.js"; document.body.appendChild(ws); }
    }
    document.title = (names[d.home.name] || d.home.name) + " × " + (names[d.away.name] || d.away.name) + " | مركز المباراة | عالم المستديرة";
    if (DISQUS && !window.DISQUS_LOADED) {
      window.DISQUS_LOADED = 1; window.disqus_config = function () { this.page.identifier = "match-" + id; this.page.url = location.href; };
      var s = document.createElement("script"); s.src = "https://" + DISQUS + ".disqus.com/embed.js"; s.setAttribute("data-timestamp", +new Date()); document.body.appendChild(s);
    }
  }

  function load() {
    return fetch(SERVER + "/match.json?id=" + id, {cache: "no-store"}).then(function (r) {
      if (r.status === 404) throw new Error("nf");
      if (!r.ok) throw new Error("err");
      return r.json();
    }).then(function (d) {
      var k = JSON.stringify(d, function (kk, v) { return kk === "generated" ? 0 : v; });
      data = d; lastOk = Date.now();
      if (k !== lastKey) { lastKey = k; render(); }
      clearInterval(timer);
      if (isLive(d)) timer = setInterval(function () { if (!document.hidden) load().catch(function () {}); }, 60000);
      else if (d.status === "NS") timer = setInterval(function () { if (!document.hidden) load().catch(function () {}); }, 300000);
    });
  }
  if (!id) { root.innerHTML = "<div class='mc-err'>اختر مباراة من <a href='" + SITE + "/p/matches-today.html'>صفحة مباريات اليوم</a> لعرض تفاصيلها.</div>"; return; }
  root.innerHTML = "<div class='mc-err'>جاري تحميل تفاصيل المباراة...</div>";
  var J = function (u) { return fetch(u).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; }); };
  Promise.all([J(NAMES_URL), J("https://nawaf737991-coder.github.io/fottballcia/names_ar.json"), J(TW_URL + "?t=" + Math.floor(Date.now() / 60000)), J(VID_URL + "?t=" + Math.floor(Date.now() / 60000))]).then(function (a) {
    var vd = ((a[3] || {}).matches || {})[id] || []; videos = vd.filter(function (v) { return /^[\w-]{11}$/.test(v.v || ""); }).slice(0, 2);
    var tw = a[2] || {}; tw = tw.matches || tw;
    tweets = ((tw[id] || []).map(function (x) { return typeof x === "string" ? {u: x} : x; })).filter(function (t) { return t && TW_RE.test(t.u || ""); }).slice(0, 12);
    var st2 = (a[1] && a[1].teams) || {}, ct = (a[1] && a[1].countries) || {};
    names = Object.assign({}, ct, st2, a[0] || {}); return load(); })
    .catch(function (e) { root.innerHTML = "<div class='mc-err'>" + (e.message === "nf" ? "هذه المباراة غير متاحة." : "تعذر تحميل المباراة الآن، حاول بعد قليل.") + "<br><a href='" + SITE + "/p/matches-today.html'>العودة لمباريات اليوم</a></div>"; });
})();
