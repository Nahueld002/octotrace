/**
 * Side panel module for Octotrace.
 * This module owns ALL DOM manipulation for the side panel.
 * It MUST NOT contain any fetch calls or cy.* calls.
 */

// Import the cytoscape-js skill for reference:
// https://github.com/octotrace/octotrace/blob/main/skills/cytoscape-js/SKILL.md

// Private state
PanelModule = {
  _currentType: null, // node|edge|null
};

/**
 * Show panel with node or edge information
 * @param {Object} data - Node or edge data
 */
PanelModule.show = function(data) {
  const panel = document.getElementById('side-panel');
  const content = document.getElementById('panel-content');
  
  // Determine if it's a node or edge
  const isEdge = data.hasOwnProperty('source');
  this._currentType = isEdge ? 'edge' : 'node';
  
  // Clear previous content
  content.innerHTML = '';
  
  // Build content based on type
  if (isEdge) {
    // Edge data
    const edgeFields = [
      { label: 'Transaction ID', value: data.id },
      { label: 'Amount', value: data.amount },
      { label: 'Date', value: data.datetime },
      { label: 'Chain', value: data.chain }
    ];
    
    edgeFields.forEach(field => {
      const fieldDiv = document.createElement('div');
      fieldDiv.className = 'panel-field';
      
      const label = document.createElement('label');
      label.textContent = field.label;
      
      const value = document.createElement('div');
      value.textContent = field.value;
      
      fieldDiv.appendChild(label);
      fieldDiv.appendChild(value);
      content.appendChild(fieldDiv);
    });
    
    // Add evidence link
    const evidenceLink = document.createElement('a');
    evidenceLink.href = `https://${data.chain === 'ETH' ? 'etherscan.io' : 'tronscan.org'}/tx/${data.id}`;
    evidenceLink.textContent = 'View on Blockchain Explorer';
    evidenceLink.target = '_blank';
    
    const linkContainer = document.createElement('div');
    linkContainer.className = 'panel-field';
    linkContainer.appendChild(evidenceLink);
    content.appendChild(linkContainer);
  } else {
    // Node data
    const nodeFields = [
      { label: 'Address', value: data.id },
      { label: 'Chain', value: data.chain },
      { label: 'Service', value: data.service || 'Unknown' },
      { label: 'Tag', value: data.tag || 'None' }
    ];
    
    nodeFields.forEach(field => {
      const fieldDiv = document.createElement('div');
      fieldDiv.className = 'panel-field';
      
      const label = document.createElement('label');
      label.textContent = field.label;
      
      const value = document.createElement('div');
      value.textContent = field.value;
      
      fieldDiv.appendChild(label);
      fieldDiv.appendChild(value);
      content.appendChild(fieldDiv);
    });
    
    // Add evidence link
    const evidenceLink = document.createElement('a');
    evidenceLink.href = `https://${data.chain === 'ETH' ? 'etherscan.io' : 'tronscan.org'}/address/${data.id}`;
    evidenceLink.textContent = 'View on Blockchain Explorer';
    evidenceLink.target = '_blank';
    
    const linkContainer = document.createElement('div');
    linkContainer.className = 'panel-field';
    linkContainer.appendChild(evidenceLink);
    content.appendChild(linkContainer);
  }
  
  // Show panel
  panel.classList.add('open');
  
  // Wire save button
  document.getElementById('panel-save').onclick = () => this.save(data);
  
  // Wire close button
  document.getElementById('panel-close').onclick = () => this.hide();
};

/**
 * Hide the side panel
 */
PanelModule.hide = function() {
  const panel = document.getElementById('side-panel');
  panel.classList.remove('open');
  document.getElementById('panel-content').innerHTML = '';
  this._currentType = null;
};

/**
 * Save data (node or edge)
 * @param {Object} data - Node or edge data to save
 */
PanelModule.save = function(data) {
  const isEdge = data.hasOwnProperty('source');
  const endpoint = isEdge ? '/api/save/tx' : '/api/save/address';
  
  fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      id: data.id,
      chain: data.chain
    })
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(result => {
    alert(isEdge ? 'Transaction saved successfully!' : 'Address saved successfully!');
  })
  .catch(error => {
    console.error('Error saving:', error);
    alert('Error saving: ' + error.message);
  });
};