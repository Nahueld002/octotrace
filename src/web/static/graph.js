/**
 * Cytoscape.js module for Octotrace graph visualization.
 * This module owns ALL cy.* calls and handles graph rendering, styling, and events.
 */

// Import the cytoscape-js skill for reference:
// https://github.com/octotrace/octotrace/blob/main/skills/cytoscape-js/SKILL.md

// Dark theme colors
const BACKGROUND_COLOR = '#1a1a2e';
const NODE_FILL_COLOR = '#16213e';
const NODE_BORDER_COLOR = '#0f3460';
const EDGE_COLOR = '#0f3460';
const ACCENT_COLOR = '#e94560';

// Graph styles following the cytoscape-js skill guidelines
const GRAPH_STYLES = [
  {
    selector: 'node',
    style: {
      'background-color': NODE_FILL_COLOR,
      'label': 'data(label)',
      'color': '#ffffff',
      'font-size': '11px',
      'text-valign': 'bottom',
      'text-margin-y': '6px',
      'width': '40px',
      'height': '40px',
      'border-width': '2px',
      'border-color': NODE_BORDER_COLOR,
    },
  },
  {
    // Exchange / known service nodes
    selector: 'node[service]',
    style: {
      'background-color': ACCENT_COLOR,
      'border-color': '#b8344a',
      'shape': 'rectangle',
    },
  },
  {
    // Node with public tag but not a known service
    selector: 'node[tag]',
    style: {
      'background-color': '#2d8a4e',
    },
  },
  {
    // Selected node
    selector: 'node:selected',
    style: {
      'border-color': ACCENT_COLOR,
      'border-width': '3px',
    },
  },
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': EDGE_COLOR,
      'target-arrow-color': EDGE_COLOR,
      'target-arrow-shape': 'triangle',   // ✓ valid — do NOT use 'triangle-back'
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
      'line-color': ACCENT_COLOR,
      'target-arrow-color': ACCENT_COLOR,
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
// CRITICAL: Assign cy first, then call cy.on('ready', ...) for events
const cy = cytoscape({
  container: document.getElementById('graph-container'),
  elements: [],
  style: GRAPH_STYLES,
  layout: { name: 'preset' },
});

// Setup events after cy is initialized
cy.on('ready', () => {
  setupEvents(cy);
});

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

  // Double click on node → expand
  cy.on('dbltap', 'node', (evt) => {
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

// Export the module
window.GraphModule = { addElements, buildNodeLabel, cy };