document.getElementById("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const username = document.getElementById("l-username").value.trim();
  const password = document.getElementById("l-password").value;
  const errEl = document.getElementById("login-error");
  errEl.classList.add("hidden");

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `로그인 실패 (HTTP ${res.status})`);
    }
    window.location.href = "/";
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove("hidden");
  }
});
