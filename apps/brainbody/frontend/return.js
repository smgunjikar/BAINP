'use strict';

(() => {
  const page = location.pathname;
  if (!['/sense-monitor', '/neurovision', '/cognition-dashboard'].includes(page)) return;
  const query = new URLSearchParams(location.search);
  const nav = document.createElement('nav');
  nav.setAttribute('aria-label', 'Brain–body context');
  const link = document.createElement('a');
  link.textContent = 'Open BBC-BE';
  nav.append(link);
  document.body.prepend(nav);

  function update() {
    const selectedMode = page === '/neurovision'
      ? document.getElementById('mode')?.value || query.get('mode')
      : query.get('mode');
    const mode = selectedMode === 'demo' ? 'demo' : 'active';
    const params = new URLSearchParams({mode});
    const person = query.get('person');
    if (page !== '/neurovision' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(person || '')) {
      params.set('person', person);
      if (mode === 'demo') params.set('profile', 'selected');
    }
    if (page === '/cognition-dashboard') params.set('view', 'timeline');
    link.href = '/brain-body?'+params;
  }

  update();
  if (page === '/neurovision') document.getElementById('mode')?.addEventListener('change', update);
})();
