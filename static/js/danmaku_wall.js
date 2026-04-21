/*
  Danmaku Wall (list view)
  - Shows open questions sorted by likes (desc), newest first as tie-break.
  - Students can like from the wall and delete/undo their own comments.
  - Lecturers can delete/undo any comment from the wall.
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

export function startDanmakuWall({ courseId, canLike, isLecturer = false }) {
  const box = document.getElementById("danmaku-wall");
  if (!box) return;

  async function postAction(url) {
    const resp = await fetch(url, { method: "POST" });
    if (!resp.ok) throw new Error("Request failed");
  }

  async function render() {
    try {
      const res = await fetch(`/api/comments/${courseId}`);
      const data = await res.json();
      const allComments = data.comments || [];
      const list = allComments.filter(c => c.status === "open");

      list.sort((a, b) => {
        if (b.likes !== a.likes) return b.likes - a.likes;
        return String(b.created_at).localeCompare(String(a.created_at));
      });

      if (list.length === 0) {
        box.innerHTML = `<div class="muted">No danmaku yet. Student questions will appear here and scroll across the screen once submitted.</div>`;
        return;
      }

      box.innerHTML = list.slice(0, 30).map(c => {
        const badge = `<span class="badge ${c.likes>=3 ? "badge-resolved" : "badge-open"}">❤ ${c.likes}</span>`;
        const likeBtn = canLike
          ? `<button class="btn tiny" data-like="${c.id}">Like</button>`
          : ``;
        const manageBtn = c.can_delete
          ? `<button class="btn tiny danger" data-delete="${c.id}">${isLecturer ? 'Delete' : 'Delete Mine'}</button>`
          : ``;

        return `
          <div class="wall-item ${likeClass(c.likes)}">
            <div class="wall-top">
              <div class="wall-title">
                <strong>${escapeHtml(c.name)}</strong>
                <span class="muted small"> · ${escapeHtml(c.created_at)}</span>
              </div>
              <div class="wall-actions">
                ${badge}
                ${likeBtn}
                ${manageBtn}
              </div>
            </div>
            <div class="wall-text">${escapeHtml(c.content)}</div>
          </div>
        `;
      }).join("");

      if (canLike) {
        box.querySelectorAll("button[data-like]").forEach(btn => {
          btn.addEventListener("click", async (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const id = btn.getAttribute("data-like");
            try {
              const resp = await fetch(`/api/like/${id}`, { method: "POST" });
              const out = await resp.json();
              if (out && (out.ok || out.reason === "already_liked")) {
                render();
              }
            } catch (e) { }
          });
        });
      }

      box.querySelectorAll("button[data-delete]").forEach(btn => {
        btn.addEventListener("click", async (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          try {
            await postAction(`/comment/${btn.dataset.delete}/delete`);
            render();
          } catch (e) {
            alert("Failed to delete the comment.");
          }
        });
      });
    } catch (e) {
      box.innerHTML = `<div class="muted">Failed to load the danmaku wall. Please refresh the page.</div>`;
    }
  }

  render();
  return setInterval(render, 2000);
}
