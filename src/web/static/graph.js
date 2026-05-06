/**
 * Cytoscape.js module for Octotrace graph visualization.
 * This module owns ALL cy.* calls and handles graph rendering, styling, and events.
 */

// Import the cytoscape-js skill for reference:
// https://github.com/octotrace/octotrace/blob/main/skills/cytoscape-js/SKILL.md

// Dark theme base colors
const EDGE_COLOR = '#0f3460';

// Graph styles — forensic color palette
// Order matters for selector specificity in Cytoscape.
const GRAPH_STYLES = [
  {
    // Default node — gray, rectangle
    selector: 'node',
    style: {
      'background-color': '#4a4a6a',
      'border-color': '#2a2a4a',
      'border-width': '2px',
      'label': 'data(label)',
      'color': '#ffffff',
      'font-size': '11px',
      'text-valign': 'bottom',
      'text-margin-y': '6px',
      'width': '40px',
      'height': '40px',
      'shape': 'rectangle',
    },
  },
  {
    // Saved in DB — green fill
    selector: 'node[?saved]',
    style: {
      'background-color': '#2d8a4e',
      'border-color': '#1e6438',
    },
  },
  {
    // Known exchange/service — orange, diamond, bigger
    selector: 'node[?is_service]',
    style: {
      'background-color': '#e94560',
      'border-color': '#b8344a',
      'shape': 'diamond',
      'width': '50px',
      'height': '50px',
    },
  },
  {
    // Expanded node — dashed yellow border (overrides border-color and width)
    selector: 'node.expanded',
    style: {
      'border-color': '#f5a623',
      'border-width': '4px',
      'border-style': 'dashed',
    },
  },
  {
    // Selected node — white border, enlarged
    selector: 'node:selected',
    style: {
      'border-color': '#ffffff',
      'border-width': '3px',
      'border-style': 'solid',
      'width': '52px',
      'height': '52px',
    },
  },
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': EDGE_COLOR,
      'target-arrow-color': EDGE_COLOR,
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(edgeLabel)',
      'text-wrap': 'wrap',
      'text-max-width': '120px',
      'font-size': '10px',
      'color': '#ccc',
      'text-rotation': 'autorotate',
    },
  },
  {
    // Saved edge — green line
    selector: 'edge[?saved]',
    style: {
      'line-color': '#2d8a4e',
      'target-arrow-color': '#2d8a4e',
      'width': 3,
    },
  },
  {
    selector: 'edge:selected',
    style: {
      'line-color': '#f5a623',
      'target-arrow-color': '#f5a623',
      'width': 3,
    },
  },
];

// Layout configuration
const ELK_LAYOUT = {
  name: 'elk',
  animate: true,
  animationDuration: 400,
  fit: false,
  elk: {
    'algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.layered.spacing.nodeNodeBetweenLayers': '120',
    'elk.spacing.nodeNode': '60',
    'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
    'elk.layered.cycleBreaking.strategy': 'GREEDY',
    'elk.edgeRouting': 'ORTHOGONAL',
  },
};

// Initialize Cytoscape instance
const cy = cytoscape({
  container: document.getElementById('graph-container'),
  elements: [],
  style: GRAPH_STYLES,
  layout: { name: 'preset' },
});

// Ready event fires DURING constructor above — calling .on('ready', ...) after
// would never trigger. Call setup directly instead.
let lastExpandedId = null;
setupEvents(cy);

/**
 * Setup all event handlers for the Cytoscape instance
 * @param {Object} cy - Cytoscape instance
 */
function setupEvents(cy) {
  // Prevent tap from firing on dbltap — debounce same-target rapid clicks
  let lastTapTime = 0;
  let lastTapTarget = null;

  // Single click on node → panel lateral
  cy.on('tap', 'node', (evt) => {
    const now = Date.now();
    const isSameTarget = lastTapTarget === evt.target.id();
    const isDoubleTap = (now - lastTapTime) < 400;

    lastTapTime = now;
    lastTapTarget = evt.target.id();

    if (isSameTarget && isDoubleTap) return; // ignore — this is a dbltap

    document.dispatchEvent(new CustomEvent('node:selected', {
      detail: { id: evt.target.id(), data: evt.target.data() }
    }));
  });

  // Single click on edge → panel lateral
  cy.on('tap', 'edge', (evt) => {
    document.dispatchEvent(new CustomEvent('edge:selected', {
      detail: { id: evt.target.id(), data: evt.target.data() }
    }));
  });

  // Double click on node → expand + visual indicator
  cy.on('dbltap', 'node', (evt) => {
    evt.target.addClass('expanded');
    lastExpandedId = evt.target.id();
    document.dispatchEvent(new CustomEvent('node:expand', {
      detail: { id: evt.target.id(), data: evt.target.data() }
    }));
  });

  // Click on background → deselect panel
  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      document.dispatchEvent(new CustomEvent('graph:deselect'));
    }
  });

  // Listen for save events from app.js — mark element as saved
  document.addEventListener('graph:mark-saved', (e) => {
    const { id } = e.detail;
    const el = cy.getElementById(id);
    if (el.length) el.data('saved', true);
  });
}

/**
 * Add nodes and edges to the graph without duplicating existing elements.
 * Existing elements are preserved — the graph is always accumulative.
 *
 * @param {Array} nodes - Array of Cytoscape node descriptors { data: { id, label, tag, chain } }
 * @param {Array} edges - Array of Cytoscape edge descriptors { data: { id, source, target, amount, datetime } }
 */
function addElements(nodes, edges) {
  const newNodes = nodes.filter((n) => !cy.getElementById(n.data.id).length);
  const newEdges = edges.filter((e) => !cy.getElementById(e.data.id).length);

  if (!newNodes.length && !newEdges.length) return;

  cy.add([...newNodes, ...newEdges]);

  // Set compound edge label: amount + datetime
  newEdges.forEach(e => {
    const el = cy.getElementById(e.data.id);
    if (!el.length) return;
    const amount = e.data.amount || '';
    const dt = e.data.datetime || '';
    const dateShort = dt ? dt.slice(0, 16).replace('T', ' ') : '';
    el.data('edgeLabel', dateShort ? `${amount}\n${dateShort}` : amount);
  });

  const isInitialLoad = cy.nodes().length === newNodes.length;
  const newIds = [...newNodes.map((n) => n.data.id),
                  ...newEdges.map((e) => e.data.id)];

  if (isInitialLoad) {
    // Primer render — usar elk para layout completo
    cy.layout({ ...ELK_LAYOUT, fit: true }).run();
  } else {
    // Expansión — posicionamiento manual sin mover nodos existentes
    expandLayout(newIds);
  }
}

/**
 * Position new nodes manually in a fan-out pattern to the right of the anchor node.
 * Called during expansions — avoids re-running elk on the entire graph.
 * @param {Array} newNodeIds - Array of new element IDs to position
 */
function expandLayout(newNodeIds) {
  const anchorNode = lastExpandedId ? cy.getElementById(lastExpandedId) : null;
  const anchorPos = anchorNode && anchorNode.length
    ? anchorNode.position()
    : { x: 0, y: 0 };

  const newNodes = cy.nodes().filter((n) =>
    newNodeIds.includes(n.id()) && n.id() !== lastExpandedId
  );

  if (!newNodes.length) {
    lastExpandedId = null;
    return;
  }

  // Posicionar nuevos nodos en abanico a la derecha del anchor
  const STEP_X = 220;
  const STEP_Y = 80;
  const total = newNodes.length;
  const startY = anchorPos.y - ((total - 1) * STEP_Y) / 2;

  newNodes.forEach((node, i) => {
    node.position({
      x: anchorPos.x + STEP_X,
      y: startY + i * STEP_Y,
    });
  });

  lastExpandedId = null;
}

/**
 * Build the display label for a node from address metadata.
 *
 * @param {string} address - Full wallet address.
 * @param {string|null} tag - Public nametag from API, or null.
 * @param {string|null} service - Known service name, or null.
 * @returns {string} Display label for Cytoscape node.
 */
function buildNodeLabel(address, tag, service) {
  if (service) return service;
  if (tag) return tag;
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

/**
 * Clear all elements from the graph.
 * Called by the Clear button in app.js — search and expand never call this.
 */
function clear() {
    cy.elements().remove();
}

/**
 * Mark a graph element as saved by its ID.
 * Changes the element's visual style immediately via the [?saved] selector.
 * @param {string} id - Element ID (txid for edges, address for nodes)
 */
function markSaved(id) {
  const el = cy.getElementById(id);
  if (el.length) el.data('saved', true);
}

/**
 * Run a layout on the given Cytoscape instance.
 * Used by app.js to trigger layout after adding elements to the case view.
 *
 * @param {Object} cyInstance - Cytoscape instance to layout
 * @param {Object} layoutOptions - Layout configuration (merged with defaults)
 */
function runLayout(cyInstance, layoutOptions = {}) {
  cyInstance.layout({ ...ELK_LAYOUT, ...layoutOptions }).run();
}

/**
 * Initialize a new Cytoscape instance for the case graph view.
 * Uses the same GRAPH_STYLES and event handlers as the main graph.
 * Layout is NOT triggered here — app.js adds elements then calls runLayout.
 *
 * @param {string} containerId - DOM element ID for the container
 * @returns {Object} New Cytoscape instance
 */
function initCaseGraph(containerId) {
  const cyCase = cytoscape({
    container: document.getElementById(containerId),
    elements: [],
    style: GRAPH_STYLES,
    layout: { name: 'preset' },
  });
  setupEvents(cyCase);
  return cyCase;
}

/**
 * Clear all elements from the case graph instance.
 * Used instead of destroy() — the container is hidden via CSS, and the
 * instance persists in memory but empty. This avoids the destroy/recreate
 * cycle and prevents memory leaks from orphaned event listeners.
 *
 * @param {Object} cyInstance - Cytoscape instance to clear
 */
function clearCaseGraph(cyInstance) {
  if (cyInstance) {
    cyInstance.elements().remove();
  }
}

/**
 * Add nodes and edges to the case graph without duplicating existing elements.
 * Uses AppState.cyCase as the target Cytoscape instance.
 * Does NOT run layout — app.js handles that separately.
 *
 * @param {Array} nodes - Array of Cytoscape node descriptors { data: { id, label, tag, chain } }
 * @param {Array} edges - Array of Cytoscape edge descriptors { data: { id, source, target, amount, datetime } }
 */
function addCaseElements(nodes, edges) {
  const cyCase = AppState.cyCase;
  if (!cyCase) return;

  const newNodes = nodes.filter((n) => !cyCase.getElementById(n.data.id).length);
  const newEdges = edges.filter((e) => !cyCase.getElementById(e.data.id).length);

  if (!newNodes.length && !newEdges.length) return;

  cyCase.add([...newNodes, ...newEdges]);

  // Set compound edge label: amount + datetime
  newEdges.forEach(e => {
    const el = cyCase.getElementById(e.data.id);
    if (!el.length) return;
    const amount = e.data.amount || '';
    const dt = e.data.datetime || '';
    const dateShort = dt ? dt.slice(0, 16).replace('T', ' ') : '';
    el.data('edgeLabel', dateShort ? `${amount}\n${dateShort}` : amount);
  });
}

// Export the module
window.GraphModule = { addElements, addCaseElements, buildNodeLabel, clear, markSaved, initCaseGraph, clearCaseGraph, runLayout };