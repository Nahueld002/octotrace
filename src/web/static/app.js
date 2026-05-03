/**
 * Application state and fetch logic for Octotrace.
 * This module owns ALL fetch calls and application state.
 * It MUST NOT contain any cy.* calls or DOM manipulation.
 */

// Import the cytoscape-js skill for reference:
// https://github.com/octotrace/octotrace/blob/main/skills/cytoscape-js/SKILL.md

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
  
  const input = addressInput.value.trim();
  const chain = chainSelect.value;
  const startDt = dateFromInput.value;
  const endDt = dateToInput.value;
  
  // Validate inputs
  if (!input) {
    alert('Please enter a wallet address or transaction ID');
    return;
  }
  
  if (!startDt || !endDt) {
    alert('Please select both date range');
    return;
  }
  
  // Prepare payload
  const payload = {
    input: input,
    chain: chain,
    start_dt: startDt,
    end_dt: endDt
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
    // Add elements to graph
    GraphModule.addElements(data.elements.nodes, data.elements.edges);
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
  
  // Prepare payload
  const payload = {
    address: nodeId,
    chain: nodeData.chain,
    start_dt: AppState.dateRange.from,
    end_dt: AppState.dateRange.to
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
    GraphModule.addElements(data.elements.nodes, data.elements.edges);
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error: ' + error.message);
  });
}

/**
 * Initialize event listeners
 */
function initApp() {
  // Search button click handler
  document.getElementById('search-btn').addEventListener('click', handleSearch);
  
  // Listen for custom events from graph.js
  document.addEventListener('node:selected', (e) => {
    PanelModule.show(e.detail);
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
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);