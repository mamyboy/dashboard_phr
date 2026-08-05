/* Responsive controller for the self-contained PHR dashboard. */
class ResponsiveChartController {
  static profileForWidth(width) {
    const w = Math.max(0, Number(width) || 0);
    let name = 'desktop';
    if (w <= 360) name = 'phone-xs';
    else if (w <= 390) name = 'phone-sm';
    else if (w <= 430) name = 'phone';
    else if (w <= 768) name = 'tablet';
    else if (w <= 1024) name = 'laptop';
    return {width: w, name, phone: w <= 430, tablet: w <= 1024};
  }

  constructor({charts, rerender, debounceMs = 140}) {
    this.charts = charts;
    this.rerender = rerender;
    this.debounceMs = debounceMs;
    this.mode = null;
    this.timer = null;
    this.observer = null;
    this.widths = new WeakMap();
    this.started = false;
    this.onViewportChange = this.onViewportChange.bind(this);
  }

  profile() {
    const width = typeof window === 'undefined' ? 1025 : window.innerWidth;
    return ResponsiveChartController.profileForWidth(width);
  }

  observeCharts() {
    if (!this.observer || typeof document === 'undefined') return;
    Object.keys(this.charts).forEach(id => {
      const element = document.getElementById(id);
      if (element) this.observer.observe(element);
    });
  }

  resizeAll() {
    Object.values(this.charts).forEach(chart => {
      if (chart && typeof chart.resize === 'function') chart.resize();
    });
  }

  onContainerResize(entries) {
    const resize = () => {
      entries.forEach(entry => {
        const width = entry.contentRect.width;
        const previous = this.widths.get(entry.target);
        this.widths.set(entry.target, width);
        if (previous !== undefined && Math.abs(previous - width) < 0.5) return;
        const chart = this.charts[entry.target.id];
        if (chart && typeof chart.resize === 'function') chart.resize();
      });
    };
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(resize);
    else resize();
  }

  onViewportChange() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      const next = this.profile().name;
      if (next !== this.mode) {
        this.mode = next;
        this.rerender();
        this.observeCharts();
      } else {
        this.resizeAll();
      }
    }, this.debounceMs);
  }

  start() {
    if (this.started || typeof window === 'undefined') return;
    this.started = true;
    this.mode = this.profile().name;
    if (typeof ResizeObserver !== 'undefined') {
      this.observer = new ResizeObserver(entries => this.onContainerResize(entries));
      this.observeCharts();
    }
    window.addEventListener('resize', this.onViewportChange, {passive: true});
    window.addEventListener('orientationchange', this.onViewportChange, {passive: true});
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', this.onViewportChange, {passive: true});
    }
  }

  stop() {
    clearTimeout(this.timer);
    if (this.observer) this.observer.disconnect();
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', this.onViewportChange);
      window.removeEventListener('orientationchange', this.onViewportChange);
      if (window.visualViewport) window.visualViewport.removeEventListener('resize', this.onViewportChange);
    }
    this.started = false;
  }
}

if (typeof globalThis !== 'undefined') globalThis.ResponsiveChartController = ResponsiveChartController;
if (typeof module !== 'undefined' && module.exports) module.exports = {ResponsiveChartController};
