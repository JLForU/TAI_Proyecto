/* Polling de discovery con backoff (P1 / NFR-U3-AVAIL-01):
 * - 2 s fijo mientras el run está running;
 * - ante error de red/5xx: backoff exponencial 2→4→8→16 s (tope 30 s);
 * - 5 fallos consecutivos ⇒ se detiene y ofrece reintento manual.
 */
(function () {
  "use strict";

  var MAX_FAILURES = 5;
  var BACKOFF_MS = [2000, 4000, 8000, 16000, 30000];
  var RUNNING_DELAY_MS = 2000;

  function init() {
    var el = document.getElementById("discovery-status");
    if (!el) return;
    if (el.getAttribute("data-status") !== "running") return;
    var runId = el.getAttribute("data-run-id");
    if (!runId) return;

    var failures = 0;
    var timer = null;

    function schedule(ms) {
      timer = setTimeout(poll, ms);
    }

    function render(data) {
      el.setAttribute("data-status", data.status);
      var badge = el.querySelector("[data-role=badge]");
      if (badge) {
        badge.textContent = data.status;
        badge.className = "badge " + (data.status === "completed" ? "badge-success" : data.status === "running" ? "badge-info" : "badge-error");
      }
      var seen = el.querySelector("[data-role=hosts_seen]");
      if (seen && data.hosts_seen !== null && data.hosts_seen !== undefined) {
        seen.textContent = String(data.hosts_seen);
      }
      var err = el.querySelector("[data-role=error]");
      if (err) err.textContent = data.error || "";
      var finished = el.querySelector("[data-role=finished_at]");
      if (finished) finished.textContent = data.finished_at || "";
    }

    function stop() {
      if (timer) clearTimeout(timer);
      el.setAttribute("data-status", "stopped");
      var msg = el.querySelector("[data-role=poll-message]");
      if (msg) {
        msg.textContent = "estado no disponible";
        msg.classList.remove("hidden");
      }
      var retry = el.querySelector("[data-role=retry]");
      if (retry) retry.classList.remove("hidden");
    }

    function onError() {
      failures += 1;
      if (failures >= MAX_FAILURES) {
        stop();
        return;
      }
      schedule(BACKOFF_MS[Math.min(failures - 1, BACKOFF_MS.length - 1)]);
    }

    function poll() {
      fetch("/api/v1/discovery/" + encodeURIComponent(runId), {
        headers: { accept: "application/json" },
      })
        .then(function (resp) {
          if (!resp.ok) throw new Error("http " + resp.status);
          return resp.json();
        })
        .then(function (data) {
          failures = 0;
          render(data);
          if (data.status === "running") {
            schedule(RUNNING_DELAY_MS);
          }
        })
        .catch(onError);
    }

    schedule(RUNNING_DELAY_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
