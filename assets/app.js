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
    var clamp = function (v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; };

    // Gaze follows the cursor; falls back to a gentle drift when idle.
    var pointer = null;          // last cursor position, client coords
    var lastMoveT = -1e9;        // seconds since start of last pointer move
    var gx = 0, gy = 0;          // smoothed gaze, -1..1 in each axis

    window.addEventListener("pointermove", function (e) {
      pointer = { x: e.clientX, y: e.clientY };
      lastMoveT = (performance.now() - start) / 1000;
    }, { passive: true });

    // Blink on click of the eye (and anywhere on the badge).
    var manualBlinkT = -1e9;
    var blink = function () { manualBlinkT = (performance.now() - start) / 1000; };
    canvas.addEventListener("pointerdown", blink);
    var badgeEl = canvas.closest(".badge");
    if (badgeEl) badgeEl.addEventListener("pointerdown", blink);

    // Ambient blink so the eye feels alive even when untouched.
    function ambientOpen(t) {
      var period = 4.6, dur = 0.22, p = t % period;
      if (p > period - dur) return Math.abs(Math.cos(Math.PI * ((p - (period - dur)) / dur)));
      return 1;
    }
    // Click-triggered blink (a touch snappier than the ambient one).
    function manualOpen(t) {
      var d = t - manualBlinkT, dur = 0.20;
      if (d < 0 || d > dur) return 1;
      return Math.abs(Math.cos(Math.PI * (d / dur)));
    }

    function frame(now) {
      var t = (now - start) / 1000;
      var w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
      var eyeR = Math.min(w, h) * 0.46;     // socket / glow extent
      var irisR = eyeR * 0.80;              // iris sits inside the dark socket
      var travel = eyeR - irisR;            // how far the iris can move and stay in-socket
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#000"; ctx.fillRect(0, 0, w, h);

      // Target gaze: toward the cursor, or a calm idle drift if it's been still.
      var tx, ty;
      var idle = (t - lastMoveT) > 2.6;
      if (pointer && !idle) {
        var rect = canvas.getBoundingClientRect();
        var ecx = rect.left + rect.width / 2, ecy = rect.top + rect.height / 2;
        var span = Math.max(rect.width, 220) * 1.9;  // distance that maps to full deflection
        tx = clamp((pointer.x - ecx) / span, -1, 1);
        ty = clamp((pointer.y - ecy) / span, -1, 1);
        var mag = Math.hypot(tx, ty), max = 1.0;
        if (mag > max) { tx *= max / mag; ty *= max / mag; }
      } else {
        tx = Math.sin(t * 0.55) * 0.34 + Math.sin(t * 0.19) * 0.16;
        ty = Math.cos(t * 0.47) * 0.22;
      }
      if (reduce) { tx = 0; ty = 0; }
      // Smooth toward the target (eyes ease, they don't snap).
      gx += (tx - gx) * 0.14; gy += (ty - gy) * 0.14;
      var ox = gx * travel, oy = gy * travel;

      var open = reduce ? 1 : Math.min(ambientOpen(t), manualOpen(t));

      // soft glow (stays put — only the iris moves)
      var glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, eyeR * 1.4);
      glow.addColorStop(0, "rgba(41,151,255,0.30)");
      glow.addColorStop(0.5, "rgba(48,214,198,0.10)");
      glow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = glow; ctx.fillRect(0, 0, w, h);

      ctx.save();
      // blink = vertical squish around the socket centre
      ctx.translate(cx, cy);
      ctx.scale(1, Math.max(0.04, open));
      ctx.translate(-cx, -cy);

      var ix = cx + ox, iy = cy + oy;

      // iris
      var ir = ctx.createRadialGradient(ix, iy, irisR * 0.1, ix, iy, irisR);
      ir.addColorStop(0, "#7fe9ff");
      ir.addColorStop(0.45, "#2997ff");
      ir.addColorStop(1, "#0a3a86");
      ctx.beginPath(); ctx.arc(ix, iy, irisR, 0, Math.PI * 2);
      ctx.fillStyle = ir; ctx.fill();

      // faint concentric rings (echo of the bullseye we first sent)
      ctx.lineWidth = Math.max(1, irisR * 0.02);
      ["rgba(255,255,255,0.10)", "rgba(255,255,255,0.07)"].forEach(function (c, i) {
        ctx.beginPath(); ctx.arc(ix, iy, irisR * (0.72 - i * 0.22), 0, Math.PI * 2);
        ctx.strokeStyle = c; ctx.stroke();
      });

      // pupil (a hair more travel than the iris — parallax)
      var px = cx + ox * 1.18, py = cy + oy * 1.18;
      ctx.beginPath(); ctx.arc(px, py, irisR * 0.42, 0, Math.PI * 2);
      ctx.fillStyle = "#03060f"; ctx.fill();

      // specular highlight
      ctx.beginPath(); ctx.arc(px - irisR * 0.34, py - irisR * 0.36, irisR * 0.15, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.9)"; ctx.fill();
      ctx.restore();

      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
})();
