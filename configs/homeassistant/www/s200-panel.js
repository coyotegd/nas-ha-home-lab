class S200Panel extends HTMLElement {
  connectedCallback() {
    // Replace with your S200 NPM proxy URL or direct IP
    window.open("https://s200.yourdomain.com", "_blank");
    history.back();
  }
}
customElements.define("s200-panel", S200Panel);
