/**
 * Side panel module for Octotrace.
 * This module owns ALL DOM manipulation for the side panel.
 * It MUST NOT contain any fetch calls or cy.* calls.
 * For saves, it emits CustomEvents — app.js handles the fetch.
 */

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
    
    // Add loading indicator for transfers table
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'panel-field';
    loadingDiv.id = 'panel-transfers-loading';
    loadingDiv.textContent = 'Loading transactions...';
    content.appendChild(loadingDiv);
  }
  
  // Show panel
  panel.classList.add('open');
  
  // Wire close button
  document.getElementById('panel-close').onclick = () => this.hide();
};

/**
 * Render transaction table for a node in the panel.
 * Called by app.js after fetching transfer data.
 *
 * @param {Array} transfers - List of normalized transfer dictionaries
 * @param {string} focalAddress - The address clicked (to determine IN/OUT)
 */
PanelModule.renderTransfers = function(transfers, focalAddress) {
  // Remove loading indicator
  const loadingEl = document.getElementById('panel-transfers-loading');
  if (loadingEl) loadingEl.remove();

  const content = document.getElementById('panel-content');

  // Section header
  const header = document.createElement('h4');
  header.textContent = `Transactions (${transfers.length})`;
  content.appendChild(header);

  // Build table
  const table = document.createElement('table');
  table.className = 'panel-transactions-table';

  // Header row
  const thead = document.createElement('thead');
  thead.innerHTML = `
    <tr>
      <th>Type</th>
      <th>Date</th>
      <th>Amount</th>
      <th>From</th>
      <th>To</th>
      <th>TXID</th>
      <th>Tag</th>
      <th></th>
    </tr>
  `;
  table.appendChild(thead);

  // Data rows
  const tbody = document.createElement('tbody');
  transfers.forEach(tx => {
    const row = document.createElement('tr');

    // Type badge (IN / OUT / SELF)
    const typeCell = document.createElement('td');
    const isFrom = tx.from_address === focalAddress;
    const isTo = tx.to_address === focalAddress;
    if (isFrom && isTo) {
      typeCell.innerHTML = '<span class="badge-self">↔ SELF</span>';
    } else if (isTo) {
      typeCell.innerHTML = '<span class="badge-in">▼ IN</span>';
    } else {
      typeCell.innerHTML = '<span class="badge-out">▲ OUT</span>';
    }
    row.appendChild(typeCell);

    // Date
    const dateCell = document.createElement('td');
    dateCell.textContent = tx.datetime_utc ? tx.datetime_utc.slice(0, 10) : '';
    row.appendChild(dateCell);

    // Amount
    const amtCell = document.createElement('td');
    amtCell.textContent = tx.amount || '0';
    row.appendChild(amtCell);

    // From
    const fromCell = document.createElement('td');
    fromCell.title = tx.from_address || '';
    fromCell.textContent = tx.from_address ? tx.from_address.slice(0, 12) + '...' : '';
    row.appendChild(fromCell);

    // To
    const toCell = document.createElement('td');
    toCell.title = tx.to_address || '';
    toCell.textContent = tx.to_address ? tx.to_address.slice(0, 12) + '...' : '';
    row.appendChild(toCell);

    // TXID (first 12 chars)
    const txidCell = document.createElement('td');
    const txidLink = document.createElement('a');
    txidLink.href = tx.url_tx || '#';
    txidLink.target = '_blank';
    txidLink.textContent = tx.txid ? tx.txid.slice(0, 12) + '...' : '';
    txidCell.appendChild(txidLink);
    row.appendChild(txidCell);

    // Tag
    const tagCell = document.createElement('td');
    tagCell.textContent = tx.tag_to || tx.tag_from || '';
    row.appendChild(tagCell);

    // Save button
    const saveCell = document.createElement('td');
    const saveBtn = document.createElement('button');
    saveBtn.textContent = '\u{1F4BE}';
    saveBtn.title = 'Save transaction';
    saveBtn.className = 'save-tx-btn';
    saveBtn.onclick = () => {
      document.dispatchEvent(new CustomEvent('save:tx', { detail: tx }));
    };
    saveCell.appendChild(saveBtn);
    row.appendChild(saveCell);

    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  content.appendChild(table);
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
