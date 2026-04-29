(async function() {
  const [timelineRes, filesRes] = await Promise.all([
    fetch('/api/timeline'),
    fetch('/api/files'),
  ]);
  const timelineData = await timelineRes.json();
  const filesData = await filesRes.json();

  const entries = timelineData.entries;
  const files = filesData.files;

  renderSidebar(files);
  if (entries.length > 0) {
    renderTimeline(entries, timelineData.settings.image_duration);
  } else {
    document.getElementById('timeline-scroll').innerHTML =
      '<div style="padding:20px;color:#666;">No timeline entries.</div>';
  }

  function renderSidebar(files) {
    const container = document.getElementById('sidebar-list');
    container.innerHTML = '';

    const hasTs = files.filter(f => f.has_timestamp);
    const noTs = files.filter(f => !f.has_timestamp);

    [...hasTs, ...noTs].forEach(f => {
      const el = document.createElement('div');
      el.className = 'sidebar-item' + (f.has_timestamp ? '' : ' warning');
      el.dataset.path = f.path;

      const icon = f.type === 'video' ? '🎬' : '📷';
      const ts = f.timestamp ? new Date(f.timestamp).toLocaleString() : 'No timestamp';
      const dur = f.duration_seconds ? ` • ${f.duration_seconds.toFixed(1)}s` : '';

      const filenameDiv = document.createElement('div');
      filenameDiv.className = 'filename';
      filenameDiv.textContent = `${icon} ${f.path.split('/').pop()}`;
      const metaDiv = document.createElement('div');
      metaDiv.className = 'meta';
      metaDiv.textContent = `${ts}${dur}`;
      el.appendChild(filenameDiv);
      el.appendChild(metaDiv);
      el.addEventListener('click', () => selectFile(f.path, f.type, el));
      container.appendChild(el);
    });
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
    const gap = 4; // visual gap between consecutive entries
    const svgHeight = barHeight + padding * 2;
    const scale = 50; // pixels per second

    // Sort entries by start_time to ensure correct visual order
    const sorted = [...entries].sort((a, b) =>
      new Date(a.start_time) - new Date(b.start_time)
    );

    // Build compressed positions — dead time between entries is removed
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

      // Map cumulative output time back to compressed x coordinate
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

  function selectFile(path, type, el) {
    // Clear previous selections
    document.querySelectorAll('.sidebar-item.selected').forEach(e => e.classList.remove('selected'));
    document.querySelectorAll('.timeline-bar.selected').forEach(e => e.classList.remove('selected'));

    if (el.classList.contains('sidebar-item')) {
      el.classList.add('selected');
      document.querySelectorAll(`.timeline-bar[data-path="${CSS.escape(path)}"]`).forEach(b => b.classList.add('selected'));
    } else {
      el.classList.add('selected');
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
      video.onloadedmetadata = null;
    } else {
      img.src = '/media/' + path;
      img.style.display = 'block';
      video.style.display = 'none';
      video.pause();
      video.src = '';
      video.onloadedmetadata = null;
    }
  }
})();
