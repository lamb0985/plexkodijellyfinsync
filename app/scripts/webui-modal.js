(() => {
  if (new URLSearchParams(location.search).get('modal') === '1') {
    document.documentElement.classList.add('embedded-modal');
    const form = document.querySelector('form[action="/env"]');
    if (form) form.action = '/env?modal=1';
    return;
  }

  const dialog = document.createElement('dialog');
  dialog.className = 'ui-dialog';
  dialog.setAttribute('aria-labelledby', 'ui-dialog-title');
  dialog.innerHTML = '<div class="ui-dialog-head"><h2 id="ui-dialog-title"></h2><button type="button" class="ui-dialog-close" aria-label="Close">×</button></div><iframe title="" class="ui-dialog-frame"></iframe>';
  document.body.append(dialog);
  const frame = dialog.querySelector('iframe');
  const title = dialog.querySelector('h2');
  dialog.querySelector('button').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => { frame.src = 'about:blank'; document.body.classList.remove('ui-dialog-open'); });
  for (const link of document.querySelectorAll('.page-links a[href="/status-page"], .page-links a[href="/env"]')) {
    link.addEventListener('click', event => {
      event.preventDefault();
      title.textContent = link.getAttribute('href') === '/env' ? 'Environment settings' : 'Saved sync status';
      frame.title = title.textContent;
      dialog.classList.toggle('env-dialog', link.getAttribute('href') === '/env');
      frame.src = link.getAttribute('href') + '?modal=1';
      dialog.showModal();
      document.body.classList.add('ui-dialog-open');
      dialog.querySelector('button').focus();
    });
  }
})();
