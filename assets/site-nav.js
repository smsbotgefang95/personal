const SHARED_NAV_ITEMS = [
  { id: "home", label: "Home", href: "index.html" },
  { id: "resources", label: "Resources", href: "resources.html" }
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
          <a class="site-brand" href="index.html">Personal</a>
          <div class="site-nav-menu">
            <div class="site-links site-shared-links">${sharedLinks}</div>
          </div>
        </div>
      </nav>
    `;
  }
}

customElements.define("site-nav", SiteNav);
