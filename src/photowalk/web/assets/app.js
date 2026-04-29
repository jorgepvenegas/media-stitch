(async function() {
  // ----- State -----
  const selection = new Set();      // checked file paths
  const pendingStack = [];          // offset entries
  let allFiles = [];                // most recent files response
  let lastPreviewFiles = [];        // files from last preview, for diff modal
  let previewIsCurrent = false;     // false if stack changed since last preview
  let originalTimestamps = {};      // path -> ISO string at app load (or after apply)

  // ----- Initial load -----
  const [timelineRes, filesRes] = await Promise.all([
    fetch('/api/timeline'),
    fetch('/api/files'),
  ]);
  const timelineData = await timelineRes.json();
  const filesData = await filesRes.json();

  allFiles = filesData.files;
  allFiles.forEach(f => { originalTimestamps[f.path] = f.timestamp; });
  renderSidebar(allFiles);
  renderTimelineFromData(timelineData);

  bindSyncPanel();
  updateButtons();

  function renderTimelineFromData(td) {
    const entries = td.entries;
    if (entries.length > 0) {
      renderTimeline(entries, td.settings.image_duration);
    } else {
      document.getElementById('timeline-scroll').innerHTML =
        '<div style="padding:20px;color:#666;">No timeline entries.</div>';
    }
  }

  // ----- Sidebar -----
  function renderSidebar(files) {
    const container = document.getElementById('sidebar-list');
    container.innerHTML = '';

    const hasTs = files.filter(f => f.has_timestamp);
    const noTs = files.filter(f => !f.has_timestamp);

    [...hasTs, ...noTs].forEach(f => {
      const el = document.createElement('div');
      el.className = 'sidebar-item' + (f.has_timestamp ? '' : ' warning') + (f.shifted ? ' shifted' : '');
      el.dataset.path = f.path;

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.disabled = !f.has_timestamp;
      checkbox.checked = selection.has(f.path);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) selection.add(f.path);
        else selection.delete(f.path);
        updateSelectionCount();
        updateButtons();
      });
      el.appendChild(checkbox);

      const block = document.createElement('div');
      block.className = 'filename-block';

      const icon = f.type === 'video' ? '🎬' : '📷';
      const ts = f.timestamp ? new Date(f.timestamp).toLocaleString() : 'No timestamp';
      const dur = f.duration_seconds ? ` • ${f.duration_seconds.toFixed(1)}s` : '';

      const filenameDiv = document.createElement('div');
      filenameDiv.className = 'filename';
      filenameDiv.textContent = `${icon} ${f.path.split('/').pop()}`;
      if (f.shifted) {
        const badge = document.createElement('span');
        badge.className = 'shifted-badge';
        badge.textContent = 'shifted';
        filenameDiv.appendChild(badge);
      }
      const metaDiv = document.createElement('div');
      metaDiv.className = 'meta';
      metaDiv.textContent = `${ts}${dur}`;

      block.appendChild(filenameDiv);
      block.appendChild(metaDiv);
      block.addEventListener('click', () => selectFile(f.path, f.type, el));
      el.appendChild(block);

      container.appendChild(el);
    });

    updateSelectionCount();
  }

  function updateSelectionCount() {
    const total = allFiles.filter(f => f.has_timestamp).length;
    document.getElementById('sync-selection-count').textContent =
      `${selection.size} of ${total} files selected`;
  }

  // ----- Sync panel wiring -----
  function bindSyncPanel() {
    document.querySelectorAll('input[name="sync-mode"]').forEach(r => {
      r.addEventListener('change', () => {
        const mode = r.value;
        if (!r.checked) return;
        document.getElementById('sync-duration').style.display = mode === 'duration' ? '' : 'none';
        document.getElementById('sync-reference').style.display = mode === 'reference' ? '' : 'none';
        document.getElementById('sync-error').textContent = '';
      });
    });

    document.getElementById('btn-all-videos').addEventListener('click', () => {
      allFiles.filter(f => f.has_timestamp && f.type === 'video').forEach(f => selection.add(f.path));
      renderSidebar(allFiles);
      updateButtons();
    });
    document.getElementById('btn-all-photos').addEventListener('click', () => {
      allFiles.filter(f => f.has_timestamp && f.type === 'photo').forEach(f => selection.add(f.path));
      renderSidebar(allFiles);
      updateButtons();
    });
    document.getElementById('btn-clear-selection').addEventListener('click', () => {
      selection.clear();
      renderSidebar(allFiles);
      updateButtons();
    });

    document.getElementById('btn-add-to-queue').addEventListener('click', addToQueue);
    document.getElementById('btn-update-timeline').addEventListener('click', updateTimeline);
    document.getElementById('btn-clear-queue').addEventListener('click', clearQueue);
    document.getElementById('btn-apply').addEventListener('click', openApplyModal);
    document.getElementById('btn-modal-cancel').addEventListener('click', closeApplyModal);
    document.getElementById('btn-modal-confirm').addEventListener('click', confirmApply);
  }

  function updateButtons() {
    document.getElementById('btn-add-to-queue').disabled = selection.size === 0;
    document.getElementById('btn-update-timeline').disabled = pendingStack.length === 0;
    document.getElementById('btn-clear-queue').disabled = pendingStack.length === 0;
    document.getElementById('btn-apply').disabled = pendingStack.length === 0 || !previewIsCurrent;
  }

  function selectFile(path, type, el) {
    document.querySelectorAll('.sidebar-item.selected').forEach(e => e.classList.remove('selected'));
    document.querySelectorAll('.timeline-bar.selected').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
    if (el.classList.contains('sidebar-item')) {
      document.querySelectorAll(`.timeline-bar[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
    } else {
      document.querySelectorAll(`.sidebar-item[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
    }

    const video = document.getElementById('preview-video');
    const img = document.getElementById('preview-image');
    const placeholder = document.getElementById('preview-placeholder');
    placeholder.style.display = 'none';

    if (type === 'video') {
      let src = '/media/' + path;
      const trimStart = el.dataset.trimStart;
      const trimEnd = el.dataset.trimEnd;
      if (trimStart !== undefined && trimEnd !== undefined) {
        src += '#t=' + parseFloat(trimStart) + ',' + parseFloat(trimEnd);
      }
      video.src = src;
      video.style.display = 'block';
      img.style.display = 'none';
      video.load();
    } else {
      img.src = '/media/' + path;
      img.style.display = 'block';
      video.style.display = 'none';
      video.pause();
      video.src = '';
    }
  }

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function renderTimeline(entries, imageDuration) {
    const svg = document.getElementById('timeline-svg');
    const scroll = document.getElementById('timeline-scroll');
    const barHeight = 40;
    const padding = 20;
    const gap = 4;
    const svgHeight = barHeight + padding * 2;
    const scale = 50;

    const sorted = [...entries].sort((a, b) =>
      new Date(a.start_time) - new Date(b.start_time)
    );

    let currentX = padding;
    const positions = sorted.map(entry => {
      const effectiveDuration = entry.kind === 'image' ? imageDuration : entry.duration_seconds;
      const width = Math.max(2, effectiveDuration * scale);
      const x = currentX;
      currentX += width + gap;
      return { entry, x, width, effectiveDuration };
    });

    const svgWidth = Math.max(scroll.clientWidth, currentX + padding);
    svg.setAttribute('width', svgWidth);
    svg.setAttribute('height', svgHeight);
    svg.innerHTML = '';

    positions.forEach(({ entry, x, width }) => {
      const y = padding;
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', width);
      rect.setAttribute('height', barHeight);
      rect.setAttribute('rx', 3);
      rect.setAttribute('class', `timeline-bar ${entry.kind === 'image' ? 'image' : 'video'}`);
      rect.dataset.path = entry.source_path;
      rect.dataset.kind = entry.kind === 'image' ? 'photo' : 'video';
      if (entry.kind === 'video_segment') {
        rect.dataset.trimStart = entry.trim_start;
        rect.dataset.trimEnd = entry.trim_end;
      }
      rect.addEventListener('click', () => selectFile(entry.source_path, rect.dataset.kind, rect));
      svg.appendChild(rect);

      if (width > 40) {
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', x + 4);
        label.setAttribute('y', y + barHeight / 2);
        label.setAttribute('class', 'timeline-label');
        let name = entry.source_path.split('/').pop();
        if (entry.kind === 'video_segment' && entry.trim_start != null && entry.trim_end != null) {
          name = `${name} [${formatTime(entry.trim_start)}–${formatTime(entry.trim_end)}]`;
        }
        label.textContent = name.length > 30 ? name.slice(0, 28) + '…' : name;
        svg.appendChild(label);
      }
    });

    renderAxis(positions, scale, padding, gap);
  }

  function renderAxis(positions, scale, padding, gap) {
    const axis = document.getElementById('timeline-axis');
    axis.innerHTML = '';
    if (positions.length === 0) return;

    const totalOutputSeconds = positions.reduce((sum, p) => sum + p.effectiveDuration, 0);
    const containerWidth = axis.clientWidth;
    const tickInterval = totalOutputSeconds > 600 ? 60 : (totalOutputSeconds > 120 ? 30 : 10);
    const numTicks = Math.floor(totalOutputSeconds / tickInterval);

    for (let i = 0; i <= numTicks; i++) {
      const sec = i * tickInterval;
      let accumulated = 0;
      let x = padding;
      for (const p of positions) {
        if (accumulated + p.effectiveDuration >= sec) {
          const intoBlock = sec - accumulated;
          x = p.x + intoBlock * scale;
          break;
        }
        accumulated += p.effectiveDuration;
        x = p.x + p.width + gap;
      }
      if (x > containerWidth) break;

      const tick = document.createElement('div');
      tick.style.position = 'absolute';
      tick.style.left = x + 'px';
      tick.style.top = '0';
      tick.style.fontSize = '11px';
      tick.style.color = '#888';
      tick.style.paddingLeft = '4px';
      tick.style.borderLeft = '1px solid #444';
      tick.style.height = '100%';
      tick.style.whiteSpace = 'nowrap';

      const minutes = Math.floor(sec / 60);
      const seconds = Math.floor(sec % 60);
      tick.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
      axis.appendChild(tick);
    }
  }

  function renderQueue() {
    const container = document.getElementById('sync-queue');
    container.innerHTML = '';
    pendingStack.forEach((entry, idx) => {
      const row = document.createElement('div');
      row.className = 'queue-entry';

      const left = document.createElement('span');
      const sign = entry.delta_seconds >= 0 ? '+' : '';
      const label = entry.source.kind === 'duration'
        ? entry.source.text
        : `ref ${sign}${Math.round(entry.delta_seconds)}s`;
      const target = entry.target_paths.length === 1
        ? entry.target_paths[0].split('/').pop()
        : `${entry.target_paths.length} files`;
      left.textContent = `${idx + 1}. ${label} → ${target}`;

      const remove = document.createElement('button');
      remove.textContent = '×';
      remove.addEventListener('click', () => {
        pendingStack.splice(idx, 1);
        previewIsCurrent = false;
        renderQueue();
        updateButtons();
      });

      row.appendChild(left);
      row.appendChild(remove);
      container.appendChild(row);
    });
  }

  async function addToQueue() {
    const errEl = document.getElementById('sync-error');
    errEl.textContent = '';

    const mode = document.querySelector('input[name="sync-mode"]:checked').value;
    let body;
    if (mode === 'duration') {
      const text = document.getElementById('sync-duration-input').value.trim();
      if (!text) { errEl.textContent = 'Enter a duration'; return; }
      body = { kind: 'duration', text };
    } else {
      const wrong = document.getElementById('sync-ref-wrong').value.trim();
      const correct = document.getElementById('sync-ref-correct').value.trim();
      if (!wrong || !correct) { errEl.textContent = 'Enter both timestamps'; return; }
      body = { kind: 'reference', wrong, correct };
    }

    let parseRes;
    try {
      parseRes = await fetch('/api/offset/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(r => r.json());
    } catch (e) {
      errEl.textContent = 'Network error contacting server';
      return;
    }

    if (parseRes.error) { errEl.textContent = parseRes.error; return; }

    pendingStack.push({
      id: crypto.randomUUID(),
      delta_seconds: parseRes.delta_seconds,
      source: body,
      target_paths: [...selection],
    });

    previewIsCurrent = false;
    renderQueue();
    updateButtons();
  }

  async function clearQueue() {
    if (pendingStack.length === 0) return;
    pendingStack.length = 0;
    document.getElementById('sync-error').textContent = '';
    renderQueue();
    await updateTimeline();
  }

  async function updateTimeline() {
    let res;
    try {
      res = await fetch('/api/timeline/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ offsets: pendingStack }),
      }).then(r => r.json());
    } catch (e) {
      showToast('Could not update timeline', { error: true });
      return;
    }

    allFiles = res.files;
    lastPreviewFiles = res.files;
    renderSidebar(allFiles);
    renderTimelineFromData({ entries: res.entries, settings: res.settings });
    previewIsCurrent = true;
    updateButtons();
  }

  function showToast(msg, opts = {}) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast' + (opts.error ? ' error' : '');
    t.style.display = '';
    if (!opts.sticky) {
      setTimeout(() => { t.style.display = 'none'; }, 4000);
    }
  }

  async function openApplyModal() {
    const diffEl = document.getElementById('apply-diff');
    diffEl.innerHTML = '';

    const shiftedFiles = lastPreviewFiles.filter(f => f.shifted);
    if (shiftedFiles.length === 0) {
      showToast('No files would change');
      return;
    }

    shiftedFiles.forEach(f => {
      const row = document.createElement('div');
      const oldTs = originalTimestamps[f.path] || '(none)';
      row.textContent = `${f.path.split('/').pop()}  ${oldTs}  →  ${f.timestamp}`;
      diffEl.appendChild(row);
    });

    const modal = document.getElementById('apply-modal');
    modal.style.display = '';
  }

  function closeApplyModal() {
    document.getElementById('apply-modal').style.display = 'none';
  }

  async function confirmApply() {
    let res;
    try {
      res = await fetch('/api/sync/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ offsets: pendingStack }),
      }).then(r => r.json());
    } catch (e) {
      showToast('Apply failed — no changes confirmed', { error: true, sticky: true });
      closeApplyModal();
      return;
    }

    allFiles = res.files;
    lastPreviewFiles = res.files;
    originalTimestamps = {};
    allFiles.forEach(f => { originalTimestamps[f.path] = f.timestamp; });

    pendingStack.length = 0;
    selection.clear();
    previewIsCurrent = false;
    renderQueue();
    renderSidebar(allFiles);
    renderTimelineFromData(res.timeline);
    updateButtons();
    closeApplyModal();

    if (res.failed && res.failed.length > 0) {
      const lines = res.failed.map(f => `${f.path.split('/').pop()}: ${f.error}`).join('\n');
      showToast(
        `Applied ${res.applied.length} of ${res.applied.length + res.failed.length}.\n${lines}`,
        { error: true, sticky: true },
      );
    } else {
      showToast(`Applied ${res.applied.length} files`);
    }
  }

  // Expose nothing globally — each task wires its own button handler.
})();
