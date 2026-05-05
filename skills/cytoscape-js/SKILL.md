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

Cytoscape.js is loaded first via vendor file, followed by elkjs and the
cytoscape-elk adapter. All three are vendorized locally in `static/vendor/`.

```html
<!-- Required load order in index.html — do not reorder -->
<script src="/static/vendor/cytoscape.min.js"></script>
<script src="/static/vendor/elk.bundled.js"></script>
<script src="/static/vendor/cytoscape-elk.js"></script>
<script src="/static/app.js"></script>
<script src="/static/graph.js"></script>
<script src="/static/panel.js"></script>
```

dagre files (`dagre.min.js`, `cytoscape-dagre.min.js`) remain in `vendor/`
for rollback safety but are no longer loaded in index.html.

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

**Critical**: Cytoscape's `ready` callback fires **synchronously during the
constructor**. This means you CANNOT use `.on('ready', ...)` after the
constructor — it will never fire because the event already happened.

```javascript
// graph.js

// WRONG — two patterns that DON'T work:
const cy = cytoscape({ ready: () => setup(cy) });  // ❌ TDZ: cy is undefined here
const cy = cytoscape({ ... });
cy.on('ready', () => setupEvents(cy));              // ❌ ready already fired

// CORRECT — assign first, then call setup directly
const cy = cytoscape({
  container: document.getElementById('graph-container'),
  elements: [],
  style: GRAPH_STYLES,
  layout: { name: 'preset' },
});
setupEvents(cy);  // ✓ cy is assigned, ready already fired during constructor
```

---

## Layout Configuration

### Initial Render: elk (layered algorithm)

Used when rendering a fresh query result. Applies the ELK layered (top-down)
algorithm with RIGHT direction (money flows left to right). The full graph
is laid out by elk once, with `fit: true` to zoom to the content.

```javascript
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
```

On initial render (`addElements` when `isInitialLoad === true`):
```javascript
cy.layout({ ...ELK_LAYOUT, fit: true }).run();
```

### Expansion: manual fan-out positioning

When expanding a node (double-click), new nodes are positioned manually
to the right of the anchor (expanded) node in a vertical fan-out pattern.
Existing nodes are never repositioned — the graph is always accumulative
and anchor positions are preserved.

```javascript
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
```

### Detecting initial vs expansion

`addElements` checks if the graph was empty before adding: if all current
nodes are new, it is an initial render and elk runs. Otherwise it is an
expansion and manual positioning is used.

```javascript
const isInitialLoad = cy.nodes().length === newNodes.length;
if (isInitialLoad) {
  cy.layout({ ...ELK_LAYOUT, fit: true }).run();
} else {
  expandLayout(newIds);
}
```

---

## Adding Elements (Incremental / Accumulative)

Never call `cy.elements().remove()` or re-initialize Cytoscape to add new
data. Use `cy.add()` with deduplication.

```javascript
/**
 * Add nodes and edges to the graph without duplicating existing elements.
 * Detects initial render vs expansion: first load uses elk layout,
 * expansions use manual fan-out positioning.
 *
 * @param {Array} nodes - Array of Cytoscape node descriptors { data: { id, label, tag, chain } }
 * @param {Array} edges - Array of Cytoscape edge descriptors { data: { id, source, target, amount, datetime } }
 */
function addElements(nodes, edges) {
  const newNodes = nodes.filter((n) => !cy.getElementById(n.data.id).length);
  const newEdges = edges.filter((e) => !cy.getElementById(e.data.id).length);

  if (!newNodes.length && !newEdges.length) return;

  cy.add([...newNodes, ...newEdges]);

  const isInitialLoad = cy.nodes().length === newNodes.length;
  const newIds = [...newNodes.map((n) => n.data.id),
                  ...newEdges.map((e) => e.data.id)];

  if (isInitialLoad) {
    cy.layout({ ...ELK_LAYOUT, fit: true }).run();
  } else {
    expandLayout(newIds);
  }
}
```

---

## Node & Edge Styles

```javascript
const GRAPH_STYLES = [
  // Default node — gray, rectangle
  { selector: 'node', style: {
      'background-color': '#4a4a6a', 'border-color': '#2a2a4a',
      'border-width': '2px', 'label': 'data(label)', 'color': '#ffffff',
      'font-size': '11px', 'text-valign': 'bottom', 'text-margin-y': '6px',
      'width': '40px', 'height': '40px', 'shape': 'rectangle',
  },},
  // Saved in DB — green fill
  { selector: 'node[?saved]', style: {
      'background-color': '#2d8a4e', 'border-color': '#1e6438',
  },},
  // Known exchange/service — orange, diamond, bigger
  { selector: 'node[?is_service]', style: {
      'background-color': '#e94560', 'border-color': '#b8344a',
      'shape': 'diamond', 'width': '50px', 'height': '50px',
  },},
  // Expanded node — dashed yellow border
  { selector: 'node.expanded', style: {
      'border-color': '#f5a623', 'border-width': '4px', 'border-style': 'dashed',
  },},
  // Selected node — white border, enlarged
  { selector: 'node:selected', style: {
      'border-color': '#ffffff', 'border-width': '3px', 'border-style': 'solid',
      'width': '52px', 'height': '52px',
  },},
  // Edge — default
  { selector: 'edge', style: {
      'width': 2, 'line-color': '#0f3460', 'target-arrow-color': '#0f3460',
      'target-arrow-shape': 'triangle', 'curve-style': 'bezier',
      'label': 'data(amount)', 'font-size': '10px', 'color': '#ccc',
      'text-rotation': 'autorotate',
  },},
  // Saved edge — green line
  { selector: 'edge[?saved]', style: {
      'line-color': '#2d8a4e', 'target-arrow-color': '#2d8a4e', 'width': 3,
  },},
  // Selected edge
  { selector: 'edge:selected', style: {
      'line-color': '#f5a623', 'target-arrow-color': '#f5a623', 'width': 3,
  },},
];
```

---

## Event Handling

```javascript
let lastTapTime = 0;
let lastTapTarget = null;
let lastExpandedId = null;

function setupEvents(cy) {
  // Single click on node → panel lateral (suppressed on dbltap)
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

  // Mark element as saved — switches to green immediately
  document.addEventListener('graph:mark-saved', (e) => {
    const { id } = e.detail;
    const el = cy.getElementById(id);
    if (el.length) el.data('saved', true);
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
| TDZ in constructor | `const cy = cytoscape({ ready: () => setup(cy) })` | Assign `cy` first, then call `setupEvents(cy)` directly — `ready` already fired |
| .on('ready', ...) after constructor | `cy.on('ready', () => setup(cy))` | Call setup directly: `setupEvents(cy)` — ready fires synchronously inside constructor |
| Destroying graph on new data | `cy.destroy()` + reinit | `cy.add()` with dedup |
| Double-tap opens panel twice | `tap` fires before `dbltap` — panel opens then re-opens | Debounce same-target rapid clicks: skip if `(now - lastTapTime) < 400` and same target |
| Expanded node moves during layout | All new nodes are in newNodeIds, anchor is not locked | Lock `lastExpandedId` in `expandLayout`: `!newNodeIds.includes(node.id()) \|\| node.id() === lastExpandedId` |
| Edge turns green but not persistent | Missing `edge[?saved]` selector or `"saved"` field in edge data | Add `edge[?saved]` style in GRAPH_STYLES AND set `"saved": txid in tx_saved_set` in backend |
| Migrating to React Flow | — | **Never. Cytoscape.js is the final choice.** |

---

## Resources

- **Cytoscape.js docs**: https://js.cytoscape.org/
- **elkjs**: https://github.com/kieler/elkjs
- **cytoscape-elk adapter**: https://github.com/cytoscape/cytoscape.js-elk
- **Cytoscape styles reference**: https://js.cytoscape.org/#style
