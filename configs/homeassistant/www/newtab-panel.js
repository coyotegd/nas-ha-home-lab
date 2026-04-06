class NewTabPanel extends HTMLElement {
  set panel(panel) {
    if (!this._opened) {
      this._opened = true;
      window.open(panel.config.url, "_blank");
    }
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      const div = document.createElement("div");
      div.style.cssText = "padding:24px;font-family:var(--paper-font-body1_-_font-family,sans-serif);";
      div.innerHTML = `<p>Opened <strong>${panel.config.name || panel.config.url}</strong> in a new tab.</p>
        <p><a href="${panel.config.url}" target="_blank">Click here</a> if it didn't open.</p>`;
      this.shadowRoot.appendChild(div);
    }
  }
}
customElements.define("newtab-panel", NewTabPanel);
