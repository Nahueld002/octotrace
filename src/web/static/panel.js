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
    evidenceLink.href = `https://${data.chain === 'ETH' ? 'etherscan.io/tx/' + data.id : 'tronscan.org/#/transaction/' + data.id}`;
    evidenceLink.textContent = 'View on Blockchain Explorer';
    evidenceLink.target = '_blank';
    
    const linkContainer = document.createElement('div');
    linkContainer.className = 'panel-field';
    linkContainer.appendChild(evidenceLink);
    content.appendChild(linkContainer);
  } else {
    // Node data — show tag or label if tag is null
    const nodeFields = [
      { label: 'Address', value: data.id },
      { label: 'Tag', value: data.tag || data.label || 'None' },
      { label: 'Chain', value: data.chain || '—' }
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
    
    // Etiqueta manual editable
    const labelDiv = document.createElement('div');
    labelDiv.className = 'panel-field';
    const labelLabel = document.createElement('label');
    labelLabel.textContent = 'Label';
    const labelInput = document.createElement('input');
    labelInput.type = 'text';
    labelInput.className = 'panel-label-input';
    labelInput.placeholder = 'Add manual label...';
    labelInput.value = data.label_manual || '';
    const labelBtn = document.createElement('button');
    labelBtn.textContent = '\u{1F4BE}';
    labelBtn.className = 'panel-label-save-btn';
    labelBtn.onclick = () => {
      document.dispatchEvent(new CustomEvent('address:label', {
        detail: {
          address: data.id,
          chain: data.chain,
          label_manual: labelInput.value.trim()
        }
      }));
    };
    labelDiv.appendChild(labelLabel);
    labelDiv.appendChild(labelInput);
    labelDiv.appendChild(labelBtn);
    content.appendChild(labelDiv);

    // Add evidence link
    const evidenceLink = document.createElement('a');
    evidenceLink.href = `https://${data.chain === 'ETH' ? 'etherscan.io/address/' + data.id : 'tronscan.org/#/address/' + data.id}`;
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
    if (tx.saved) {
      row.classList.add('tx-saved');
    }

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
    fromCell.textContent = tx.from_address || '';
    row.appendChild(fromCell);

    // To
    const toCell = document.createElement('td');
    toCell.title = tx.to_address || '';
    toCell.textContent = tx.to_address || '';
    row.appendChild(toCell);

    // TXID
    const txidCell = document.createElement('td');
    const txidLink = document.createElement('a');
    txidLink.href = tx.url_tx || '#';
    txidLink.target = '_blank';
    txidLink.textContent = tx.txid || '';
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

/**
 * Show edge data in panel (no fetch needed — data comes from graph)
 * @param {Object} edgeData - Edge data from graph event
 */
PanelModule.showEdge = function(edgeData) {
  const panel = document.getElementById('side-panel');
  const content = document.getElementById('panel-content');
  content.innerHTML = '';

  const chain = edgeData.chain;
  const txUrl = chain === 'ETH'
    ? `https://etherscan.io/tx/${edgeData.id}`
    : `https://tronscan.org/#/transaction/${edgeData.id}`;

  const fields = [
    { label: 'Transaction ID', value: edgeData.id },
    { label: 'Amount',         value: edgeData.amount },
    { label: 'Date',           value: edgeData.datetime },
    { label: 'Chain',          value: chain },
    { label: 'From',           value: edgeData.source },
    { label: 'To',             value: edgeData.target },
  ];

  fields.forEach(f => {
    const div = document.createElement('div');
    div.className = 'panel-field';
    div.innerHTML = `<label>${f.label}</label><div>${f.value || '—'}</div>`;
    content.appendChild(div);
  });

  const linkDiv = document.createElement('div');
  linkDiv.className = 'panel-field';
  linkDiv.innerHTML = `<a href="${txUrl}" target="_blank">View on Blockchain Explorer</a>`;
  content.appendChild(linkDiv);

  // Save button (create dynamically — no static #panel-save in HTML)
  const saveBtn = document.createElement('button');
  saveBtn.id = 'panel-save';
  saveBtn.textContent = '\u{1F4BE} Save transaction';
  saveBtn.onclick = () => {
    document.dispatchEvent(new CustomEvent('save:tx', {
      detail: {
        txid: edgeData.id,
        chain: edgeData.chain,
        from_address: edgeData.source,
        to_address: edgeData.target,
        amount: edgeData.amount,
        datetime_utc: edgeData.datetime,
        token_symbol: 'USDT',
        block_number: null,
        confirmations: null,
        tag_from: null,
        tag_to: null,
        url_tx: edgeData.chain === 'ETH'
          ? `https://etherscan.io/tx/${edgeData.id}`
          : `https://tronscan.org/#/transaction/${edgeData.id}`,
        raw_json: '{}'
      }
    }));
  };
  content.appendChild(saveBtn);

  // Close button
  document.getElementById('panel-close').onclick = () => PanelModule.hide();

  panel.classList.add('open');
};

/**
 * Show loading state in panel
 * @param {Object} nodeData - Node data (unused, for API consistency)
 */
PanelModule.showLoading = function(nodeData) {
  const panel = document.getElementById('side-panel');
  const content = document.getElementById('panel-content');
  content.innerHTML = '<div class="panel-loading">Cargando transacciones...</div>';
  panel.classList.add('open');
};

/**
 * Show error message in panel
 * @param {string} msg - Error message to display
 */
PanelModule.showError = function(msg) {
  document.getElementById('panel-content').innerHTML =
    `<div class="panel-error">Error: ${msg}</div>`;
};

// Panel resize via drag handle — replaces CSS resize/direction rtl
document.addEventListener('DOMContentLoaded', () => {
  const handle = document.getElementById('panel-resize-handle');
  if (!handle) return;

  handle.addEventListener('mousedown', () => {
    const onMove = (e) => {
      const newWidth = window.innerWidth - e.clientX;
      const panel = document.getElementById('side-panel');
      panel.style.width = Math.max(320, Math.min(newWidth, window.innerWidth * 0.8)) + 'px';
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', () => {
      document.removeEventListener('mousemove', onMove);
    }, { once: true });
  });
});
