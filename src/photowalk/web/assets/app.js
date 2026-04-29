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
    renderTimeline(entries);
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

      el.innerHTML = `
        <div class="filename">${icon} ${f.path.split('/').pop()}</div>
        <div class="meta">${ts}${dur}</div>
      `;
      el.addEventListener('click', () => selectFile(f.path, f.type, el));
      container.appendChild(el);
    });
  }

  function renderTimeline(entries) {
    const svg = document.getElementById('timeline-svg');
    const scroll = document.getElementById('timeline-scroll');

    const times = entries.map(e => new Date(e.start_time).getTime());
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times.map((t, i) => t + entries[i].duration_seconds * 1000));
    const totalMs = maxTime - minTime;
    const totalSeconds = totalMs / 1000;

    const barHeight = 40;
    const padding = 20;
    const svgHeight = barHeight + padding * 2;
    const scale = 50; // pixels per second
    const svgWidth = Math.max(scroll.clientWidth, totalSeconds * scale + padding * 2);

    svg.setAttribute('width', svgWidth);
    svg.setAttribute('height', svgHeight);
    svg.innerHTML = '';

    entries.forEach((entry, i) => {
      const startMs = new Date(entry.start_time).getTime() - minTime;
      const x = padding + (startMs / 1000) * scale;
      const w = Math.max(2, entry.duration_seconds * scale);
      const y = padding;

      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', w);
      rect.setAttribute('height', barHeight);
      rect.setAttribute('rx', 3);
      rect.classList.baseVal = `timeline-bar ${entry.kind === 'image' ? 'image' : 'video'}`;
      rect.dataset.path = entry.source_path;
      rect.dataset.kind = entry.kind === 'image' ? 'photo' : 'video';
      rect.addEventListener('click', () => selectFile(entry.source_path, rect.dataset.kind, rect));
      svg.appendChild(rect);

      if (w > 40) {
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', x + 4);
        label.setAttribute('y', y + barHeight / 2);
        label.classList.baseVal = 'timeline-label';
        const name = entry.source_path.split('/').pop();
        label.textContent = name.length > 20 ? name.slice(0, 18) + '…' : name;
        svg.appendChild(label);
      }
    });

    renderAxis(minTime, maxTime, scale, padding);
  }

  function renderAxis(minTime, maxTime, scale, padding) {
    const axis = document.getElementById('timeline-axis');
    axis.innerHTML = '';
    const totalSeconds = (maxTime - minTime) / 1000;
    const containerWidth = axis.clientWidth;
    const tickInterval = totalSeconds > 600 ? 60 : (totalSeconds > 120 ? 30 : 10);
    const numTicks = Math.floor(totalSeconds / tickInterval);

    for (let i = 0; i <= numTicks; i++) {
      const sec = i * tickInterval;
      const left = padding + sec * scale;
      if (left > containerWidth) break;

      const tick = document.createElement('div');
      tick.style.position = 'absolute';
      tick.style.left = left + 'px';
      tick.style.top = '0';
      tick.style.fontSize = '11px';
      tick.style.color = '#888';
      tick.style.paddingLeft = '4px';
      tick.style.borderLeft = '1px solid #444';
      tick.style.height = '100%';
      tick.style.whiteSpace = 'nowrap';

      const date = new Date(minTime + sec * 1000);
      tick.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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
      video.src = '/media/' + path;
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
})();
