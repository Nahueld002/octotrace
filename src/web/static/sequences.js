/**
 * Sequences module for Octotrace.
 * Handles sequence management UI, modal display, and graph highlighting.
 * This module owns ALL sequence-related CustomEvent listeners and DOM manipulation.
 */

// Module state
const SequencesModule = {
  sequences: [],
  currentSequence: null,
};

/**
 * Initialize sequences module
 */
function initSequences() {
  // Fetch sequences on load
  fetchSequences();
  
  // Add toolbar button
  addToolbarButton();
  
  // Listen for custom events
  document.addEventListener('sequences:loaded', handleSequencesLoaded);
  document.addEventListener('sequences:changed', handleSequencesChanged);
  document.addEventListener('sequences:highlight', handleSequenceHighlight);
  document.addEventListener('sequences:clear-highlight', handleClearHighlight);
}

/**
 * Add sequences button to toolbar
 */
function addToolbarButton() {
  const inputBar = document.getElementById('input-bar');
  if (!inputBar) return;
  
  const sequencesBtn = document.createElement('button');
  sequencesBtn.id = 'sequences-btn';
  sequencesBtn.textContent = '🔗 Sequences';
  sequencesBtn.title = 'Manage transaction sequences';
  sequencesBtn.onclick = showSequencesModal;
  
  // Insert before the case toggle button
  const caseToggleBtn = document.getElementById('case-toggle-btn');
  if (caseToggleBtn) {
    inputBar.insertBefore(sequencesBtn, caseToggleBtn);
  } else {
    inputBar.appendChild(sequencesBtn);
  }
}

/**
 * Fetch all sequences from API
 */
function fetchSequences() {
  fetch('/api/sequences')
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(sequences => {
      SequencesModule.sequences = sequences;
      document.dispatchEvent(new CustomEvent('sequences:loaded', {
        detail: { sequences }
      }));
    })
    .catch(error => {
      console.error('Error fetching sequences:', error);
      alert('Error loading sequences: ' + error.message);
    });
}

/**
 * Handle sequences loaded event
 */
function handleSequencesLoaded(event) {
  SequencesModule.sequences = event.detail.sequences;
}

/**
 * Handle sequences changed event - refetch sequences
 */
function handleSequencesChanged() {
  fetchSequences();
  
  // Also re-apply highlighting if a sequence is currently selected
  if (SequencesModule.currentSequence) {
    highlightSequence(SequencesModule.currentSequence);
  }
}

/**
 * Handle sequence highlight event
 */
function handleSequenceHighlight(event) {
  const sequenceName = event.detail.sequence_name;
  SequencesModule.currentSequence = sequenceName;
  highlightSequence(sequenceName);
}

/**
 * Handle clear highlight event
 */
function handleClearHighlight() {
  SequencesModule.currentSequence = null;
  clearHighlighting();
}

/**
 * Show sequences modal
 */
function showSequencesModal() {
  // Create modal if it doesn't exist
  let modal = document.getElementById('sequences-modal');
  if (!modal) {
    modal = createSequencesModal();
    document.body.appendChild(modal);
  }
  
  // Update modal content
  updateSequencesModal();
  
  // Show modal
  modal.classList.add('open');
}

/**
 * Create sequences modal element
 */
function createSequencesModal() {
  const modal = document.createElement('div');
  modal.id = 'sequences-modal';
  modal.className = 'sequences-modal';
  
  modal.innerHTML = `
    <div class="sequences-modal-content">
      <div class="sequences-modal-header">
        <h2>Transaction Sequences</h2>
        <button class="sequences-modal-close" onclick="document.getElementById('sequences-modal').classList.remove('open')">×</button>
      </div>
      <div class="sequences-modal-body">
        <div class="sequences-actions">
          <button id="create-sequence-btn" class="sequences-btn-primary">Create New Sequence</button>
        </div>
        <div id="sequences-list" class="sequences-list">
          <!-- Sequences will be populated here -->
        </div>
      </div>
    </div>
  `;
  
  // Add event listener for create button
  modal.addEventListener('click', (e) => {
    if (e.target.id === 'create-sequence-btn') {
      showCreateSequenceForm();
    }
  });
  
  return modal;
}

/**
 * Update sequences modal content
 */
function updateSequencesModal() {
  const listContainer = document.getElementById('sequences-list');
  if (!listContainer) return;
  
  if (SequencesModule.sequences.length === 0) {
    listContainer.innerHTML = '<p class="sequences-empty">No sequences created yet.</p>';
    return;
  }
  
  // Sort by created_at descending
  const sortedSequences = [...SequencesModule.sequences].sort((a, b) => 
    new Date(b.created_at) - new Date(a.created_at)
  );
  
  listContainer.innerHTML = sortedSequences.map(sequence => `
    <div class="sequence-card" data-sequence-id="${sequence.id}">
      <div class="sequence-card-header">
        <h3>${sequence.name}</h3>
        <div class="sequence-card-actions">
          <button class="sequence-select-btn" data-sequence-id="${sequence.id}" data-sequence-name="${sequence.name}">Select</button>
          <button class="sequence-delete-btn" data-sequence-id="${sequence.id}">Delete</button>
        </div>
      </div>
      <div class="sequence-card-body">
        <p class="sequence-description">${sequence.description || 'No description'}</p>
        <div class="sequence-meta">
          <span class="sequence-jumps">Jumps: ${sequence.jump_count}</span>
          <span class="sequence-date">Created: ${new Date(sequence.created_at).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  `).join('');
  
  // Add event listeners for select and delete buttons
  listContainer.querySelectorAll('.sequence-select-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const sequenceId = e.target.dataset.sequenceId;
      const sequenceName = e.target.dataset.sequenceName;
      selectSequence(sequenceId, sequenceName);
    });
  });
  
  listContainer.querySelectorAll('.sequence-delete-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const sequenceId = e.target.dataset.sequenceId;
      deleteSequence(sequenceId);
    });
  });
}

/**
 * Show create sequence form
 */
function showCreateSequenceForm() {
  const modalBody = document.querySelector('.sequences-modal-body');
  if (!modalBody) return;
  
  modalBody.innerHTML = `
    <h3>Create New Sequence</h3>
    <form id="create-sequence-form" class="sequence-form">
      <div class="form-group">
        <label for="sequence-name">Name *</label>
        <input type="text" id="sequence-name" required maxlength="128">
      </div>
      <div class="form-group">
        <label for="sequence-description">Description</label>
        <textarea id="sequence-description" rows="3"></textarea>
      </div>
      <div class="form-actions">
        <button type="button" class="sequences-btn-secondary" onclick="document.getElementById('sequences-modal').classList.remove('open')">Cancel</button>
        <button type="submit" class="sequences-btn-primary">Create Sequence</button>
      </div>
    </form>
  `;
  
  // Add form submit handler
  const form = document.getElementById('create-sequence-form');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      createSequence();
    });
  }
}

/**
 * Create a new sequence
 */
function createSequence() {
  const nameInput = document.getElementById('sequence-name');
  const descInput = document.getElementById('sequence-description');
  
  if (!nameInput || !nameInput.value.trim()) {
    alert('Please enter a sequence name');
    return;
  }
  
  const payload = {
    name: nameInput.value.trim(),
    description: descInput ? descInput.value.trim() : ''
  };
  
  fetch('/api/sequences', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (!response.ok) {
      return response.json().then(err => {
        throw new Error(err.detail || `HTTP ${response.status}`);
      });
    }
    return response.json();
  })
  .then(() => {
    // Close modal and refresh sequences
    document.getElementById('sequences-modal').classList.remove('open');
    fetchSequences();
    alert('✅ Sequence created successfully');
  })
  .catch(error => {
    console.error('Error creating sequence:', error);
    alert('Error creating sequence: ' + error.message);
  });
}

/**
 * Select a sequence for highlighting
 */
function selectSequence(sequenceId, sequenceName) {
  document.dispatchEvent(new CustomEvent('sequences:highlight', {
    detail: { sequence_name: sequenceName }
  }));
  
  // Close modal
  document.getElementById('sequences-modal').classList.remove('open');
}

/**
 * Delete a sequence
 */
function deleteSequence(sequenceId) {
  if (!confirm('Are you sure you want to delete this sequence? This cannot be undone.')) {
    return;
  }
  
  fetch(`/api/sequences/${sequenceId}`, {
    method: 'DELETE'
  })
  .then(response => {
    if (!response.ok) {
      return response.json().then(err => {
        throw new Error(err.detail || `HTTP ${response.status}`);
      });
    }
    return response.json();
  })
  .then(() => {
    // Refresh sequences
    fetchSequences();
    alert('✅ Sequence deleted successfully');
    
    // If this was the currently highlighted sequence, clear highlighting
    if (SequencesModule.currentSequence) {
      document.dispatchEvent(new CustomEvent('sequences:clear-highlight'));
    }
  })
  .catch(error => {
    console.error('Error deleting sequence:', error);
    alert('Error deleting sequence: ' + error.message);
  });
}

/**
 * Highlight edges belonging to a sequence
 */
function highlightSequence(sequenceName) {
  // First, get the sequence details to find all its jumps
  const sequence = SequencesModule.sequences.find(s => s.name === sequenceName);
  if (!sequence) return;
  
  fetch(`/api/sequences/${sequence.id}`)
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(sequenceData => {
      // Get all transaction IDs in this sequence
      const txids = sequenceData.jumps.map(jump => jump.txid);
      
      // Highlight edges in the graph
      highlightEdges(txids);
    })
    .catch(error => {
      console.error('Error fetching sequence details:', error);
      alert('Error highlighting sequence: ' + error.message);
    });
}

/**
 * Highlight specific edges in the graph
 */
function highlightEdges(txids) {
  // Use the graph module function to highlight edges
  if (window.GraphModule && window.GraphModule.highlightEdgesByTxids) {
    window.GraphModule.highlightEdgesByTxids(txids);
  }
}

/**
 * Clear all highlighting and restore normal opacity
 */
function clearHighlighting() {
  // Use the graph module function to clear highlighting
  if (window.GraphModule && window.GraphModule.clearSequenceHighlighting) {
    window.GraphModule.clearSequenceHighlighting();
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initSequences);

// Export for global access
window.SequencesModule = {
  fetchSequences,
  highlightSequence,
  clearHighlighting
};