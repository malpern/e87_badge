// e87_badge site — nav, reveal-on-scroll, copy buttons, live badge eye.

(function () {
  // ── Sticky nav background on scroll ──────────────────────────────────
  var nav = document.querySelector(".nav");
  if (nav) {
    var onScroll = function () { nav.classList.toggle("scrolled", window.scrollY > 12); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // ── Reveal on scroll ─────────────────────────────────────────────────
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.14, rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll(".reveal").forEach(function (el) { el.classList.add("in"); });
  }

  // ── Copy buttons on code windows ─────────────────────────────────────
  document.querySelectorAll(".code-win").forEach(function (win) {
    var bar = win.querySelector(".code-bar");
    var pre = win.querySelector("pre");
    if (!bar || !pre) return;
    var btn = document.createElement("button");
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy code");
    btn.style.cssText =
      "margin-left:auto;font:500 12px var(--mono);color:var(--text-mute);" +
      "background:transparent;border:1px solid var(--hairline);border-radius:7px;" +
      "padding:3px 10px;cursor:pointer;transition:.2s;";
    btn.addEventListener("mouseenter", function () { btn.style.color = "var(--text)"; btn.style.borderColor = "var(--hairline-2)"; });
    btn.addEventListener("mouseleave", function () { btn.style.color = "var(--text-mute)"; btn.style.borderColor = "var(--hairline)"; });
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(pre.innerText).then(function () {
        btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy"; }, 1400);
      });
    });
    bar.appendChild(btn);
  });

  // ── Live badge eye (the thing we actually display on the device) ─────
  var canvas = document.getElementById("badge-eye");
  if (canvas && canvas.getContext) {
    var ctx = canvas.getContext("2d");
    var DPR = Math.min(window.devicePixelRatio || 1, 2);
    function size() {
      var r = canvas.getBoundingClientRect();
      canvas.width = r.width * DPR; canvas.height = r.height * DPR;
    }
    size(); window.addEventListener("resize", size);

    var start = performance.now();
    // Blink schedule: open for ~3.2s, quick blink ~0.22s.
    function openAmount(t) {
      var period = 3.4, blink = 0.22;
      var p = t % period;
      if (p > period - blink) {
        var x = (p - (period - blink)) / blink; // 0..1 over the blink
        return Math.abs(Math.cos(Math.PI * x)); // 1 -> 0 -> 1
      }
      return 1;
    }
    // Gentle gaze drift.
    function gaze(t) {
      return { x: Math.sin(t * 0.6) * 0.06 + Math.sin(t * 0.21) * 0.04,
               y: Math.cos(t * 0.5) * 0.04 };
    }

    function frame(now) {
      var t = (now - start) / 1000;
      var w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
      var R = Math.min(w, h) * 0.42;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#000"; ctx.fillRect(0, 0, w, h);

      var open = reduce ? 1 : openAmount(t);
      var g = reduce ? { x: 0, y: 0 } : gaze(t);
      var ox = g.x * R, oy = g.y * R;

      // soft glow
      var glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 1.5);
      glow.addColorStop(0, "rgba(41,151,255,0.30)");
      glow.addColorStop(0.5, "rgba(48,214,198,0.10)");
      glow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = glow; ctx.fillRect(0, 0, w, h);

      ctx.save();
      // blink = vertical squish around the eye centre
      ctx.translate(cx, cy);
      ctx.scale(1, Math.max(0.04, open));
      ctx.translate(-cx, -cy);

      // iris
      var ir = ctx.createRadialGradient(cx + ox, cy + oy, R * 0.1, cx + ox, cy + oy, R);
      ir.addColorStop(0, "#7fe9ff");
      ir.addColorStop(0.45, "#2997ff");
      ir.addColorStop(1, "#0a3a86");
      ctx.beginPath(); ctx.arc(cx + ox, cy + oy, R, 0, Math.PI * 2);
      ctx.fillStyle = ir; ctx.fill();

      // faint concentric rings (echo of the bullseye we first sent)
      ctx.lineWidth = Math.max(1, R * 0.018);
      ["rgba(255,255,255,0.10)", "rgba(255,255,255,0.07)"].forEach(function (c, i) {
        ctx.beginPath(); ctx.arc(cx + ox, cy + oy, R * (0.72 - i * 0.22), 0, Math.PI * 2);
        ctx.strokeStyle = c; ctx.stroke();
      });

      // pupil
      ctx.beginPath(); ctx.arc(cx + ox * 1.3, cy + oy * 1.3, R * 0.34, 0, Math.PI * 2);
      ctx.fillStyle = "#03060f"; ctx.fill();

      // specular highlight
      ctx.beginPath(); ctx.arc(cx + ox - R * 0.28, cy + oy - R * 0.3, R * 0.12, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.9)"; ctx.fill();
      ctx.restore();

      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
})();
