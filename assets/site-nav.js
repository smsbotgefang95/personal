const SHARED_NAV_ITEMS = [
  { id: "citizenship", href: "citizenship-interview-prep.html", label: "🇺🇸 US Citizenship Interview Prep" },
  { id: "english", href: "learning-english.html", label: "📘 Learning English" },
  { id: "time-analysis", href: "time-analysis.html", label: "⏰ Time Analysis" },
  { id: "kpi", href: "kpi-dashboard.html", label: "📊 KPI Life Tracker" },
  { id: "life", href: "life-events.html", label: "🗓️ Life Events" },
  { id: "gardening", href: "gardening-journal.html", label: "🌱 Gardening Journal" }
];

class SiteNav extends HTMLElement {
  connectedCallback() {
    const activePage = this.getAttribute("active-page") || "home";
    const sharedLinks = SHARED_NAV_ITEMS.map((item) => {
      const isActive = item.id === activePage;
      const activeClass = isActive ? " class=\"active\"" : "";
      const currentAttr = isActive ? " aria-current=\"page\"" : "";
      return `<a${activeClass} href="${item.href}"${currentAttr}>${item.label}</a>`;
    }).join("");

    this.innerHTML = `
      <nav class="site-nav" aria-label="Site navigation">
        <div class="site-nav-inner">
          <a class="site-brand" href="index.html">Home</a>
          <div class="site-nav-menu">
            <div class="site-links site-shared-links">${sharedLinks}</div>
          </div>
        </div>
      </nav>
    `;
  }
}

customElements.define("site-nav", SiteNav);
