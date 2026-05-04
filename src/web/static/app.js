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

/**
 * Handle node selected — fetch transfers for panel display
 * @param {Object} eventDetail - Event detail with node data
 */
function handleNodeSelected(eventDetail) {
  // First show basic node info in panel
  PanelModule.show(eventDetail);

  const nodeId = eventDetail.id;
  const nodeData = eventDetail.data;
  const chain = nodeData.chain || AppState.currentChain;
  const startDt = AppState.dateRange.from;
  const endDt = AppState.dateRange.to;

  if (!startDt || !endDt || !nodeId) return;

  // Fetch transfer data for this node to populate the table
  fetch(`/api/node/${encodeURIComponent(nodeId)}?chain=${encodeURIComponent(chain)}&start_dt=${encodeURIComponent(startDt)}&end_dt=${encodeURIComponent(endDt)}`)
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
      console.error('Error fetching node transactions:', error);
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
  .then(() => alert('Transaction saved'))
  .catch(err => alert('Error: ' + err.message));
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
    PanelModule.show(e.detail);
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

  // Clear button — removes all elements from graph and closes panel
  document.getElementById('clear-btn').addEventListener('click', () => {
    GraphModule.clear();
    PanelModule.hide();
  });
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);
