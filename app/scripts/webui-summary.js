// Header counts use the same saved state and section rules as the Dashboard.
(function () {
  const summary = document.querySelector('.sync-summary');
  if (!summary) return;

  const fields = {
    progress: summary.querySelector('[data-summary="progress"]'),
    next: summary.querySelector('[data-summary="next"]'),
    aligned: summary.querySelector('[data-summary="aligned"]'),
  };

  async function refreshSummary() {
    try {
      const response = await fetch('/status', { cache: 'no-store', credentials: 'include' });
      if (!response.ok && response.status !== 404) throw new Error('Status unavailable');
      const result = await response.json();
      const entries = Object.values(result.data || {});
      let progress = 0;
      let next = 0;
      let aligned = 0;

      for (const entry of entries) {
        const platforms = ['plex', 'kodi', 'jellyfin'].map(name => entry[name]);
        const available = platforms.filter(Boolean);
        const isEpisode = available.some(item => item.media_type === 'episode');
        const hasResume = available.some(item =>
          item.resume && Number(item.resume) > 0 && item.status !== 'watched'
        );
        const isNext = !hasResume && isEpisode &&
          available.some(item => item.status === 'unwatched') &&
          available.every(item => item.status !== 'watched');
        if (!hasResume && !isNext) continue;

        if (hasResume) progress++;
        else next++;
        if (platforms.every(Boolean) &&
            platforms.every(item => item.status === platforms[0].status &&
              Math.abs(Number(item.resume || 0) - Number(platforms[0].resume || 0)) <= 1)) {
          aligned++;
        }
      }

      fields.progress.textContent = progress;
      fields.next.textContent = next;
      fields.aligned.textContent = `${aligned} / ${progress + next}`;
    } catch (error) {
      Object.values(fields).forEach(field => { field.textContent = '—'; });
    }
  }

  refreshSummary();
  setInterval(() => { if (!document.hidden) refreshSummary(); }, 5000);
  window.addEventListener('focus', refreshSummary);
})();
