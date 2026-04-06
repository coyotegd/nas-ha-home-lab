class UgosPanel extends HTMLElement {
  connectedCallback() {
    // Replace YOUR_NAS_IP with your NAS IP or UGOS hostname
    window.open("https://YOUR_NAS_IP:9443", "_blank");
    history.back();
  }
}
customElements.define("ugos-panel", UgosPanel);
