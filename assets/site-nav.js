const NAV_ITEMS = [
  { id: "home", label: "Home", href: "index.html" },
  { id: "life", label: "Life Events", href: "life-events.html" },
  { id: "citizenship", label: "Citizenship Prep", href: "citizenship-interview-prep.html" },
  { id: "kpi", label: "KPI Dashboard", href: "kpi-dashboard.html" },
  { id: "resources", label: "Resources", href: "resources.html" }
];

class SiteNav extends HTMLElement {
  connectedCallback() {
    const activePage = this.getAttribute("active-page") || "home";
    const links = NAV_ITEMS.map((item) => {
      const isActive = item.id === activePage;
      const activeClass = isActive ? " class=\"active\"" : "";
      const currentAttr = isActive ? " aria-current=\"page\"" : "";
      return `<a${activeClass} href="${item.href}"${currentAttr}>${item.label}</a>`;
    }).join("");

    this.innerHTML = `
      <nav class="site-nav" aria-label="Site navigation">
        <div class="site-nav-inner">
          <a class="site-brand" href="index.html">Personal</a>
          <div class="site-links">${links}</div>
        </div>
      </nav>
    `;
  }
}

customElements.define("site-nav", SiteNav);
