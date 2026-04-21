/*
  Danmaku (bullet screen) overlay.
  - Shows "open" questions as floating messages on screen.
  - Students can click a danmaku to like it.
  - Colors change with like count.
*/

function likeClass(likes) {
  if (likes >= 8) return "hot-4";
  if (likes >= 5) return "hot-3";
  if (likes >= 3) return "hot-2";
  if (likes >= 1) return "hot-1";
  return "hot-0";
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function startDanmaku({ courseId, canLike }) {
  const layer = document.getElementById("danmaku-layer");
  if (!layer) return;

  let openComments = [];
  let idx = 0;
  let running = true;

  async function refresh() {
    try {
      const res = await fetch(`/api/comments/${courseId}`);
      const data = await res.json();
      const list = (data.comments || []).filter(c => c.status === "open");
      openComments = list;
    } catch (e) {
      // ignore
    }
  }

  function spawnOne() {
    if (!running) return;
    if (!openComments || openComments.length === 0) return;

    const c = openComments[idx % openComments.length];
    idx += 1;

    const item = document.createElement("div");
    item.className = `danmaku-item ${likeClass(c.likes)}`;
    item.dataset.commentId = c.id;
    item.dataset.likes = c.likes;

    const h = window.innerHeight || 800;
    const top = Math.floor(Math.random() * Math.max(120, h - 180)) + 80;
    item.style.top = `${top}px`;
    item.style.left = `${(window.innerWidth || 1200) + 20}px`;

    const label = `<span class="danmaku-name">${escapeHtml(c.name)}</span>`;
    const text = `<span class="danmaku-text">${escapeHtml(c.content)}</span>`;
    const like = `<span class="danmaku-like">❤ <b>${c.likes}</b></span>`;
    item.innerHTML = `${label}: ${text} ${like}`;

    if (canLike) {
      item.classList.add("clickable");
      item.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const commentId = item.dataset.commentId;
        try {
          const resp = await fetch(`/api/like/${commentId}`, { method: "POST" });
          const out = await resp.json();
          if (out && (out.ok || out.reason === "already_liked")) {
            const newLikes = out.likes ?? Number(item.dataset.likes || 0);
            item.dataset.likes = newLikes;
            const b = item.querySelector(".danmaku-like b");
            if (b) b.textContent = String(newLikes);
            item.className = `danmaku-item ${likeClass(newLikes)} clickable`;
            item.classList.add("pulsed");
            setTimeout(() => item.classList.remove("pulsed"), 250);
          }
        } catch (e) { /* ignore */ }
      });
    }

    layer.appendChild(item);

    const distance = (window.innerWidth || 1200) + (item.offsetWidth || 400) + 80;
    const seconds = Math.max(10, Math.min(18, 10 + Math.random() * 8)); // 10–18s
    item.style.transition = `transform ${seconds}s linear`;
    item.getBoundingClientRect(); // force layout
    item.style.transform = `translateX(-${distance}px)`;

    setTimeout(() => item.remove(), (seconds + 0.2) * 1000);
  }

  refresh();
  const refreshTimer = setInterval(refresh, 2500);
  const spawnTimer = setInterval(spawnOne, 900);

  window.addEventListener("visibilitychange", () => {
    running = !document.hidden;
  });

  return () => {
    clearInterval(refreshTimer);
    clearInterval(spawnTimer);
    running = false;
  };
}
