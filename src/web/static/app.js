/**
 * Application state and fetch logic for Octotrace.
 * This module owns ALL fetch calls and application state.
 * It MUST NOT contain any cy.* calls or DOM manipulation.
 */

// Application state
window.AppState = {
  currentChain: 'ETH',
  dateRange: {from: '', to: ''},
  nodeContextMap: {},
  caseViewActive: false,
  caseGraphLoaded: false,
  cyCase: null,
  
  /**
   * Get node context information
   * @param {string} address - Wallet address
   * @returns {Object|null} Node context or null
   */
  getNodeContext(address) {
    return this.nodeContextMap[address] || null;
  },
  
  /**
   * Set node context information
   * @param {string} address - Wallet address
   * @param {Object} context - Context object with chain, start, end properties
   */
  setNodeContext(address, context) {
    this.nodeContextMap[address] = context;
  }
};

/**
 * Handle search button click
 */
function handleSearch() {
  const addressInput = document.getElementById('address-input');
  const chainSelect = document.getElementById('chain-select');
  const dateFromInput = document.getElementById('date-from');
  const dateToInput = document.getElementById('date-to');
  const minAmountInput = document.getElementById('min-amount');
  
  const input = addressInput.value.trim();
  const chain = chainSelect.value;
  const startDt = dateFromInput.value;
  const endDt = dateToInput.value;
  const minAmount = minAmountInput ? minAmountInput.value || '1' : '1';
  
  // Validate inputs
  if (!input) {
    alert('Please enter a wallet address or transaction ID');
    return;
  }
  
  if (!startDt || !endDt) {
    alert('Please select both date range');
    return;
  }

  // Persist search context for expand operations
  AppState.dateRange = { from: startDt, to: endDt };
  AppState.currentChain = chain;

  // Prepare payload
  const payload = {
    input: input,
    chain: chain,
    start_dt: startDt,
    end_dt: endDt,
    min_amount: minAmount
  };

  // Make API call
  fetch('/api/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    // Display informative message if backend returned one
    if (data.message) {
      alert(data.message);
    }
    // Add elements to graph
    if (data.elements) {
      GraphModule.addElements(data.elements.nodes, data.elements.edges);
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error: ' + error.message);
  });
}

/**
 * Handle node expansion
 * @param {Object} eventDetail - Event detail with node data
 */
function handleNodeExpand(eventDetail) {
  // Do not expand in case view — no date range context, out of scope
  if (AppState.caseViewActive) return;

  const nodeId = eventDetail.id;
  const nodeData = eventDetail.data;
  const minAmountInput = document.getElementById('min-amount');
  const minAmount = minAmountInput ? minAmountInput.value || '1' : '1';
  
  // Prepare payload
  const payload = {
    address: nodeId,
    chain: nodeData.chain,
    start_dt: AppState.dateRange.from,
    end_dt: AppState.dateRange.to,
    min_amount: minAmount
  };
  
  // Make API call
  fetch('/api/expand', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    // Add elements to graph
    if (data.elements) {
      GraphModule.addElements(data.elements.nodes, data.elements.edges);
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error: ' + error.message);
  });
}

// AbortController for node selection — cancel stale fetches
let nodeSelectController = null;

/**
 * Handle node selected — fetch transfers for panel display
 * @param {Object} eventDetail - Event detail with node data
 */
function handleNodeSelected(eventDetail) {
  // Cancel previous fetch if still pending
  if (nodeSelectController) {
    nodeSelectController.abort();
  }
  nodeSelectController = new AbortController();

  // First show basic node info in panel
  PanelModule.show(eventDetail.data); // anteriormente como `PanelModule.show(eventDetail);`

  const nodeId = eventDetail.id;
  const nodeData = eventDetail.data;
  const chain = nodeData.chain || AppState.currentChain;
  const startDt = AppState.dateRange.from;
  const endDt = AppState.dateRange.to;

  if (!startDt || !endDt || !nodeId) return;

  // Fetch transfer data for this node to populate the table
  fetch(`/api/node/${encodeURIComponent(nodeId)}?chain=${encodeURIComponent(chain)}&start_dt=${encodeURIComponent(startDt)}&end_dt=${encodeURIComponent(endDt)}`, {
      signal: nodeSelectController.signal
    })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      if (data.transfers) {
        PanelModule.renderTransfers(data.transfers, eventDetail.id);
      }
    })
    .catch(error => {
      if (error.name === 'AbortError') return; // fetch cancelled — ignore
      console.error('Error fetching node transactions:', error);
      PanelModule.showError(error.message);
    });
}

/**
 * Handle save:tx event — save transaction to database
 * @param {Object} tx - Transaction data from the detail event
 */
function handleSaveTx(tx) {
  fetch('/api/save/tx', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      tx: {
        txid: tx.txid,
        chain: tx.chain,
        from_address: tx.from_address,
        to_address: tx.to_address,
        amount: tx.amount,
        datetime_utc: tx.datetime_utc,
        token_symbol: tx.token_symbol || 'USDT',
        block_number: tx.block_number || null,
        confirmations: tx.confirmations || null,
        tag_from: tx.tag_from || null,
        tag_to: tx.tag_to || null,
        url_tx: tx.url_tx || '',
        raw_json: tx.raw_json || '{}'
      }
    })
  })
  .then(r => r.json())
  .then(result => {
    // Mark the edge as saved in the graph — immediate visual feedback
    GraphModule.markSaved(tx.txid);
    GraphModule.markSaved(tx.from_address);
    GraphModule.markSaved(tx.to_address);
    if (result.already_existed) {
      alert('⚠️ Esta transacción ya estaba guardada. Los datos fueron actualizados.');
    } else {
      alert('✅ Transacción guardada correctamente.');
    }
  })
  .catch(err => alert('Error: ' + err.message));
}

/**
 * Handle case view toggle button click.
 * Switches between the main investigation graph and the case graph view.
 * Uses CSS .hidden class to toggle visibility — never calls destroy().
 * The case graph is lazily loaded on first toggle to case view.
 * Inputs are disabled while case view is active.
 */
function handleCaseToggle() {
  const toggleBtn = document.getElementById('case-toggle-btn');
  const caseContainer = document.getElementById('case-graph-container');
  const mainContainer = document.getElementById('graph-container');
  const searchInputs = [
    'address-input', 'chain-select', 'date-from', 'date-to',
    'min-amount', 'search-btn', 'clear-btn'
  ];

  if (AppState.caseViewActive) {
    // --- Switch OFF: clear case view, show main view ---
    // Clear the case graph elements (never destroy the instance)
    // The cyCase instance persists in memory but empty, per user constraint
    if (AppState.cyCase) {
      GraphModule.clearCaseGraph(AppState.cyCase);
    }
    caseContainer.classList.add('hidden');
    mainContainer.classList.remove('hidden');
    AppState.caseViewActive = false;
    AppState.caseGraphLoaded = false;
    toggleBtn.textContent = '📁 Case View';
    // Re-enable search inputs
    searchInputs.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.disabled = false;
    });
  } else {
    // --- Switch ON: hide main view, show case view ---
    mainContainer.classList.add('hidden');
    caseContainer.classList.remove('hidden');
    AppState.caseViewActive = true;
    toggleBtn.textContent = '🔍 Investigation';
    // Disable search inputs
    searchInputs.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.disabled = true;
    });

    // Always re-fetch fresh data (case view = fresh snapshot each activation)
    // Show spinner, hide empty message
    document.getElementById('case-spinner').classList.remove('hidden');
    document.getElementById('case-empty').classList.add('hidden');

    fetch('/api/case/graph')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        document.getElementById('case-spinner').classList.add('hidden');
        if (data.elements && (data.elements.nodes.length || data.elements.edges.length)) {
          // Create cyCase once on first load, reuse on subsequent toggles
          if (!AppState.cyCase) {
            AppState.cyCase = GraphModule.initCaseGraph('case-graph-container');
          }
          GraphModule.addCaseElements(data.elements.nodes, data.elements.edges);
          GraphModule.runLayout(AppState.cyCase, { fit: true });
          AppState.caseGraphLoaded = true;
        } else {
          document.getElementById('case-empty').classList.remove('hidden');
        }
      })
      .catch(err => {
        document.getElementById('case-spinner').classList.add('hidden');
        const emptyEl = document.getElementById('case-empty');
        emptyEl.textContent = 'Error: ' + err.message;
        emptyEl.classList.remove('hidden');
      });
  }
}

/**
 * Initialize event listeners
 */
function initApp() {
  // Search button click handler
  document.getElementById('search-btn').addEventListener('click', handleSearch);
  
  // Listen for custom events from graph.js
  document.addEventListener('node:selected', (e) => {
    handleNodeSelected(e.detail);
  });
  
  document.addEventListener('edge:selected', (e) => {
    PanelModule.showEdge(e.detail.data);
  });
  
  document.addEventListener('node:expand', (e) => {
    handleNodeExpand(e.detail);
  });
  
  document.addEventListener('graph:deselect', () => {
    PanelModule.hide();
  });

  // Listen for save events from panel.js
  document.addEventListener('save:tx', (e) => {
    handleSaveTx(e.detail);
  });

  // Listen for address label save events from panel.js
  document.addEventListener('address:label', (e) => {
    const { address, chain, label_manual } = e.detail;
    fetch('/api/address/label', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address, chain, label_manual })
    })
    .then(r => r.json())
    .then(() => alert('\u2705 Etiqueta guardada.'))
    .catch(err => alert('Error: ' + err.message));
  });

  // Clear button — removes all elements from graph and closes panel
  document.getElementById('clear-btn').addEventListener('click', () => {
    GraphModule.clear();
    PanelModule.hide();
  });

  // Case view toggle button
  document.getElementById('case-toggle-btn').addEventListener('click', handleCaseToggle);
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);
