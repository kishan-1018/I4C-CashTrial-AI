/**
 * Interactive Multi-Rail Mule Network Graph Controller
 * Renders nodes, directed money-flow edges, velocity indicators, and account inspectors.
 */

class MuleGraphController {
  constructor(containerId = "graph-container") {
    this.containerId = containerId;
    this.container = null;
    this.graphData = null;
  }

  init() {
    this.container = document.getElementById(this.containerId);
  }

  render(graphData) {
    this.graphData = graphData;
    if (!this.container) this.init();
    if (!this.container) return;

    this.container.innerHTML = "";

    const width = this.container.clientWidth || 600;
    const height = this.container.clientHeight || 450;

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.style.cursor = "grab";

    // Defs for glowing arrowheads
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
      <marker id="arrow" viewBox="0 -5 10 10" refX="22" refY="0" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M0,-5L10,0L0,5" fill="#00E5FF"/>
      </marker>
    `;
    svg.appendChild(defs);

    const nodes = graphData.nodes || [];
    const links = graphData.links || [];

    // Calculate layout positions horizontally across hops
    const numNodes = nodes.length;
    const paddingX = 80;
    const stepX = (width - paddingX * 2) / Math.max(1, numNodes - 1);
    const midY = height / 2;

    const nodePositions = {};
    nodes.forEach((n, idx) => {
      nodePositions[n.id] = {
        x: paddingX + idx * stepX,
        y: midY + (idx % 2 === 0 ? -35 : 35),
        data: n
      };
    });

    // Render Links
    links.forEach(l => {
      const source = nodePositions[l.source];
      const target = nodePositions[l.target];
      if (!source || !target) return;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "line");
      path.setAttribute("x1", source.x);
      path.setAttribute("y1", source.y);
      path.setAttribute("x2", target.x);
      path.setAttribute("y2", target.y);
      path.setAttribute("stroke", "#00E5FF");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("stroke-opacity", "0.75");
      path.setAttribute("stroke-dasharray", "4, 4");
      path.setAttribute("marker-end", "url(#arrow)");
      svg.appendChild(path);

      // Edge label (amount & velocity)
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", (source.x + target.x) / 2);
      label.setAttribute("y", (source.y + target.y) / 2 - 8);
      label.setAttribute("fill", "#94A3B8");
      label.setAttribute("font-size", "10px");
      label.setAttribute("text-anchor", "middle");
      label.textContent = `INR ${l.amount.toLocaleString()} (${l.velocity_mins}m)`;
      svg.appendChild(label);
    });

    // Render Nodes
    nodes.forEach(n => {
      const pos = nodePositions[n.id];
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.style.cursor = "pointer";

      let color = "#38BDF8";
      if (n.node_type === "VICTIM") color = "#00E676"; // Green
      else if (n.node_type === "TERMINAL_MULE") color = "#FF3D71"; // Coral
      else if (n.node_type === "TOUCHPOINT") color = "#FFB300"; // Gold

      // Outer glow circle
      const outerCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      outerCircle.setAttribute("cx", pos.x);
      outerCircle.setAttribute("cy", pos.y);
      outerCircle.setAttribute("r", "16");
      outerCircle.setAttribute("fill", color);
      outerCircle.setAttribute("fill-opacity", "0.25");
      g.appendChild(outerCircle);

      // Core circle
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", pos.x);
      circle.setAttribute("cy", pos.y);
      circle.setAttribute("r", "10");
      circle.setAttribute("fill", color);
      circle.setAttribute("stroke", "#0E1626");
      circle.setAttribute("stroke-width", "2");
      g.appendChild(circle);

      // Text label
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", pos.x);
      text.setAttribute("y", pos.y + 24);
      text.setAttribute("fill", "#F8FAFC");
      text.setAttribute("font-size", "11px");
      text.setAttribute("font-weight", "600");
      text.setAttribute("text-anchor", "middle");
      text.textContent = n.label.length > 18 ? n.label.substring(0, 16) + '...' : n.label;
      g.appendChild(text);

      // Sub-label (Bank / Role)
      const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
      sub.setAttribute("x", pos.x);
      sub.setAttribute("y", pos.y + 36);
      sub.setAttribute("fill", "#64748B");
      sub.setAttribute("font-size", "9px");
      sub.setAttribute("text-anchor", "middle");
      sub.textContent = n.bank || n.role || '';
      g.appendChild(sub);

      // Click event on node
      g.addEventListener("click", () => {
        alert(
          `Node Details:\n` +
          `Label: ${n.label}\n` +
          `Role: ${n.role || n.node_type}\n` +
          `Bank: ${n.bank || 'N/A'}\n` +
          `IFSC: ${n.ifsc || 'N/A'}\n` +
          `Centrality Index: ${n.centrality || '0.0'}\n` +
          `State: ${n.branch_state || n.jurisdiction || 'N/A'}`
        );
      });

      svg.appendChild(g);
    });

    this.container.appendChild(svg);
  }
}

window.muleGraph = new MuleGraphController();
