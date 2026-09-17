/* train dashboard: Korail-app-like flow. Vanilla JS, no build step. */
(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const state = { csrf: null, me: null, tab: "book", jobsTimer: null, pick: null, lastSearch: null };

  // ---------- helpers ----------
  async function api(method, path, body) {
    const headers = { "Accept": "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (state.csrf && method !== "GET") headers["X-CSRF-Token"] = state.csrf;
    const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: "same-origin" });
    let data = null;
    try { data = await res.json(); } catch (_) { /* no body */ }
    if (res.status === 401 && path !== "/web/login") { showLogin(); }
    if (!res.ok) {
      const d = data && data.detail;
      const msg = typeof d === "string" ? d : (d && d.message) || res.statusText;
      const err = new Error(msg); err.status = res.status; throw err;
    }
    return data;
  }
  const hhmm = (t) => (t ? `${t.slice(0, 2)}:${t.slice(2, 4)}` : "");
  const ymd = (d) => d.replace(/-/g, "");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 3500); }
  function setError(el, msg) { el.textContent = msg || ""; el.hidden = !msg; }

  // ---------- screens ----------
  function showLogin() {
    stopJobsPolling();
    state.csrf = null; state.me = null;
    $("#screen-home").hidden = true; $("#screen-login").hidden = false; $("#who").hidden = true;
  }
  function showHome() {
    $("#screen-login").hidden = true; $("#screen-home").hidden = false;
    $("#who").hidden = false; $("#who-name").textContent = `${state.me.name || ""} (${state.me.korail_id})`;
    selectTab(state.tab);
  }
  function selectTab(tab) {
    state.tab = tab;
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    document.querySelectorAll(".tab").forEach((t) => (t.hidden = t.id !== `tab-${tab}`));
    if (tab === "jobs") { loadJobs(); startJobsPolling(); } else { stopJobsPolling(); }
    if (tab === "holds") loadHolds();
  }

  // ---------- login ----------
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, btn = f.querySelector("button"), err = $("#login-error");
    setError(err); btn.disabled = true; btn.textContent = "로그인 중…";
    try {
      const me = await api("POST", "/web/login", { korail_id: f.korail_id.value.trim(), korail_pw: f.korail_pw.value });
      f.korail_pw.value = "";
      state.csrf = me.csrf; state.me = me; showHome();
    } catch (ex) { setError(err, ex.message); }
    finally { btn.disabled = false; btn.textContent = "로그인"; }
  });
  $("#logout").addEventListener("click", async () => { try { await api("POST", "/web/logout"); } catch (_) {} showLogin(); toast("로그아웃했습니다"); });

  // ---------- search ----------
  const hours = $("select[name=hour]"), endHours = $("select[name=end_hour]");
  for (let h = 0; h < 24; h++) {
    const v = String(h).padStart(2, "0");
    hours.add(new Option(`${v}:00`, `${v}0000`)); endHours.add(new Option(`${v}:59`, `${v}5959`));
  }
  const today = new Date(); hours.value = `${String(Math.min(23, today.getHours() + 1)).padStart(2, "0")}0000`;
  $("input[name=date]").value = today.toISOString().slice(0, 10);
  $("input[name=date]").min = today.toISOString().slice(0, 10);
  $("#swap").addEventListener("click", () => { const f = $("#search-form"); [f.dep.value, f.arr.value] = [f.arr.value, f.dep.value]; });

  $("#search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, btn = f.querySelector("button.primary"), err = $("#search-error");
    const body = { dep: f.dep.value.trim(), arr: f.arr.value.trim(), date: ymd(f.date.value), time: f.hour.value };
    if (f.end_hour.value) body.end_time = f.end_hour.value;
    if (f.trains.value.trim()) body.trains = f.trains.value.trim();
    setError(err); btn.disabled = true; btn.textContent = "조회 중…";
    try {
      const data = await api("POST", "/web/search", body);
      state.lastSearch = body; renderTrains(data.trains);
    } catch (ex) { setError(err, ex.message); }
    finally { btn.disabled = false; btn.textContent = "조회하기"; }
  });

  function renderTrains(trains) {
    const box = $("#results");
    if (!trains.length) { box.innerHTML = `<p class="empty">조건에 맞는 열차가 없습니다.</p>`; return; }
    box.innerHTML = trains.map((t) => `
      <div class="train">
        <div>
          <div class="type">${esc(t.train_type)} <span class="no">${esc(t.train_no)}</span></div>
          <div class="time">${hhmm(t.dep_time)}<small>${esc(t.dep)} →</small>${hhmm(t.arr_time)}<small>${esc(t.arr)}</small></div>
          <div class="seats">
            <span class="seat ${t.special ? "ok" : "no"}">특실 ${t.special ? "예약가능" : "매진"}</span>
            <span class="seat ${t.general ? "ok" : "no"}">일반실 ${t.general ? "예약가능" : "매진"}</span>
          </div>
        </div>
        <button class="secondary small" data-train="${esc(t.train_no)}">${t.special || t.general ? "예약 시도" : "빈자리 시도"}</button>
      </div>`).join("");
    box.querySelectorAll("button[data-train]").forEach((b) => b.addEventListener("click", () => openSheet(trains.find((t) => t.train_no === b.dataset.train))));
  }

  // ---------- reserve sheet (creates a per-job sandbox) ----------
  function openSheet(train) {
    state.pick = train;
    $("#sheet-title").textContent = `${train.train_type} ${train.train_no} 예약 시도`;
    $("#sheet-sub").textContent = `${train.dep} ${hhmm(train.dep_time)} → ${train.arr} ${hhmm(train.arr_time)} · ${train.date.slice(4, 6)}/${train.date.slice(6)}`;
    const f = $("#reserve-form");
    f.monitor_only.checked = false; setError($("#sheet-error"));
    if (train.special && !train.general) f.seat_class.value = "special";
    else if (train.general && !train.special) f.seat_class.value = "general";
    else f.seat_class.value = "any";
    $("#sheet").hidden = false;
  }
  $("#sheet-cancel").addEventListener("click", () => ($("#sheet").hidden = true));
  $("#sheet").addEventListener("click", (e) => { if (e.target.id === "sheet") $("#sheet").hidden = true; });
  $("#reserve-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, t = state.pick, s = state.lastSearch, btn = f.querySelector("button.primary");
    const body = {
      dep: s.dep, arr: s.arr, date: t.date, time: t.dep_time, end_time: t.dep_time, trains: [t.train_no],
      seat_class: f.seat_class.value, interval_sec: Number(f.interval_sec.value) || 3,
      monitor_only: f.monitor_only.checked, max_minutes: Number(f.max_minutes.value) || 60,
    };
    if (f.seat_letter.value) body.seat_letter = f.seat_letter.value;
    btn.disabled = true; setError($("#sheet-error"));
    try {
      const job = await api("POST", "/web/jobs", body);
      $("#sheet").hidden = true; toast(`예약 시도 시작 (${job.id}) — 새 샌드박스 준비 중`); selectTab("jobs");
    } catch (ex) { setError($("#sheet-error"), ex.message); }
    finally { btn.disabled = false; }
  });

  // ---------- jobs ----------
  const STATUS_KO = { provisioning: "샌드박스 준비 중", running: "시도 중", reserved: "예약 완료", idle_timeout: "시간 종료", cancelled: "취소됨", failed: "실패" };
  async function loadJobs() {
    let jobs; try { jobs = await api("GET", "/web/jobs"); } catch (_) { return; }
    const active = jobs.filter((j) => j.status === "running" || j.status === "provisioning").length;
    const badge = $("#jobs-badge"); badge.hidden = !active; badge.textContent = active;
    const box = $("#jobs");
    if (!jobs.length) { box.innerHTML = `<p class="empty">진행 중인 예약 시도가 없습니다.</p>`; return; }
    box.innerHTML = jobs.map((j) => {
      const s = j.spec, live = j.status === "running" || j.status === "provisioning";
      return `<div class="job">
        <div class="head">
          <div><b>${esc(s.dep)} → ${esc(s.arr)}</b> <span class="meta">${s.date.slice(4, 6)}/${s.date.slice(6)} ${hhmm(s.time)} 열차 ${esc((s.trains || []).join(",") || "전체")}</span></div>
          <span class="status ${esc(j.status)}">${STATUS_KO[j.status] || esc(j.status)}</span>
        </div>
        <div class="meta">${s.seat_class === "special" ? "특실" : s.seat_class === "general" ? "일반실" : "등급 무관"}${s.seat_letter ? ` · ${esc(s.seat_letter)}석` : ""}${s.monitor_only ? " · 알림만" : ""} · 샌드박스 ${esc((j.worker_id || "-").slice(0, 8))} · IP ${esc(j.egress_ip || "…")}${j.error ? ` · <span style="color:var(--no)">${esc(j.error)}</span>` : ""}</div>
        ${j.log_tail ? `<pre class="log">${esc(j.log_tail.split("\n").slice(-6).join("\n"))}</pre>` : ""}
        ${live ? `<button class="secondary small danger" data-cancel="${esc(j.id)}">시도 취소</button>` : ""}
      </div>`;
    }).join("");
    box.querySelectorAll("button[data-cancel]").forEach((b) => b.addEventListener("click", async () => {
      b.disabled = true;
      try { await api("DELETE", `/web/jobs/${b.dataset.cancel}`); toast("취소했습니다"); loadJobs(); } catch (ex) { toast(ex.message); b.disabled = false; }
    }));
  }
  function startJobsPolling() { stopJobsPolling(); state.jobsTimer = setInterval(loadJobs, 5000); }
  function stopJobsPolling() { if (state.jobsTimer) clearInterval(state.jobsTimer); state.jobsTimer = null; }

  // ---------- holds ----------
  async function loadHolds() {
    const box = $("#holds"); box.innerHTML = `<p class="empty">불러오는 중…</p>`;
    let data; try { data = await api("GET", "/web/holds"); } catch (ex) { box.innerHTML = `<p class="error">${esc(ex.message)}</p>`; return; }
    if (!data.holds.length) { box.innerHTML = `<p class="empty">미결제 예약이 없습니다.</p>`; return; }
    box.innerHTML = data.holds.map((h) => `<div class="hold">
      <div class="head"><div><b>${esc(h.train_type)} ${esc(h.train_no)}</b> <span class="meta">${h.date.slice(4, 6)}/${h.date.slice(6)}</span></div><span class="status running">미결제</span></div>
      <div class="time" style="font-size:18px;font-weight:800">${hhmm(h.dep_time)} ${esc(h.dep)} → ${hhmm(h.arr_time)} ${esc(h.arr)}</div>
      <div class="meta">${h.car ? `${esc(h.car)}호차 ${esc(h.seat || "")}` : `${h.seats}석`} · ${Number(h.price).toLocaleString("ko-KR")}원 · 결제기한 ${esc(h.pay_by.slice(4, 6))}/${esc(h.pay_by.slice(6, 8))} ${hhmm(h.pay_by.slice(9))}</div>
      <button class="secondary small danger" data-hold="${esc(h.rsv_id)}">예약 취소</button>
    </div>`).join("");
    box.querySelectorAll("button[data-hold]").forEach((b) => b.addEventListener("click", async () => {
      if (!confirm("이 예약을 취소할까요?")) return;
      b.disabled = true;
      try { await api("DELETE", `/web/holds/${b.dataset.hold}`); toast("예약을 취소했습니다"); loadHolds(); } catch (ex) { toast(ex.message); b.disabled = false; }
    }));
  }
  $("#holds-refresh").addEventListener("click", loadHolds);
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => selectTab(b.dataset.tab)));

  // ---------- boot: restore session if the cookie is still valid ----------
  (async () => {
    try { const me = await api("GET", "/web/me"); state.csrf = me.csrf; state.me = me; showHome(); }
    catch (_) { showLogin(); }
  })();
})();
