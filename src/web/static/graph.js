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
      'label': 'data(amount)',
      'font-size': '10px',
      'color': '#ccc',
      'text-rotation': 'autorotate',
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
const DAGRE_LAYOUT = {
  name: 'dagre',
  rankDir: 'LR',        // Left to Right — money flow direction
  nodeSep: 60,          // horizontal spacing between nodes
  rankSep: 120,         // vertical spacing between ranks
  padding: 40,
  animate: true,
  animationDuration: 400,
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
setupEvents(cy);

/**
 * Setup all event handlers for the Cytoscape instance
 * @param {Object} cy - Cytoscape instance
 */
function setupEvents(cy) {
  // Single click on node → panel lateral
  cy.on('tap', 'node', (evt) => {
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

  const newIds = [...newNodes.map((n) => n.data.id),
                  ...newEdges.map((e) => e.data.id)];
  expandLayout(newIds);
}

/**
 * Run layout only on new elements to avoid repositioning existing nodes
 * @param {Array} newNodeIds - Array of new node IDs to layout
 */
function expandLayout(newNodeIds) {
  const subset = cy.elements().filter((el) =>
    newNodeIds.includes(el.id()) || el.neighborhood().some(
      (n) => newNodeIds.includes(n.id())
    )
  );
  subset.layout({
    ...DAGRE_LAYOUT,
    animate: true,
    fit: false,           // do NOT re-fit the whole viewport
  }).run();
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

// Export the module
window.GraphModule = { addElements, buildNodeLabel, clear };