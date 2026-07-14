/* Cmd+K palette. Rows are rendered server-side with data-label; this filters
   them client-side, supports up/down/enter, and clicks the active row.
   No backend — every row is a link or a local action. */
function commandPalette() {
  return {
    q: "",
    active: 0,
    rows() {
      return Array.prototype.slice.call(this.$refs.list.querySelectorAll("[data-label]"));
    },
    visible() {
      var q = this.q.trim().toLowerCase();
      return this.rows().filter(function (r) {
        return !q || r.dataset.label.toLowerCase().indexOf(q) !== -1;
      });
    },
    open() {
      this.q = "";
      this.active = 0;
      this.$nextTick(function () {
        this.filter();
        this.$refs.search.focus();
      }.bind(this));
    },
    filter() {
      var vis = this.visible();
      this.rows().forEach(function (r) { r.style.display = "none"; });
      vis.forEach(function (r) { r.style.display = ""; });
      if (this.active >= vis.length) this.active = Math.max(0, vis.length - 1);
      this.highlight(vis);
    },
    highlight(vis) {
      var list = vis || this.visible();
      this.rows().forEach(function (r) { r.classList.remove("cmdk-row--active"); });
      if (list[this.active]) list[this.active].classList.add("cmdk-row--active");
    },
    move(d) {
      var vis = this.visible();
      if (!vis.length) return;
      this.active = (this.active + d + vis.length) % vis.length;
      this.highlight(vis);
      vis[this.active].scrollIntoView({ block: "nearest" });
    },
    choose() {
      var vis = this.visible();
      if (vis[this.active]) vis[this.active].click();
    },
  };
}
