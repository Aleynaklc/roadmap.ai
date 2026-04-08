const completed = new Set(JSON.parse(localStorage.getItem('aie-completed') || '[]'));
const bookmarks = new Set(JSON.parse(localStorage.getItem('aie-bookmarks') || '[]'));
let stages = [];
let currentNode = null;
let currentStage = null;
let tutorOpen = false;

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function loadRoadmap() {
  const data = await fetchJson('/api/roadmap');
  stages = data.stages;
}

function getNodeContext(nodeId, stageId) {
  const stage = stages.find((item) => item.id === stageId);
  if (!stage) throw new Error(`Unknown stage: ${stageId}`);
  const node = stage.nodes.find((item) => item.id === nodeId);
  if (!node) throw new Error(`Unknown node: ${nodeId}`);
  return { stage, node };
}

function updateProgress() {
  const total = stages.reduce((sum, stage) => sum + stage.nodes.length, 0);
  const done = completed.size;
  const pct = total ? Math.round((done / total) * 100) : 0;
  document.getElementById('progress-text').textContent = `${done} / ${total} completed`;
  document.getElementById('prog-fill').style.width = `${pct}%`;
  document.getElementById('progress-pct').textContent = `${pct}%`;
}

function renderRoadmap() {
  const container = document.getElementById('roadmap-container');
  container.innerHTML = '';

  stages.forEach((stage) => {
    const el = document.createElement('div');
    el.className = 'stage';
    el.dataset.stage = stage.id;
    el.innerHTML = `
      <div class="stage-label">
        <span class="stage-pill" style="color:${stage.color};border-color:${stage.color}40;background:${stage.color}08">
          ${stage.label}
        </span>
      </div>
      <div class="stage-nodes">
        ${stage.nodes.map((node) => `
          <button class="node ${completed.has(node.id) ? 'completed' : ''}"
                  type="button"
                  data-id="${node.id}"
                  data-stage-id="${stage.id}"
                  style="--node-color:${stage.color}">
            <span class="node-icon">${node.icon}</span>
            <span class="node-title">${node.title}</span>
            <span class="node-tag">${node.tag}</span>
          </button>
        `).join('')}
      </div>
    `;
    container.appendChild(el);
  });

  updateProgress();
}

async function openLesson(nodeId, stageId) {
  const { stage, node } = getNodeContext(nodeId, stageId);
  currentNode = node;
  currentStage = stage;

  document.getElementById('lesson-stage-badge').textContent = stage.label;
  document.getElementById('lesson-title-h').textContent = node.title;
  document.getElementById('lesson-body').innerHTML = '<p>Loading lesson...</p>';
  document.getElementById('lesson-overlay').classList.add('open');
  document.getElementById('lesson-panel').classList.add('open');
  document.body.style.overflow = 'hidden';

  const completeButton = document.getElementById('complete-btn');
  completeButton.classList.toggle('done', completed.has(node.id));
  completeButton.textContent = completed.has(node.id) ? '✓ Completed!' : '✓ Mark as Complete';
  document.getElementById('bookmark-btn').classList.toggle('active', bookmarks.has(node.id));

  try {
    const lesson = await fetchJson(`/api/lesson/${node.id}`);
    const badge = document.getElementById('lesson-stage-badge');
    badge.textContent = lesson.stage;
    badge.style.color = lesson.stageColor;
    badge.style.borderColor = `${lesson.stageColor}40`;
    document.getElementById('lesson-body').innerHTML = lesson.content;
  } catch (error) {
    document.getElementById('lesson-body').innerHTML = '<div class="callout danger">Failed to load lesson content.</div>';
    console.error(error);
  }
}

function closeLesson() {
  document.getElementById('lesson-overlay').classList.remove('open');
  document.getElementById('lesson-panel').classList.remove('open');
  document.body.style.overflow = '';
  currentNode = null;
  currentStage = null;
}

function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

function markComplete() {
  if (!currentNode) return;
  const btn = document.getElementById('complete-btn');
  if (completed.has(currentNode.id)) {
    completed.delete(currentNode.id);
    btn.textContent = '✓ Mark as Complete';
    btn.classList.remove('done');
    showToast('Marked as incomplete');
  } else {
    completed.add(currentNode.id);
    btn.textContent = '✓ Completed!';
    btn.classList.add('done');
    showToast('Topic completed');
  }
  localStorage.setItem('aie-completed', JSON.stringify([...completed]));
  const nodeEl = document.querySelector(`.node[data-id="${currentNode.id}"]`);
  if (nodeEl) nodeEl.classList.toggle('completed', completed.has(currentNode.id));
  updateProgress();
}

function toggleBookmark() {
  if (!currentNode) return;
  const btn = document.getElementById('bookmark-btn');
  if (bookmarks.has(currentNode.id)) {
    bookmarks.delete(currentNode.id);
    btn.classList.remove('active');
    showToast('Bookmark removed');
  } else {
    bookmarks.add(currentNode.id);
    btn.classList.add('active');
    showToast('Bookmarked');
  }
  localStorage.setItem('aie-bookmarks', JSON.stringify([...bookmarks]));
}

function openSearch() {
  document.getElementById('search-modal').classList.add('open');
  setTimeout(() => document.getElementById('search-input').focus(), 50);
  doSearch('');
}

function closeSearch(event) {
  const modal = document.getElementById('search-modal');
  if (!event || event.target === modal) {
    modal.classList.remove('open');
    document.getElementById('search-input').value = '';
  }
}

function doSearch(query) {
  const q = query.toLowerCase().trim();
  const results = [];
  stages.forEach((stage) => {
    stage.nodes.forEach((node) => {
      if (!q || node.title.toLowerCase().includes(q) || node.tag.includes(q) || stage.label.toLowerCase().includes(q)) {
        results.push({ stage, node });
      }
    });
  });

  const resultsEl = document.getElementById('search-results');
  if (!results.length) {
    resultsEl.innerHTML = `<div class="search-empty">No results for "${query}"</div>`;
    return;
  }

  resultsEl.innerHTML = results.slice(0, 12).map(({ stage, node }) => `
    <button class="search-item" type="button" data-node-id="${node.id}" data-stage-id="${stage.id}">
      <span class="search-item-icon">${node.icon}</span>
      <span class="search-item-info">
        <span class="search-item-title">${node.title}</span>
        <span class="search-item-stage" style="color:${stage.color}">${stage.label}</span>
      </span>
      ${completed.has(node.id) ? '<span style="color:var(--accent3);font-size:.7rem">✓</span>' : ''}
    </button>
  `).join('');
}

function filterNodes(type, btn) {
  document.querySelectorAll('.filter-btn').forEach((button) => button.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.node').forEach((node) => {
    if (type === 'all') node.style.opacity = '1';
    else if (type === 'completed') node.style.opacity = completed.has(node.dataset.id) ? '1' : '.3';
    else node.style.opacity = !completed.has(node.dataset.id) ? '1' : '.3';
  });
}

function toggleTutor() {
  tutorOpen = !tutorOpen;
  document.getElementById('tutor-chat').classList.toggle('open', tutorOpen);
}

async function sendTutor() {
  const input = document.getElementById('tutor-input');
  const message = input.value.trim();
  if (!message) return;
  input.value = '';

  const messages = document.getElementById('tutor-messages');
  messages.innerHTML += `<div class="tutor-msg user">${message}</div>`;
  const typingId = `typing-${Date.now()}`;
  messages.innerHTML += `<div class="tutor-msg ai tutor-typing" id="${typingId}">Thinking...</div>`;
  messages.scrollTop = messages.scrollHeight;

  try {
    const data = await fetchJson('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        lesson_title: currentNode?.title ?? null,
        stage_label: currentStage?.label ?? null,
      }),
    });
    document.getElementById(typingId).textContent = data.reply;
    document.getElementById(typingId).classList.remove('tutor-typing');
  } catch (error) {
    document.getElementById(typingId).textContent = 'Chat endpoint failed.';
    document.getElementById(typingId).classList.remove('tutor-typing');
    console.error(error);
  }

  messages.scrollTop = messages.scrollHeight;
}

function copyCode(btn) {
  const code = btn.closest('.code-block').querySelector('code').textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = 'copied!';
    setTimeout(() => {
      btn.textContent = 'copy';
    }, 1500);
  });
}

function bindEvents() {
  document.addEventListener('click', (event) => {
    const node = event.target.closest('.node');
    if (node) {
      openLesson(node.dataset.id, node.dataset.stageId);
      return;
    }

    const searchItem = event.target.closest('.search-item');
    if (searchItem) {
      closeSearch();
      openLesson(searchItem.dataset.nodeId, searchItem.dataset.stageId);
      return;
    }

    const copyButton = event.target.closest('.copy-btn');
    if (copyButton) {
      copyCode(copyButton);
      return;
    }

    const taskItem = event.target.closest('[data-task-toggle], .task-list li');
    if (taskItem) {
      taskItem.classList.toggle('done');
    }
  });

  document.getElementById('nav-search-trigger').addEventListener('click', openSearch);
  document.getElementById('curriculum-trigger').addEventListener('click', (event) => {
    event.preventDefault();
    showToast('Curriculum overview is already on the page');
  });
  document.getElementById('search-close').addEventListener('click', () => closeSearch());
  document.getElementById('search-modal').addEventListener('click', closeSearch);
  document.getElementById('search-input').addEventListener('input', (event) => doSearch(event.target.value));
  document.getElementById('lesson-overlay').addEventListener('click', closeLesson);
  document.getElementById('lesson-close-btn').addEventListener('click', closeLesson);
  document.getElementById('complete-btn').addEventListener('click', markComplete);
  document.getElementById('bookmark-btn').addEventListener('click', toggleBookmark);
  document.getElementById('tutor-toggle').addEventListener('click', toggleTutor);
  document.getElementById('tutor-send').addEventListener('click', sendTutor);
  document.getElementById('tutor-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') sendTutor();
  });
  document.querySelectorAll('.filter-btn').forEach((button) => {
    button.addEventListener('click', () => filterNodes(button.dataset.filter, button));
  });
  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openSearch();
    }
    if (event.key === 'Escape') {
      closeSearch();
      closeLesson();
    }
  });
}

async function init() {
  await loadRoadmap();
  renderRoadmap();
  bindEvents();
}

init().catch((error) => {
  console.error(error);
  showToast('Failed to initialize roadmap');
});
