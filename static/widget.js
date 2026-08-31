(function () {
  const script = document.currentScript || document.querySelector('script[src*="/api/v1/widgets/script.js"]');
  if (!script) return;

  const tenantId = script.getAttribute('data-tenant-id') || 'DEMO_TENANT';
  const widgetContainerId = 'nexus-widget';
  const host = script.src.replace(/\/api\/v1\/widgets\/script\.js.*$/, '');
  const apiUrl = `${host}/api/v1/widgets/embed-data?tenant_id=${encodeURIComponent(tenantId)}`;

  function buildWidgetMarkup(data) {
    const reviews = Array.isArray(data?.reviews) ? data.reviews : [];
    const config = data?.config || {};
    const primaryColor = config.primary_color || '#4F46E5';
    const theme = config.theme === 'dark' ? 'dark' : 'light';
    const layout = config.layout || 'slider';
    const showDate = config.show_date !== false;

    const reviewCards = reviews
      .map((review) => {
        const reviewText = review.review_text || 'No review text available.';
        const author = review.author_name || 'Verified customer';
        const createdAt = review.created_at ? new Date(review.created_at).toLocaleDateString() : '';
        const stars = Array.from({ length: 5 }, (_, index) => `
          <span style="color:${index < Number(review.rating) ? '#fbbf24' : '#cbd5e1'}; font-size:14px;">★</span>
        `).join('');

        return `
          <article style="background:${theme === 'dark' ? '#0f172a' : '#ffffff'}; border:1px solid rgba(148,163,184,0.22); border-radius:16px; padding:16px; box-shadow:0 10px 25px rgba(15,23,42,0.08); display:flex; flex-direction:column; gap:10px; min-height:160px;">
            <div style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
              <div style="display:flex; flex-direction:column; gap:4px;">
                <strong style="font-size:15px; color:${theme === 'dark' ? '#f8fafc' : '#0f172a'};">${author}</strong>
                <div style="display:flex; align-items:center; gap:2px;">${stars}</div>
              </div>
              ${showDate && createdAt ? `<span style="font-size:11px; color:${theme === 'dark' ? '#94a3b8' : '#64748b'};">${createdAt}</span>` : ''}
            </div>
            <p style="margin:0; color:${theme === 'dark' ? '#e2e8f0' : '#334155'}; line-height:1.5; font-size:14px;">${reviewText}</p>
          </article>
        `;
      })
      .join('');

    const containerStyles = `
      :host {
        all: initial;
        color-scheme: light;
        font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }
      * { box-sizing: border-box; }
      .widget-shell {
        width: 100%;
        max-width: 520px;
        margin: 0 auto;
        background: ${theme === 'dark' ? '#020817' : '#f8fafc'};
        border: 1px solid rgba(148,163,184,0.2);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 14px 35px rgba(15, 23, 42, 0.12);
      }
      .widget-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 16px;
      }
      .widget-title {
        font-size: 18px;
        font-weight: 700;
        color: ${theme === 'dark' ? '#f8fafc' : '#0f172a'};
        margin: 0;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 7px 10px;
        border-radius: 999px;
        background: ${primaryColor}1A;
        color: ${primaryColor};
        font-size: 12px;
        font-weight: 700;
      }
      .review-grid {
        display: grid;
        gap: 14px;
      }
      .review-grid[data-layout="slider"] {
        grid-template-columns: 1fr;
      }
      .review-grid[data-layout="grid"] {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .review-grid[data-layout="badge"] {
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      }
      @media (max-width: 640px) {
        .review-grid[data-layout="grid"] {
          grid-template-columns: 1fr;
        }
      }
    `;

    return `
      <style>${containerStyles}</style>
      <div class="widget-shell">
        <div class="widget-header">
          <h3 class="widget-title">What clients say</h3>
          <span class="badge">${reviews.length} reviews</span>
        </div>
        <div class="review-grid" data-layout="${layout}">${reviewCards || '<p style="margin:0; color:#64748b;">No reviews available.</p>'}</div>
      </div>
    `;
  }

  async function initWidget() {
    const target = document.getElementById(widgetContainerId) || document.body.appendChild(Object.assign(document.createElement('div'), { id: widgetContainerId }));
    const shadowHost = target;
    if (!shadowHost.shadowRoot) {
      shadowHost.attachShadow({ mode: 'open' });
    }

    try {
      const response = await fetch(apiUrl, { headers: { Accept: 'application/json' } });
      if (!response.ok) {
        throw new Error(`Widget data fetch failed: ${response.status}`);
      }

      const data = await response.json();
      const shadowRoot = shadowHost.shadowRoot;
      shadowRoot.innerHTML = buildWidgetMarkup(data);
    } catch (error) {
      console.error('Nexus widget load failed:', error);
      if (shadowHost.shadowRoot) {
        shadowHost.shadowRoot.innerHTML = '<div style="padding:16px;color:#ef4444;font-family:Arial,sans-serif;">Widget failed to load.</div>';
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWidget, { once: true });
  } else {
    initWidget();
  }
})();
