async function postAction(url) {
  const resp = await fetch(url, { method: "POST" });
  if (!resp.ok) throw new Error("Request failed");
}

async function fetchFeed() {
  const feed = document.getElementById("feed");
  try {
    const res = await fetch(`/api/comments/${courseId}`);
    const data = await res.json();

    if (!data.comments || data.comments.length === 0) {
      feed.innerHTML = `<div class="muted">No comments yet. Be the first to ask!</div>`;
      return;
    }

    feed.innerHTML = data.comments.map(c => {
      const statusBadge = c.status === "resolved"
        ? `<span class="badge badge-resolved">resolved</span>`
        : c.status === "deleted"
          ? `<span class="badge badge-deleted">deleted</span>`
          : `<span class="badge badge-open">open</span>`;

      const praise = c.praised ? `<div class="praise-badge">Praised by the lecturer</div>` : "";

      const note = c.lecturer_note
        ? `<div class="lecturer-note-large">Lecturer note: ${escapeHtml(c.lecturer_note)}</div>`
        : "";

      const buttons = c.can_delete
        ? c.status === "deleted"
          ? `<button class="btn tiny secondary" data-undo="${c.id}">Undo</button>`
          : `<button class="btn tiny danger" data-delete="${c.id}">Delete</button>`
        : "";

      return `
        <div class="item ${c.status === 'deleted' ? 'item-deleted' : ''}">
          <div class="meta">
            <div>
              <strong>${escapeHtml(c.name)}</strong>
              <span class="muted small"> · ${escapeHtml(c.created_at)}</span>
            </div>
            <div>${statusBadge}</div>
          </div>
          <div class="content">${escapeHtml(c.content)}</div>
          ${praise}
          ${note}
          ${buttons ? `<div class="feed-actions">${buttons}</div>` : ''}
        </div>
      `;
    }).join("");

    feed.querySelectorAll("button[data-delete]").forEach(btn => {
      btn.addEventListener("click", async () => {
        try {
          await postAction(`/comment/${btn.dataset.delete}/delete`);
          fetchFeed();
        } catch (e) {
          alert("Failed to delete the comment.");
        }
      });
    });

    feed.querySelectorAll("button[data-undo]").forEach(btn => {
      btn.addEventListener("click", async () => {
        try {
          await postAction(`/comment/${btn.dataset.undo}/undo`);
          fetchFeed();
        } catch (e) {
          alert("Failed to undo the delete action.");
        }
      });
    });
  } catch (e) {
    feed.innerHTML = `<div class="muted">Failed to load feed. Refresh the page.</div>`;
  }
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

fetchFeed();
setInterval(fetchFeed, 3000);
if (typeof courseId !== "undefined") {
  fetchHonors(courseId);
  setInterval(() => fetchHonors(courseId), 4000);
}


async function fetchHonors(courseId) {
  const box = document.getElementById("honors-board");
  if (!box) return;
  try {
    const res = await fetch(`/api/honors/${courseId}`);
    const data = await res.json();
    const honors = data.honors || [];
    if (honors.length === 0) {
      box.innerHTML = `<div class="muted">No praised students yet.</div>`;
      return;
    }
    box.innerHTML = honors.map((h, idx) => `
      <div class="wall-item honor-item honor-rank-${idx+1}">
        <div class="wall-top">
          <strong>#${idx + 1} ${escapeHtml(h.name)}</strong>
          <span class="badge badge-resolved">${h.praise_count} praise${h.praise_count > 1 ? 's' : ''}</span>
        </div>
      </div>
    `).join("");
  } catch (e) {
    box.innerHTML = `<div class="muted">Failed to load the praised students board.</div>`;
  }
}

window.fetchHonors = fetchHonors;
