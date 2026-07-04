const SHARED_NAV_ITEMS = [
  { id: "citizenship", href: "citizenship-interview-prep.html", label: "🇺🇸 美国公民入籍面试备考" },
  { id: "english", href: "learning-english.html", label: "📘 学英语" },
  { id: "time-analysis", href: "time-analysis.html", label: "⏰ 时间分析" },
  { id: "kpi", href: "kpi-dashboard.html", label: "📊 KPI 生活追踪" },
  { id: "life", href: "life-events.html", label: "🗓️ 人生事件" },
  { id: "gardening", href: "gardening-journal.html", label: "🌱 园艺日志" }
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
      <nav class="site-nav" aria-label="站点导航">
        <div class="site-nav-inner">
          <a class="site-brand" href="index.html">首页</a>
          <div class="site-nav-menu">
            <div class="site-links site-shared-links">${sharedLinks}</div>
          </div>
        </div>
      </nav>
    `;
  }
}

customElements.define("site-nav", SiteNav);
