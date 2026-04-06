class IframePanel extends HTMLElement {
  set panel(panel) {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      const iframe = document.createElement("iframe");
      iframe.src = panel.config.url;
      iframe.style.cssText = "border:0;width:100%;height:100%;position:absolute;top:0;left:0;";
      this.shadowRoot.appendChild(iframe);
    }
  }
}
customElements.define("iframe-panel", IframePanel);
