---
name: cytoscape-js
description: >
  Cytoscape.js graph rendering, event handling, layout configuration, and
  incremental expansion patterns for forensic transaction graphs.
  Trigger: When developing or modifying any file in static/ that interacts
  with Cytoscape: graph.js, app.js, or index.html graph container.
license: Apache-2.0
metadata:
  author: octotrace
  version: "1.0"
  scope: [web]
  auto_invoke:
    - "Developing interactive graph visualization with Cytoscape.js"
    - "Modifying graph.js"
    - "Modifying app.js graph-related logic"
    - "Adding or changing node/edge styles"
    - "Implementing node expansion or click events"
    - "Changing graph layout"
---

## When to Use

- Creating or modifying `graph.js` (Cytoscape instance, styles, events)
- Adding node/edge rendering logic in `app.js`
- Implementing expand-on-doubleclick behavior
- Changing visual styles for nodes, edges, or labels
- Debugging graph rendering or event handling issues

---

## Stack Constraint

Cytoscape.js is loaded via CDN in `index.html`. The `dagre` layout requires
the `cytoscape-dagre` plugin, also loaded via CDN **before** the app scripts.

```html
<!-- Required CDN order in index.html — do not reorder -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
<script src="app.js"></script>
<script src="graph.js"></script>
<script src="panel.js"></script>
```

---

## Module Boundary (CRITICAL)

`graph.js` and `app.js` have strict, non-overlapping responsibilities.
**No agent may cross this boundary.**

| File | Owns | Must NOT contain |
|------|------|-----------------|
| `graph.js` | Cytoscape instance, styles, layouts, events, `addElements()` | fetch calls, URL building, date logic |
| `app.js` | fetch, state, input handling, date ranges | any `cy.` calls, Cytoscape API |
| `panel.js` | DOM panel updates, save buttons | any `cy.` calls, fetch calls |

If implementing a feature requires touching both `graph.js` and `app.js`,
use the **event bridge pattern** — `graph.js` dispatches a `CustomEvent`,
`app.js` listens. Never call functions across modules directly.

```javascript
// graph.js — dispatch event on node click
cy.on('tap', 'node', (evt) => {
  const node = evt.target;
  document.dispatchEvent(new CustomEvent('node:selected', {
    detail: { id: node.id(), data: node.data() }
  }));
});

// app.js — listen and react
document.addEventListener('node:selected', (e) => {
  currentSelection = e.detail;
  // call panel.js or fetch more data
});
```

---

## Initialization Pattern

**Critical**: Cytoscape's `ready` callback fires synchronously during the
constructor. Always assign `cy` before calling any setup functions.

```javascript
// graph.js

// WRONG — TDZ bug: setup() runs before cy is assigned
const cy = cytoscape({ ready: () => setup(cy) });  // ❌

// CORRECT — assign first, then configure
const cy = cytoscape({
  container: document.getElementById('graph-container'),
  elements: [],
  style: GRAPH_STYLES,
  layout: { name: 'preset' },
});
cy.on('ready', () => setupEvents(cy));  // ✓
```

---

## Layout Configuration

### Default: dagre (full render)

Used when rendering a fresh query result.

```javascript
const DAGRE_LAYOUT = {
  name: 'dagre',
  rankDir: 'LR',        // Left to Right — money flow direction
  nodeSep: 60,          // horizontal spacing between nodes
  rankSep: 120,         // vertical spacing between ranks
  padding: 40,
  animate: true,
  animationDuration: 400,
};

function runLayout() {
  cy.layout(DAGRE_LAYOUT).run();
}
```

### Expansion: dagre on subset

When expanding a node, run layout only on new elements to avoid
repositioning existing nodes.

```javascript
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
```

---

## Adding Elements (Incremental / Accumulative)

Never call `cy.elements().remove()` or re-initialize Cytoscape to add new
data. Use `cy.add()` with deduplication.

```javascript
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
```

---

## Node & Edge Styles

```javascript
const GRAPH_STYLES = [
  {
    selector: 'node',
    style: {
      'background-color': '#2d6a9f',
      'label': 'data(label)',
      'color': '#ffffff',
      'font-size': '11px',
      'text-valign': 'bottom',
      'text-margin-y': '6px',
      'width': '40px',
      'height': '40px',
      'border-width': '2px',
      'border-color': '#1a4a6e',
    },
  },
  {
    // Exchange / known service nodes
    selector: 'node[service]',
    style: {
      'background-color': '#e07b00',
      'border-color': '#a05500',
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
      'border-color': '#f5c518',
      'border-width': '3px',
    },
  },
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': '#555',
      'target-arrow-color': '#555',
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
      'line-color': '#f5c518',
      'target-arrow-color': '#f5c518',
      'width': 3,
    },
  },
];
```

---

## Event Handling

```javascript
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
  cy.on('dblclick', 'node', (evt) => {
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
```

---

## Node Label Strategy

Each node gets a `label` field in its `data`. Priority order:

1. `service` — known exchange name (e.g. `"Binance"`) → shown in orange rectangle
2. `tag` — public nametag from API (e.g. `"Binance 14"`) → shown in green
3. Truncated address — first 6 + `...` + last 4 chars (e.g. `"0x4e83...311c"`)

```javascript
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
```

---

## Known Bugs (Do Not Reintroduce)

| Bug | Wrong | Correct |
|-----|-------|---------|
| Invalid arrow shape | `'triangle-back'` | `'triangle'` |
| TDZ in constructor | `const cy = cytoscape({ ready: () => setup(cy) })` | Assign `cy` first, then call `cy.on('ready', ...)` |
| Destroying graph on new data | `cy.destroy()` + reinit | `cy.add()` with dedup |
| Migrating to React Flow | — | **Never. Cytoscape.js is the final choice.** |

---

## Resources

- **Cytoscape.js docs**: https://js.cytoscape.org/
- **dagre layout plugin**: https://github.com/cytoscape/cytoscape.js-dagre
- **Cytoscape styles reference**: https://js.cytoscape.org/#style
