const API_BASE = "";

function getConnection() {
  const authMethod = document.querySelector('input[name=auth]:checked').value;
  const conn = {
    host: document.getElementById("c-host").value.trim(),
    port: parseInt(document.getElementById("c-port").value, 10) || 22,
    ssh_username: document.getElementById("c-username").value.trim(),
    operator: document.getElementById("c-operator").value.trim() || null,
    auth_method: authMethod,
  };
  if (authMethod === "password") {
    conn.password = document.getElementById("c-password").value;
  } else {
    conn.private_key = document.getElementById("c-privkey").value;
    conn.private_key_passphrase = document.getElementById("c-passphrase").value || null;
  }
  return conn;
}

function splitList(value) {
  return value.split(",").map((s) => s.trim()).filter((s) => s.length > 0);
}

async function postJSON(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `요청 실패 (HTTP ${res.status})`);
  }
  return data;
}

// --- auth method toggle -----------------------------------------------
document.querySelectorAll('input[name=auth]').forEach((el) => {
  el.addEventListener("change", () => {
    const isPw = document.querySelector('input[name=auth]:checked').value === "password";
    document.getElementById("auth-password").classList.toggle("hidden", !isPw);
    document.getElementById("auth-key").classList.toggle("hidden", isPw);
  });
});

// --- tabs ----------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("form-" + btn.dataset.tab).classList.add("active");
  });
});

// --- connection test -------------------------------------------------
document.getElementById("btn-test-conn").addEventListener("click", async () => {
  const statusEl = document.getElementById("conn-status");
  statusEl.textContent = "연결 확인 중...";
  statusEl.className = "status";
  try {
    const data = await postJSON("/api/connection/test", { connection: getConnection() });
    statusEl.textContent = data.success ? "연결 성공" : "연결됨 (명령 실행 실패)";
    statusEl.className = "status " + (data.success ? "ok" : "fail");
    renderResult(data);
    loadLogs();
  } catch (e) {
    statusEl.textContent = "실패: " + e.message;
    statusEl.className = "status fail";
  }
});

// --- result rendering --------------------------------------------------
function renderResult(entry) {
  document.getElementById("result-empty").classList.add("hidden");
  const box = document.getElementById("result-box");
  box.classList.remove("hidden");

  const summary = document.getElementById("result-summary");
  summary.textContent = (entry.success ? "[성공] " : "[실패] ") + entry.message;
  summary.className = entry.success ? "ok" : "fail";

  const tbody = document.getElementById("result-steps");
  tbody.innerHTML = "";
  (entry.steps || []).forEach((s, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${escapeHtml(s.name)}</td>
      <td><pre>${escapeHtml(s.command)}</pre></td>
      <td><pre>${escapeHtml(s.stdout)}</pre></td>
      <td><pre>${escapeHtml(s.stderr)}</pre></td>
      <td>${s.exit_code}</td>
      <td class="${s.success ? "ok-cell" : "fail-cell"}">${s.success ? "성공" : "실패"}</td>
    `;
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// --- forms ---------------------------------------------------------------
function formData(form) {
  const fd = new FormData(form);
  const out = {};
  for (const [k, v] of fd.entries()) out[k] = v;
  return out;
}

async function submitAction(path, body, submitBtn) {
  submitBtn.disabled = true;
  const original = submitBtn.textContent;
  submitBtn.textContent = "실행 중...";
  try {
    const data = await postJSON(path, body);
    renderResult(data);
    loadLogs();
  } catch (e) {
    renderResult({ success: false, message: e.message, steps: [] });
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = original;
  }
}

document.getElementById("form-create").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = formData(ev.target);
  const body = {
    connection: getConnection(),
    username: f.username,
    primary_group: f.primary_group,
    secondary_groups: splitList(f.secondary_groups || ""),
    home_dir: f.home_dir || null,
    shell: f.shell || "/bin/bash",
    password: f.password || null,
    comment: f.comment || null,
    create_missing_groups: !!f.create_missing_groups,
  };
  submitAction("/api/account/create", body, ev.submitter);
});

document.getElementById("form-delete").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = formData(ev.target);
  if (!confirm(`정말로 계정 '${f.username}' 을(를) 삭제하시겠습니까? 홈 디렉토리와 메일함이 함께 삭제되며 되돌릴 수 없습니다.`)) return;
  const body = { connection: getConnection(), username: f.username };
  submitAction("/api/account/delete", body, ev.submitter);
});

document.getElementById("form-pgroup").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = formData(ev.target);
  const body = {
    connection: getConnection(),
    username: f.username,
    new_group: f.new_group,
    create_missing_group: !!f.create_missing_group,
  };
  submitAction("/api/group/primary", body, ev.submitter);
});

document.getElementById("form-sgroup").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = formData(ev.target);
  const body = {
    connection: getConnection(),
    username: f.username,
    groups: splitList(f.groups || ""),
    mode: f.mode || "replace",
    create_missing_groups: !!f.create_missing_groups,
  };
  submitAction("/api/group/secondary", body, ev.submitter);
});

// --- logs ------------------------------------------------------------
async function loadLogs() {
  const listEl = document.getElementById("log-list");
  try {
    const res = await fetch(API_BASE + "/api/logs?limit=100");
    const data = await res.json();
    listEl.innerHTML = "";
    if (!data.entries || data.entries.length === 0) {
      listEl.innerHTML = '<div class="hint">로그가 없습니다.</div>';
      return;
    }
    data.entries.forEach((entry) => {
      const div = document.createElement("div");
      div.className = "log-entry";
      const badge = entry.success
        ? '<span class="badge ok">성공</span>'
        : '<span class="badge fail">실패</span>';
      div.innerHTML = `
        <div class="log-head">
          <div><strong>${escapeHtml(entry.action)}</strong> ${badge}</div>
          <div class="meta">${escapeHtml(entry.timestamp)} · ${escapeHtml(entry.ssh_host)} · ${escapeHtml(entry.ssh_username)} · ${escapeHtml(entry.operator || "-")}</div>
        </div>
        <div class="meta">${escapeHtml(entry.message)}</div>
        <div class="log-detail"></div>
      `;
      div.addEventListener("click", () => {
        div.classList.toggle("expanded");
        const detail = div.querySelector(".log-detail");
        if (div.classList.contains("expanded") && !detail.dataset.rendered) {
          const rows = (entry.steps || [])
            .map(
              (s, i) => `<tr>
                <td>${i + 1}</td><td>${escapeHtml(s.name)}</td>
                <td><pre>${escapeHtml(s.command)}</pre></td>
                <td><pre>${escapeHtml(s.stdout)}</pre></td>
                <td><pre>${escapeHtml(s.stderr)}</pre></td>
                <td>${s.exit_code}</td>
                <td class="${s.success ? "ok-cell" : "fail-cell"}">${s.success ? "성공" : "실패"}</td>
              </tr>`
            )
            .join("");
          detail.innerHTML = `<table class="steps-table"><thead><tr><th>#</th><th>단계</th><th>명령어</th><th>stdout</th><th>stderr</th><th>exit</th><th>결과</th></tr></thead><tbody>${rows}</tbody></table>`;
          detail.dataset.rendered = "1";
        }
      });
      listEl.appendChild(div);
    });
  } catch (e) {
    listEl.innerHTML = '<div class="hint">로그를 불러오지 못했습니다: ' + escapeHtml(e.message) + "</div>";
  }
}

document.getElementById("btn-refresh-logs").addEventListener("click", loadLogs);

loadLogs();
