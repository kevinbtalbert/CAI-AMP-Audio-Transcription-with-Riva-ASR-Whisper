// Healthcare Call Analytics - Frontend Application

let currentFile = null;
let currentResult = null;
let currentFolderPath = "";

// Version history
let currentVersions = [];
let currentVersionIndex = 0;

// Simple notification functions
function showSuccess(message) {
    console.log('✓ Success:', message);
    // Could be enhanced with a toast notification later
}

function showError(message) {
    console.error('✗ Error:', message);
    alert('Error: ' + message);
}

// ===== SOLR DASHBOARD FUNCTIONS =====

let currentView = 'files'; // 'files' or 'dashboard'
let currentPage = 0;
let pageSize = 20;
let totalResults = 0;

// Toggle between files view and dashboard view
function toggleView() {
    const sidebar = document.querySelector('.sidebar');
    const mainPanel = document.querySelector('.main-panel');
    const dashboardPanel = document.getElementById('dashboardPanel');
    const toggleBtn = document.getElementById('dashboardToggle');
    
    if (currentView === 'files') {
        // Switch to dashboard
        sidebar.style.display = 'none';
        mainPanel.style.display = 'none';
        dashboardPanel.style.display = 'block';
        toggleBtn.innerHTML = '<i class="fas fa-folder"></i> Files';
        currentView = 'dashboard';
        loadDashboard();
    } else {
        // Switch to files
        sidebar.style.display = 'block';
        mainPanel.style.display = 'block';
        dashboardPanel.style.display = 'none';
        toggleBtn.innerHTML = '<i class="fas fa-chart-bar"></i> Dashboard';
        currentView = 'files';
    }
}

// Check if Solr is enabled and show/hide dashboard button
async function checkSolrStatus() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        
        const dashboardToggle = document.getElementById('dashboardToggle');
        if (settings.solr_enabled) {
            dashboardToggle.style.display = 'inline-block';
        } else {
            dashboardToggle.style.display = 'none';
        }
    } catch (error) {
        console.error('Error checking Solr status:', error);
    }
}

// Load dashboard data
async function loadDashboard() {
    try {
        // Load all dashboard data in parallel for faster loading
        await Promise.all([
            loadDashboardStats(),
            loadCategoricalInsights(),
            searchCalls()
        ]);
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showError('Failed to load dashboard data');
    }
}

// Load categorical insights (medications, conditions, symptoms)
async function loadCategoricalInsights() {
    try {
        // Fetch and parse all facets in parallel
        const [medications, conditions, symptoms] = await Promise.all([
            fetch('/api/solr/categorical-facets/medications').then(r => r.json()),
            fetch('/api/solr/categorical-facets/conditions').then(r => r.json()),
            fetch('/api/solr/categorical-facets/symptoms').then(r => r.json())
        ]);
        
        displayCategoryInsights('topMedications', 'medicationsCount', medications, 'medication');
        displayCategoryInsights('topConditions', 'conditionsCount', conditions, 'condition');
        displayCategoryInsights('topSymptoms', 'symptomsCount', symptoms, 'symptom');
        
    } catch (error) {
        console.error('Error loading categorical insights:', error);
        document.getElementById('topMedications').innerHTML = '<div class="loading-text">No data available</div>';
        document.getElementById('topConditions').innerHTML = '<div class="loading-text">No data available</div>';
        document.getElementById('topSymptoms').innerHTML = '<div class="loading-text">No data available</div>';
    }
}

// Display category insights (medications, conditions, symptoms)
function displayCategoryInsights(elementId, countElementId, data, categoryType) {
    const container = document.getElementById(elementId);
    const countElement = document.getElementById(countElementId);
    
    if (!data.success || !data.facets || Object.keys(data.facets).length === 0) {
        container.innerHTML = '<div class="loading-text">No data available yet. Analyze and index some calls first!</div>';
        countElement.textContent = '0';
        return;
    }
    
    // Convert facets object to array and sort by count
    const items = Object.entries(data.facets)
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10);  // Top 10
    
    countElement.textContent = items.length;
    
    if (items.length === 0) {
        container.innerHTML = '<div class="loading-text">No data available</div>';
        return;
    }
    
    container.innerHTML = items.map(item => `
        <div class="insight-item" onclick="filterByCategory('${categoryType}', '${escapeHtml(item.name)}')">
            <span class="insight-name">${escapeHtml(item.name)}</span>
            <span class="insight-badge">${item.count} call${item.count > 1 ? 's' : ''}</span>
        </div>
    `).join('');
}

// Filter by category (when clicking on an insight)
async function filterByCategory(categoryType, value) {
    console.log(`Filtering by ${categoryType}:`, value);
    
    // Set search query
    document.getElementById('searchQuery').value = value;
    
    // If it's clinical data, set call type filter
    if (categoryType === 'medication' || categoryType === 'condition' || categoryType === 'symptom') {
        document.getElementById('filterCallType').value = 'clinical';
    }
    
    // Execute search
    await searchCalls();
}

// Load dashboard statistics
async function loadDashboardStats() {
    try {
        const response = await fetch('/api/solr/stats');
        if (!response.ok) throw new Error('Failed to fetch stats');
        
        const stats = await response.json();
        
        // Update stat cards
        document.getElementById('totalCalls').textContent = stats.total_calls || 0;
        document.getElementById('highUrgency').textContent = stats.urgency_distribution?.high || 0;
        document.getElementById('clinicalCalls').textContent = stats.call_type_distribution?.clinical || 0;
        document.getElementById('positiveSentiment').textContent = stats.sentiment_distribution?.positive || 0;
        
    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('totalCalls').textContent = 'Error';
        document.getElementById('highUrgency').textContent = 'Error';
        document.getElementById('clinicalCalls').textContent = 'Error';
        document.getElementById('positiveSentiment').textContent = 'Error';
    }
}

// Search calls in Solr
async function searchCalls() {
    try {
        const query = document.getElementById('searchQuery')?.value || '*:*';
        const urgencyFilter = document.getElementById('filterUrgency')?.value;
        const typeFilter = document.getElementById('filterCallType')?.value;
        const sentimentFilter = document.getElementById('filterSentiment')?.value;
        
        // Build query - search across multiple fields
        let q;
        if (!query || query === '*:*') {
            q = '*:*';
        } else {
            // Search in transcription, medications, conditions, and symptoms
            const escapedQuery = query.replace(/[:"()]/g, '\\$&'); // Escape special Solr chars
            q = `(transcription:"${escapedQuery}" OR ` +
                `healthcare_insights.medications.name:"${escapedQuery}" OR ` +
                `healthcare_insights.medical_conditions.condition:"${escapedQuery}" OR ` +
                `healthcare_insights.symptoms.symptom:"${escapedQuery}" OR ` +
                `file_path:*${escapedQuery}*)`;
        }
        
        // Apply filters
        if (urgencyFilter) {
            q = `(${q}) AND healthcare_insights.urgency_level.level:${urgencyFilter}`;
        }
        if (typeFilter) {
            q = `(${q}) AND healthcare_insights.call_type:${typeFilter}`;
        }
        if (sentimentFilter) {
            q = `(${q}) AND healthcare_insights.sentiment_analysis.overall_sentiment:${sentimentFilter}`;
        }
        
        const response = await fetch(`/api/solr/query?q=${encodeURIComponent(q)}&rows=${pageSize}&start=${currentPage * pageSize}`);
        if (!response.ok) throw new Error('Search failed');
        
        const result = await response.json();
        
        totalResults = result.numFound || 0;
        displaySearchResults(result.docs, result.message);
        updatePagination();
        
        document.getElementById('resultsCount').textContent = `${totalResults} results`;
        document.getElementById('resultsTitle').textContent = query === '*:*' ? 'Recent Calls' : 'Search Results';
        
    } catch (error) {
        console.error('Error searching calls:', error);
        document.getElementById('resultsTableBody').innerHTML = 
            '<tr><td colspan="9" class="text-center"><i class="fas fa-exclamation-triangle"></i> Error loading results. Make sure Solr is configured correctly.</td></tr>';
    }
}

// Display search results in table
function displaySearchResults(docs, message = null) {
    const tbody = document.getElementById('resultsTableBody');
    
    if (!docs || docs.length === 0) {
        const emptyMessage = message || 'No results found. Analyze some calls and push them to Solr first!';
        tbody.innerHTML = `<tr><td colspan="9" class="text-center">
            <i class="fas fa-info-circle"></i> ${emptyMessage}
        </td></tr>`;
        return;
    }
    
    tbody.innerHTML = docs.map(doc => {
        // Solr returns ALL fields as arrays, even single values
        // Helper function to safely get first value from array
        const getFirst = (field) => {
            const val = doc[field];
            return Array.isArray(val) ? val[0] : val;
        };
        
        const urgency = getFirst('healthcare_insights.urgency_level.level') || 'unknown';
        const callType = getFirst('healthcare_insights.call_type') || 'general';
        const sentiment = getFirst('healthcare_insights.sentiment_analysis.overall_sentiment') || 'neutral';
        const filePath = getFirst('file_path') || 'Unknown';
        const timestamp = getFirst('timestamp');
        const date = timestamp ? new Date(timestamp).toLocaleDateString() : '-';
        
        // Get arrays (these ARE arrays, so keep them as is)
        const medications = doc['healthcare_insights.medications.name'] || [];
        const conditions = doc['healthcare_insights.medical_conditions.condition'] || [];
        const symptoms = doc['healthcare_insights.symptoms.symptom'] || [];
        
        // Format medications
        const medicationTags = medications.slice(0, 2).map(med => 
            `<span class="medication-tag">${med}</span>`
        ).join('');
        const medMore = medications.length > 2 ? `<span class="medication-tag">+${medications.length - 2}</span>` : '';
        
        // Format conditions
        const conditionsList = conditions.slice(0, 2).join(', ');
        const condMore = conditions.length > 2 ? ` (+${conditions.length - 2})` : '';
        
        // Format symptoms
        const symptomsList = symptoms.slice(0, 2).join(', ');
        const sympMore = symptoms.length > 2 ? ` (+${symptoms.length - 2})` : '';
        
        return `
            <tr>
                <td><strong>${filePath}</strong></td>
                <td>${date}</td>
                <td><span class="type-badge type-${callType}">${callType}</span></td>
                <td><span class="urgency-badge urgency-${urgency}">${urgency}</span></td>
                <td><i class="fas fa-circle sentiment-${sentiment}"></i> ${sentiment}</td>
                <td>${conditionsList || '-'}${condMore}</td>
                <td>${medicationTags}${medMore || (medications.length === 0 ? '-' : '')}</td>
                <td>${symptomsList || '-'}${sympMore}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="viewCallDetails('${doc.id}')">
                        <i class="fas fa-eye"></i> View
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Update pagination controls
function updatePagination() {
    const pagination = document.getElementById('resultsPagination');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    const pageInfo = document.getElementById('pageInfo');
    
    const totalPages = Math.ceil(totalResults / pageSize);
    
    if (totalPages <= 1) {
        pagination.style.display = 'none';
        return;
    }
    
    pagination.style.display = 'flex';
    prevBtn.disabled = currentPage === 0;
    nextBtn.disabled = currentPage >= totalPages - 1;
    pageInfo.textContent = `Page ${currentPage + 1} of ${totalPages}`;
}

// Navigate to previous page
function previousPage() {
    if (currentPage > 0) {
        currentPage--;
        searchCalls();
    }
}

// Navigate to next page
function nextPage() {
    const totalPages = Math.ceil(totalResults / pageSize);
    if (currentPage < totalPages - 1) {
        currentPage++;
        searchCalls();
    }
}

// Clear search filters
function clearFilters() {
    document.getElementById('searchQuery').value = '';
    document.getElementById('filterUrgency').value = '';
    document.getElementById('filterCallType').value = '';
    document.getElementById('filterSentiment').value = '';
    currentPage = 0;
    searchCalls();
}

// View call details (placeholder - could open modal with full details)
async function viewCallDetails(docId) {
    try {
        // Query Solr for the specific document
        const response = await fetch(`/api/solr/query?q=id:"${encodeURIComponent(docId)}"&rows=1`);
        const data = await response.json();
        
        if (!data.success || !data.docs || data.docs.length === 0) {
            showError('Could not find call details in Solr');
            return;
        }
        
        const doc = data.docs[0];
        
        // Create a modal to display the full document
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'flex';
        
        const getFirst = (field) => {
            const val = doc[field];
            return Array.isArray(val) ? val[0] : val;
        };
        
        const fileName = getFirst('file_path') || 'Unknown File';
        
        const docJson = JSON.stringify(doc, null, 2);
        
        modal.innerHTML = `
            <div class="modal-content modal-large" style="max-width: 1200px; width: 95%; max-height: 90vh;">
                <div class="modal-header">
                    <h3><i class="fas fa-file-medical"></i> Call Details: ${escapeHtml(fileName)}</h3>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">×</button>
                </div>
                <div class="modal-body" style="padding: 1.5rem;">
                    <h4 style="margin-top: 0; margin-bottom: 1rem; color: #333;">Solr Document Record</h4>
                    <div style="max-height: 70vh; overflow-y: auto; margin-bottom: 1.5rem;">
                        <pre id="solrDocJson" style="background: #1e1e1e; color: #d4d4d4; padding: 1.5rem; border-radius: 6px; overflow-x: auto; font-size: 0.875rem; line-height: 1.5; margin: 0; font-family: 'Courier New', monospace; white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(docJson)}</pre>
                    </div>
                    <div class="modal-actions" style="display: flex; gap: 0.75rem; justify-content: flex-end; border-top: 1px solid #e0e0e0; padding-top: 1rem; margin: 0;">
                        <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                            <i class="fas fa-times"></i> Close
                        </button>
                        <button class="btn btn-primary" id="copyJsonBtn" onclick="copyJsonToClipboard()">
                            <i class="fas fa-copy"></i> Copy JSON
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Store the JSON for copying
        window.tempDocJson = docJson;
        
        document.body.appendChild(modal);
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
                delete window.tempDocJson;
            }
        });
        
    } catch (error) {
        console.error('Error viewing call details:', error);
        showError('Failed to load call details: ' + error.message);
    }
}

// Helper function to copy JSON to clipboard
function copyJsonToClipboard() {
    if (window.tempDocJson) {
        navigator.clipboard.writeText(window.tempDocJson).then(() => {
            const btn = document.getElementById('copyJsonBtn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
            btn.classList.add('btn-success');
            btn.classList.remove('btn-primary');
            
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.classList.remove('btn-success');
                btn.classList.add('btn-primary');
            }, 2000);
        }).catch(err => {
            showError('Failed to copy: ' + err.message);
        });
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Content Loaded - Initializing app...');
    try {
        console.log('Calling checkSetup...');
        checkSetup();  // Check if first-time setup needed
        
        console.log('Calling loadFiles...');
        loadFiles();
        
        console.log('Calling checkHealth...');
        checkHealth();
        
        console.log('Calling setupDragAndDrop...');
        setupDragAndDrop();
        
        console.log('Checking Solr status...');
        checkSolrStatus();  // Show/hide dashboard button based on Solr config
        
        console.log('App initialization complete');
    } catch (error) {
        console.error('Error during app initialization:', error);
    }
});

// Check if initial setup is needed
async function checkSetup() {
    try {
        const response = await fetch('/api/setup-check');
        const setup = await response.json();
        
        if (setup.needs_setup) {
            // Show setup modal
            showSetupModal(setup.missing_items);
        }
    } catch (error) {
        console.error('Error checking setup:', error);
        // Don't block the app if setup check fails
    }
}

function showSetupModal(missingItems) {
    const modal = document.getElementById('setupModal');
    
    // Update checklist if we have specific missing items
    if (missingItems && missingItems.length > 0) {
        const checklist = document.getElementById('setupChecklistItems');
        checklist.innerHTML = missingItems.map(item => 
            `<li><i class="fas fa-circle"></i> ${item}</li>`
        ).join('');
    }
    
    modal.style.display = 'flex';
}

function closeSetupAndOpenSettings() {
    // Close setup modal
    document.getElementById('setupModal').style.display = 'none';
    
    // Open settings modal
    showSettingsModal();
}

function dismissSetup() {
    // Just close the setup modal
    document.getElementById('setupModal').style.display = 'none';
    
    // Show a helpful toast/message
    console.log('Setup dismissed. You can access Settings from the header anytime.');
}

// Check API health
// Health checking with detailed status
async function checkHealth() {
    const refreshIcon = document.getElementById('refreshIcon');
    if (refreshIcon) refreshIcon.classList.add('fa-spin');
    
    try {
        const response = await fetch('/api/health/status');
        const health = await response.json();
        
        updateStatusIndicator('riva', health.riva_asr);
        updateStatusIndicator('nemotron', health.nemotron);
        
    } catch (error) {
        console.error('Health check failed:', error);
        showError('Failed to check model status');
    } finally {
        if (refreshIcon) refreshIcon.classList.remove('fa-spin');
    }
}

function updateStatusIndicator(service, healthData) {
    const statusIcon = document.getElementById(`${service}Status`);
    const statusText = document.getElementById(`${service}StatusText`);
    const lastCheck = document.getElementById(`${service}LastCheck`);
    
    if (!statusIcon || !statusText) return;
    
    // Update icon color based on status
    statusIcon.className = 'fas fa-circle';
    
    if (healthData.status === 'online') {
        statusIcon.style.color = '#4caf50';  // green
        statusText.textContent = 'Online';
        statusText.title = '';
    } else if (healthData.status === 'offline') {
        statusIcon.style.color = '#f44336';  // red
        statusText.textContent = 'Offline';
        statusText.title = healthData.error || 'Service is offline';
    } else if (healthData.status === 'error') {
        statusIcon.style.color = '#ff9800';  // orange
        statusText.textContent = 'Error';
        statusText.title = healthData.error || 'Service error';
    } else if (healthData.status === 'disabled') {
        statusIcon.style.color = '#9e9e9e';  // gray
        statusText.textContent = 'Disabled';
        statusText.title = 'Service is disabled';
    } else if (healthData.status === 'not_configured') {
        statusIcon.style.color = '#ff9800';  // orange
        statusText.textContent = 'Not Configured';
        statusText.title = healthData.error || 'Service not configured';
    } else {
        statusIcon.style.color = '#9e9e9e';
        statusText.textContent = 'Unknown';
        statusText.title = healthData.error || 'Status unknown';
    }
    
    // Update last check time
    if (lastCheck && healthData.timestamp) {
        const checkTime = new Date(healthData.timestamp);
        lastCheck.textContent = `(checked ${formatTimeAgo(checkTime)})`;
    }
    
    // Show error in text if present
    if (healthData.error) {
        statusText.style.cursor = 'help';
    }
}

function formatTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

async function refreshHealth() {
    await fetch('/api/health/refresh', { method: 'POST' });
    await checkHealth();
}

// Start health check interval
setInterval(checkHealth, 30000);  // Check every 30 seconds

// Version History Functions
async function loadVersions(filePath) {
    try {
        const response = await fetch(`/api/result/${encodeURIComponent(filePath)}/versions`);
        const data = await response.json();
        
        currentVersions = data.versions;
        
        if (currentVersions.length > 0) {
            currentVersionIndex = 0;  // Show most recent
            document.getElementById('versionNavigator').style.display = 'flex';
            updateVersionDisplay();
            await loadVersion(currentVersions[0].version);
        } else {
            document.getElementById('versionNavigator').style.display = 'none';
        }
    } catch (error) {
        console.log('No versions found or error loading versions');
        document.getElementById('versionNavigator').style.display = 'none';
    }
}

function updateVersionDisplay() {
    const currentVersion = currentVersions[currentVersionIndex];
    document.getElementById('currentVersion').textContent = 
        `Version ${currentVersion.version}`;
    document.getElementById('versionCount').textContent = 
        `(${currentVersionIndex + 1} of ${currentVersions.length})`;
    
    const versionDate = new Date(currentVersion.timestamp);
    document.getElementById('versionDate').textContent = 
        versionDate.toLocaleString();
    
    // Enable/disable navigation buttons
    document.getElementById('prevVersionBtn').disabled = currentVersionIndex === 0;
    document.getElementById('nextVersionBtn').disabled = 
        currentVersionIndex === currentVersions.length - 1;
}

async function loadVersion(version) {
    try {
        const response = await fetch(
            `/api/result/${encodeURIComponent(currentFile.path)}/version/${version}`
        );
        const result = await response.json();
        displayResult(result);
    } catch (error) {
        showError(`Failed to load version ${version}`);
    }
}

function previousVersion() {
    if (currentVersionIndex > 0) {
        currentVersionIndex--;
        updateVersionDisplay();
        loadVersion(currentVersions[currentVersionIndex].version);
    }
}

function nextVersion() {
    if (currentVersionIndex < currentVersions.length - 1) {
        currentVersionIndex++;
        updateVersionDisplay();
        loadVersion(currentVersions[currentVersionIndex].version);
    }
}

// Load files from server
async function loadFiles(path = "") {
    console.log('loadFiles called with path:', path);
    currentFolderPath = path;
    const browser = document.getElementById('fileBrowser');
    
    if (!browser) {
        console.error('fileBrowser element not found!');
        return;
    }
    
    // Show loading state immediately
    browser.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading files...</div>';
    
    try {
        console.log('Fetching files from API...');
        // Add cache-busting timestamp to force refresh
        const timestamp = new Date().getTime();
        const response = await fetch(`/api/files/browse?path=${encodeURIComponent(path)}&_t=${timestamp}`);
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Received data:', data);
        
        if (data.error) {
            browser.innerHTML = `<div class="loading"><i class="fas fa-exclamation-circle"></i> ${data.error}</div>`;
            return;
        }
        
        browser.innerHTML = '';
        
        // Add back button if not in root
        if (path) {
            const backButton = createBackButton(path);
            browser.appendChild(backButton);
        }
        
        // Add folders first
        const folders = data.items.filter(item => item.type === 'directory');
        const files = data.items.filter(item => item.type === 'file');
        
        console.log('Rendering', folders.length, 'folders and', files.length, 'files');
        
        folders.forEach(folder => {
            browser.appendChild(createFolderElement(folder));
        });
        
        files.forEach(file => {
            browser.appendChild(createFileElement(file));
        });
        
        if (data.items.length === 0) {
            browser.innerHTML = '<div class="loading">No files yet. Upload audio files to begin.</div>';
        }
        
        console.log('loadFiles completed successfully');
        
    } catch (error) {
        console.error('Error loading files:', error);
        browser.innerHTML = `<div class="loading"><i class="fas fa-exclamation-circle"></i> Error loading files: ${error.message}</div>`;
    }
}

// Create back button
function createBackButton(currentPath) {
    const parts = currentPath.split('/');
    parts.pop();
    const parentPath = parts.join('/');
    
    const div = document.createElement('div');
    div.className = 'folder-item';
    div.innerHTML = `
        <i class="fas fa-arrow-left"></i>
        <div class="file-info">
            <div class="file-name">Back</div>
        </div>
    `;
    div.onclick = () => loadFiles(parentPath);
    return div;
}

// Create folder element
function createFolderElement(folder) {
    const div = document.createElement('div');
    div.className = 'folder-item';
    div.innerHTML = `
        <i class="fas fa-folder"></i>
        <div class="file-info">
            <div class="file-name">${escapeHtml(folder.name)}</div>
            <div class="file-meta">${new Date(folder.modified).toLocaleDateString()}</div>
        </div>
    `;
    div.onclick = () => loadFiles(folder.path);
    return div;
}

// Create file element
function createFileElement(file) {
    const div = document.createElement('div');
    div.className = 'file-item';
    div.dataset.path = file.path;
    div.innerHTML = `
        <i class="fas fa-file-audio"></i>
        <div class="file-info">
            <div class="file-name">${escapeHtml(file.name)}</div>
            <div class="file-meta">${file.size_formatted} • ${new Date(file.modified).toLocaleDateString()}</div>
        </div>
        <button class="btn-icon btn-delete" onclick="event.stopPropagation(); deleteFile('${escapeHtml(file.path)}', '${escapeHtml(file.name)}')" title="Delete file">
            <i class="fas fa-trash"></i>
        </button>
    `;
    div.onclick = () => selectFile(file);
    return div;
}

// Select file
function selectFile(file) {
    // Remove previous selection
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
    
    // Add selection
    const element = document.querySelector(`[data-path="${file.path}"]`);
    if (element) {
        element.classList.add('selected');
    }
    
    currentFile = file;
    
    // Show file details screen
    document.getElementById('welcomeScreen').classList.add('hidden');
    document.getElementById('fileDetailsScreen').classList.remove('hidden');
    
    // Update file info
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileMetadata').textContent = 
        `${file.size_formatted} • Modified: ${new Date(file.modified).toLocaleDateString()}`;
    
    // Hide previous results
    document.getElementById('analysisResults').classList.add('hidden');
    document.getElementById('processingState').classList.remove('hidden');
    document.getElementById('resultsDisplay').classList.add('hidden');
    
    // Check if we have existing results
    loadExistingResult(file.path);
}

// Load existing result if available
async function loadExistingResult(filePath) {
    try {
        const response = await fetch(`/api/result/${encodeURIComponent(filePath)}`);
        if (response.ok) {
            const result = await response.json();
            displayResult(result);
        }
    } catch (error) {
        console.log('No existing result found');
    }
}

// Analyze file
async function analyzeFile() {
    if (!currentFile) {
        showError('No file selected');
        return;
    }
    
    // Check if models are online first
    const healthResponse = await fetch('/api/health/status');
    const health = await healthResponse.json();
    
    if (health.riva_asr.status !== 'online') {
        showError(
            `Cannot analyze - Riva ASR is ${health.riva_asr.status}\n\n` +
            (health.riva_asr.error || 'Service is not available') +
            '\n\nPlease check your CDP configuration in Settings.'
        );
        return;
    }
    
    const analyzeBtn = document.getElementById('analyzeBtn');
    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
    
    // Show processing state
    document.getElementById('analysisResults').classList.remove('hidden');
    document.getElementById('processingState').classList.remove('hidden');
    document.getElementById('resultsDisplay').classList.add('hidden');
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_path: currentFile.path
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.message || error.detail || 'Analysis failed');
        }
        
        const result = await response.json();
        currentResult = result;
        
        // Display results
        displayResult(result);
        
        // Load version history
        await loadVersions(currentFile.path);
        
        showSuccess(`Analysis completed in ${result.processing_time.toFixed(2)}s`);
        
    } catch (error) {
        console.error('Error analyzing file:', error);
        showError(error.message || 'Failed to analyze file');
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<i class="fas fa-play"></i> Analyze Call';
    }
}

// Display analysis result
function displayResult(result) {
    document.getElementById('processingState').classList.add('hidden');
    document.getElementById('resultsDisplay').classList.remove('hidden');
    
    currentResult = result;
    
    // Call Type Detection
    const callType = result.healthcare_insights.call_type || 'general';
    
    // Summary
    document.getElementById('callSummary').textContent = 
        result.healthcare_insights.call_summary;
    
    // Metadata
    const duration = Math.floor(result.call_metadata.duration_seconds / 60);
    document.getElementById('callDuration').textContent = `${duration}m ${Math.floor(result.call_metadata.duration_seconds % 60)}s`;
    
    const provider = result.healthcare_insights.participants.provider_name || 
                    result.healthcare_insights.participants.provider_role || 
                    'Not identified';
    document.getElementById('providerName').textContent = provider;
    
    const confidence = (result.call_metadata.confidence_score * 100).toFixed(1);
    document.getElementById('confidence').textContent = `${confidence}%`;
    
    const sentiment = result.healthcare_insights.sentiment_analysis.overall_sentiment;
    document.getElementById('sentiment').textContent = sentiment.charAt(0).toUpperCase() + sentiment.slice(1);
    
    // Urgency badge - adapt for call type
    const urgency = result.healthcare_insights.urgency_level.level;
    const badge = document.getElementById('urgencyBadge');
    
    if (callType === 'administrative') {
        badge.textContent = 'Administrative Call';
        badge.className = 'badge info';
    } else {
        badge.textContent = `${urgency.charAt(0).toUpperCase() + urgency.slice(1)} Urgency`;
        badge.className = `badge ${urgency}`;
    }
    
    // Medical conditions
    displayList('conditionsList', result.healthcare_insights.medical_conditions, 
        item => `
            <div class="item">
                <div class="item-title">${escapeHtml(item.condition)}</div>
                <div class="item-context">${escapeHtml(item.context)}</div>
            </div>
        `);
    
    // Medications
    displayList('medicationsList', result.healthcare_insights.medications,
        item => `
            <div class="item">
                <div class="item-title">${escapeHtml(item.name)}</div>
                ${item.dosage ? `<div class="item-detail">Dosage: ${escapeHtml(item.dosage)}</div>` : ''}
                ${item.frequency ? `<div class="item-detail">Frequency: ${escapeHtml(item.frequency)}</div>` : ''}
                <div class="item-context">${escapeHtml(item.context)}</div>
            </div>
        `);
    
    // Symptoms
    displayList('symptomsList', result.healthcare_insights.symptoms,
        item => `
            <div class="item">
                <div class="item-title">${escapeHtml(item.symptom)}</div>
                <div class="item-context">${escapeHtml(item.context)}</div>
            </div>
        `);
    
    // Follow-up actions
    displayList('followUpsList', result.healthcare_insights.follow_up_actions,
        item => `
            <div class="item">
                <div class="item-title">${item.type.replace(/_/g, ' ').toUpperCase()}</div>
                <div class="item-detail">${escapeHtml(item.description)}</div>
            </div>
        `);
    
    // Transcription
    document.getElementById('transcriptionText').textContent = result.transcription;
    
    // Display enhanced summary if available
    displayEnhancedSummary(result);
    
    // Key topics
    const topicsList = document.getElementById('topicsList');
    topicsList.innerHTML = '';
    result.healthcare_insights.key_topics.forEach(topic => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = topic;
        topicsList.appendChild(tag);
    });
    
    // Compliance
    const compliance = result.healthcare_insights.compliance_indicators;
    const complianceList = document.getElementById('complianceList');
    complianceList.innerHTML = `
        <div class="compliance-item">
            <span>Consent Mentioned</span>
            <span class="compliance-check ${compliance.consent_mentioned ? 'pass' : 'fail'}">
                <i class="fas fa-${compliance.consent_mentioned ? 'check-circle' : 'circle'}"></i>
            </span>
        </div>
        <div class="compliance-item">
            <span>Privacy Acknowledged</span>
            <span class="compliance-check ${compliance.privacy_acknowledged ? 'pass' : 'fail'}">
                <i class="fas fa-${compliance.privacy_acknowledged ? 'check-circle' : 'circle'}"></i>
            </span>
        </div>
        <div class="compliance-item">
            <span>Patient Understanding Confirmed</span>
            <span class="compliance-check ${compliance.patient_understanding_confirmed ? 'pass' : 'fail'}">
                <i class="fas fa-${compliance.patient_understanding_confirmed ? 'check-circle' : 'circle'}"></i>
            </span>
        </div>
        <div class="compliance-item">
            <span>Follow-up Scheduled</span>
            <span class="compliance-check ${compliance.follow_up_scheduled ? 'pass' : 'fail'}">
                <i class="fas fa-${compliance.follow_up_scheduled ? 'check-circle' : 'circle'}"></i>
            </span>
        </div>
        <div class="compliance-item">
            <span><strong>Documentation Quality</strong></span>
            <span><strong>${compliance.documentation_quality.toUpperCase().replace(/_/g, ' ')}</strong></span>
        </div>
    `;
    
    // Structured data
    document.getElementById('structuredData').textContent = 
        JSON.stringify(result, null, 2);
    
    // Attach event listeners for buttons (Push to Solr, etc.)
    attachResultEventListeners();
}

// Display list helper
function displayList(elementId, items, template) {
    const element = document.getElementById(elementId);
    if (!items || items.length === 0) {
        element.innerHTML = '<p class="empty-state">None identified</p>';
        return;
    }
    element.innerHTML = items.map(template).join('');
}

// Upload modal
function showUploadModal() {
    document.getElementById('uploadModal').classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
    // Reset upload form
    document.getElementById('fileInput').value = '';
    document.getElementById('uploadArea').classList.remove('hidden');
    document.getElementById('uploadProgress').classList.add('hidden');
}

// Drag and drop
function setupDragAndDrop() {
    const uploadArea = document.getElementById('uploadArea');
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.style.borderColor = '#76b900';
            uploadArea.style.background = '#f8f9fa';
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.style.borderColor = '';
            uploadArea.style.background = '';
        }, false);
    });
    
    uploadArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    }, false);
}

// Handle file select
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        uploadFile(file);
    }
}

// Upload file
async function uploadFile(file) {
    document.getElementById('uploadArea').classList.add('hidden');
    document.getElementById('uploadProgress').classList.remove('hidden');
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('folder_path', currentFolderPath);
    
    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Upload failed');
        }
        
        const result = await response.json();
        
        document.getElementById('uploadStatus').textContent = 'Upload complete!';
        document.getElementById('progressFill').style.width = '100%';
        
        setTimeout(() => {
            closeModal('uploadModal');
            loadFiles(currentFolderPath);
        }, 1000);
        
    } catch (error) {
        console.error('Upload error:', error);
        alert('Error uploading file. Please try again.');
        closeModal('uploadModal');
    }
}

// Delete file
async function deleteFile(filePath, fileName) {
    // Confirm deletion
    if (!confirm(`Are you sure you want to delete "${fileName}"?\n\nThis action cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/files/${encodeURIComponent(filePath)}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Delete failed');
        }
        
        const result = await response.json();
        console.log('Delete successful:', result);
        
        // If the deleted file was currently selected, clear selection
        if (currentFile && currentFile.path === filePath) {
            currentFile = null;
            const fileDetails = document.getElementById('fileDetails');
            const analysisResults = document.getElementById('analysisResults');
            
            if (fileDetails) {
                fileDetails.classList.add('hidden');
            }
            if (analysisResults) {
                analysisResults.classList.add('hidden');
            }
        }
        
        // Reload file list - force refresh with current folder
        console.log('Reloading files from:', currentFolderPath);
        await loadFiles(currentFolderPath);
        
        // Show success message after reload
        showSuccess(`File "${fileName}" deleted successfully`);
        
    } catch (error) {
        console.error('Delete error:', error);
        showError(`Failed to delete file: ${error.message}`);
    }
}

// New folder modal
function showNewFolderModal() {
    document.getElementById('newFolderModal').classList.remove('hidden');
}

async function createFolder() {
    const input = document.getElementById('folderNameInput');
    const name = input.value.trim();
    
    if (!name) {
        alert('Please enter a folder name');
        return;
    }
    
    try {
        const response = await fetch('/api/files/create-folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                path: currentFolderPath,
                name: name
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to create folder');
        }
        
        closeModal('newFolderModal');
        input.value = '';
        loadFiles(currentFolderPath);
        
    } catch (error) {
        console.error('Error creating folder:', error);
        alert('Error creating folder. Please try again.');
    }
}

// Copy transcription
function copyTranscription() {
    const text = document.getElementById('transcriptionText').textContent;
    
    // Try modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showSuccess('Transcription copied to clipboard!');
        }).catch(err => {
            console.error('Clipboard API failed:', err);
            // Fallback to older method
            fallbackCopyToClipboard(text);
        });
    } else {
        // Use fallback for older browsers
        fallbackCopyToClipboard(text);
    }
}

// Fallback copy method for older browsers or when clipboard API fails
function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.width = '2em';
    textArea.style.height = '2em';
    textArea.style.padding = '0';
    textArea.style.border = 'none';
    textArea.style.outline = 'none';
    textArea.style.boxShadow = 'none';
    textArea.style.background = 'transparent';
    
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showSuccess('Transcription copied to clipboard!');
        } else {
            showError('Failed to copy transcription. Please select and copy manually.');
        }
    } catch (err) {
        console.error('Fallback copy failed:', err);
        showError('Failed to copy transcription. Please select and copy manually.');
    }
    
    document.body.removeChild(textArea);
}

// Toggle transcription visibility
function toggleTranscription() {
    const body = document.getElementById('transcriptionBody');
    const icon = document.getElementById('transcriptionToggleIcon');
    
    if (body.style.display === 'none') {
        body.style.display = 'block';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
    } else {
        body.style.display = 'none';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
    }
}

// Download JSON
function downloadJSON() {
    if (!currentResult) return;
    
    const dataStr = JSON.stringify(currentResult, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `analysis_${currentFile.name}_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
}

// Settings Management
async function showSettingsModal() {
    document.getElementById('settingsModal').classList.remove('hidden');
    await loadSettings();
}

async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        
        // Load transcription settings
        document.getElementById('cdpBaseUrl').value = settings.cdp_base_url || '';
        document.getElementById('cdpJwtPath').value = settings.cdp_jwt_path || '/tmp/jwt';
        document.getElementById('defaultLanguage').value = settings.default_language || 'en';
        
        // Update CDP token status
        updateTokenStatus(settings.cdp_token_configured, settings.cdp_token_preview);
        
        // Load summarization settings
        document.getElementById('nemotronEnabled').checked = settings.nemotron_enabled || false;
        document.getElementById('nemotronBaseUrl').value = settings.nemotron_base_url || '';
        document.getElementById('nemotronModelId').value = settings.nemotron_model_id || 'nvidia/llama-3.3-nemotron-super-49b-v1';
        
        // Load Solr settings
        document.getElementById('solrEnabled').checked = settings.solr_enabled || false;
        document.getElementById('solrBaseUrl').value = settings.solr_base_url || '';
        document.getElementById('solrCollectionName').value = settings.solr_collection_name || 'healthcare_calls';
        
        // Update Solr token status (but don't expose the actual token)
        updateSolrTokenStatus(settings.solr_token_configured, settings.solr_token_preview);
        
        // Load general settings
        document.getElementById('serverHost').value = settings.host || '0.0.0.0';
        document.getElementById('serverPort').value = settings.port || 8000;
        document.getElementById('autoRenewTokens').checked = settings.auto_renew_tokens !== false;  // Default to true
        document.getElementById('knoxRenewalEndpoint').value = settings.knox_renewal_endpoint || '';
        // Don't load hadoop_jwt (security)
        
    } catch (error) {
        console.error('Error loading settings:', error);
        alert('Error loading settings');
    }
}

function updateTokenStatus(configured, preview) {
    const statusEl = document.getElementById('tokenStatus');
    if (configured && preview) {
        statusEl.textContent = `Status: Token configured (${preview})`;
        statusEl.style.color = '#4caf50';
    } else {
        statusEl.textContent = 'Status: Using JWT file';
        statusEl.style.color = '#7f8c8d';
    }
}

function toggleTokenVisibility() {
    const tokenInput = document.getElementById('cdpToken');
    const icon = document.getElementById('tokenToggleIcon');
    
    if (tokenInput.type === 'password') {
        tokenInput.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        tokenInput.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

function updateSolrTokenStatus(configured, preview) {
    const statusEl = document.getElementById('solrTokenStatus');
    if (configured && preview) {
        statusEl.textContent = `Status: Token configured (${preview})`;
        statusEl.style.color = '#4caf50';
    } else {
        statusEl.textContent = 'Solr requires its own CDP access token';
        statusEl.style.color = '#7f8c8d';
    }
}

function toggleSolrTokenVisibility() {
    const tokenInput = document.getElementById('solrToken');
    const icon = document.getElementById('solrTokenToggleIcon');
    
    if (tokenInput.type === 'password') {
        tokenInput.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        tokenInput.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

async function saveSettings() {
    try {
        const settings = {
            cdp_base_url: document.getElementById('cdpBaseUrl').value,
            cdp_jwt_path: document.getElementById('cdpJwtPath').value,
            default_language: document.getElementById('defaultLanguage').value,
            nemotron_enabled: document.getElementById('nemotronEnabled').checked,
            nemotron_base_url: document.getElementById('nemotronBaseUrl').value,
            nemotron_model_id: document.getElementById('nemotronModelId').value,
            solr_enabled: document.getElementById('solrEnabled').checked,
            solr_base_url: document.getElementById('solrBaseUrl').value,
            solr_collection_name: document.getElementById('solrCollectionName').value,
            auto_renew_tokens: document.getElementById('autoRenewTokens').checked,
            knox_renewal_endpoint: document.getElementById('knoxRenewalEndpoint').value,
        };
        
        // Include CDP token if provided
        const cdpToken = document.getElementById('cdpToken').value.trim();
        if (cdpToken) {
            settings.cdp_token = cdpToken;
        }
        
        // Include Solr token if provided
        const solrToken = document.getElementById('solrToken').value.trim();
        if (solrToken) {
            settings.solr_token = solrToken;
        }
        
        // Include hadoop-jwt if provided
        const hadoopJwt = document.getElementById('hadoopJwt').value.trim();
        if (hadoopJwt) {
            settings.hadoop_jwt = hadoopJwt;
        }
        
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (!response.ok) {
            throw new Error('Failed to save settings');
        }
        
        const result = await response.json();
        
        // Show success message
        alert('✓ Settings saved successfully!\n\n' + 
              '• Changes persisted to .env file\n' +
              '• Configuration will survive restarts\n' +
              (cdpToken ? '• CDP Token securely stored\n' : '') +
              '\nServices have been reinitialized with new settings.');
        
        // Clear token input for security
        document.getElementById('cdpToken').value = '';
        document.getElementById('cdpToken').type = 'password';
        document.getElementById('tokenToggleIcon').className = 'fas fa-eye';
        
        closeModal('settingsModal');
        
        // Refresh health check and hide setup modal if it was showing
        checkHealth();
        document.getElementById('setupModal').style.display = 'none';
        
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('❌ Error saving settings.\n\nPlease check the console for details and try again.');
    }
}

function showSettingsTab(tabName) {
    // Remove active class from all tabs and contents
    document.querySelectorAll('.settings-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.settings-content').forEach(content => content.classList.remove('active'));
    
    // Add active class to selected tab and content
    event.target.classList.add('active');
    document.getElementById(tabName + 'Settings').classList.add('active');
}

// Convert markdown-style text to HTML
function markdownToHtml(text) {
    if (!text) return '';
    
    // Convert ### and #### headings first (before line breaks)
    text = text.replace(/^#### (.+)$/gm, '<h5>$1</h5>');
    text = text.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    
    // Convert **bold** to <strong>
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Process lists line by line to handle nesting
    const lines = text.split('\n');
    let inList = false;
    let listDepth = 0;
    const processedLines = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const bulletMatch = line.match(/^(\s*)([\*\+\-])\s+(.+)$/);
        
        if (bulletMatch) {
            const indent = bulletMatch[1].length;
            const content = bulletMatch[3];
            const depth = Math.floor(indent / 2); // 2 spaces or 1 tab = 1 level
            
            if (!inList) {
                processedLines.push('<ul>');
                inList = true;
                listDepth = depth;
            } else if (depth > listDepth) {
                processedLines.push('<ul>');
                listDepth = depth;
            } else if (depth < listDepth) {
                processedLines.push('</ul>');
                listDepth = depth;
            }
            
            processedLines.push(`<li>${content}</li>`);
        } else {
            if (inList) {
                while (listDepth >= 0) {
                    processedLines.push('</ul>');
                    listDepth--;
                }
                inList = false;
            }
            processedLines.push(line);
        }
    }
    
    // Close any remaining lists
    if (inList) {
        while (listDepth >= 0) {
            processedLines.push('</ul>');
            listDepth--;
        }
    }
    
    text = processedLines.join('\n');
    
    // Remove excessive blank lines (more than one consecutive)
    text = text.replace(/\n{3,}/g, '\n\n');
    
    // Convert line breaks (double newline = paragraph, single = br)
    text = text.replace(/\n\n+/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');
    
    // Remove <br> tags right before/after block elements
    text = text.replace(/<br>\s*<\/ul>/g, '</ul>');
    text = text.replace(/<ul>\s*<br>/g, '<ul>');
    text = text.replace(/<br>\s*<h/g, '<h');
    text = text.replace(/<\/h[45]>\s*<br>/g, (match) => match.replace('<br>', ''));
    
    // Wrap in paragraph if not already wrapped
    if (!text.startsWith('<h') && !text.startsWith('<p>') && !text.startsWith('<ul>')) {
        text = '<p>' + text + '</p>';
    }
    
    return text;
}

// Check if a list item is complete/valid
function isValidListItem(item) {
    if (!item || typeof item !== 'string') return false;
    
    const trimmed = item.trim();
    
    // Skip empty or very short items
    if (trimmed.length < 5) return false;
    
    // Skip items that are just labels/headers with no content
    // (ends with colon and has no sentence)
    if (trimmed.endsWith(':') && !trimmed.includes('.') && trimmed.length < 100) {
        return false;
    }
    
    // Skip meta-notes from AI
    if (trimmed.toLowerCase().startsWith('note:') || 
        trimmed.toLowerCase().includes('if you\'d like') ||
        trimmed.toLowerCase().includes('somewhat speculative')) {
        return false;
    }
    
    // Skip items that are just formatting instructions
    if (trimmed.match(/^\d+\.\s*\*\*[^*]+\*\*:\s*$/)) {
        return false;
    }
    
    return true;
}

// Display enhanced summary if available
function displayEnhancedSummary(result) {
    const enhancedSummary = result.healthcare_insights?.enhanced_summary;
    
    if (enhancedSummary && enhancedSummary.generated_by === 'nemotron') {
        const card = document.getElementById('enhancedSummaryCard');
        card.style.display = 'block';
        
        // Clinical summary - render markdown
        document.getElementById('clinicalSummary').innerHTML = markdownToHtml(enhancedSummary.clinical_summary);
        
        // Key takeaways - filter and validate
        const takeawaysList = document.getElementById('keyTakeawaysList');
        takeawaysList.innerHTML = '';
        if (enhancedSummary.key_takeaways && enhancedSummary.key_takeaways.length > 0) {
            const validTakeaways = enhancedSummary.key_takeaways.filter(isValidListItem);
            
            if (validTakeaways.length > 0) {
                validTakeaways.forEach(takeaway => {
                    const li = document.createElement('li');
                    li.innerHTML = markdownToHtml(takeaway);
                    takeawaysList.appendChild(li);
                });
            } else {
                takeawaysList.innerHTML = '<li>No key takeaways generated</li>';
            }
        } else {
            takeawaysList.innerHTML = '<li>No key takeaways generated</li>';
        }
        
        // Recommended actions - filter and validate
        const actionsList = document.getElementById('recommendedActionsList');
        actionsList.innerHTML = '';
        if (enhancedSummary.recommended_actions && enhancedSummary.recommended_actions.length > 0) {
            const validActions = enhancedSummary.recommended_actions.filter(isValidListItem);
            
            if (validActions.length > 0) {
                validActions.forEach(action => {
                    const li = document.createElement('li');
                    li.innerHTML = markdownToHtml(action);
                    actionsList.appendChild(li);
                });
            } else {
                actionsList.innerHTML = '<li>No specific actions recommended</li>';
            }
        } else {
            actionsList.innerHTML = '<li>No specific actions recommended</li>';
        }
    } else {
        document.getElementById('enhancedSummaryCard').style.display = 'none';
    }
}

// Push to Solr
async function pushToSolr() {
    console.log('pushToSolr() called, currentResult:', currentResult);
    
    if (!currentResult) {
        showError('No analysis result to push. Please analyze a call first.');
        return;
    }
    
    const pushBtn = document.getElementById('pushToSolrBtn');
    if (!pushBtn) {
        console.error('Push to Solr button not found');
        return;
    }
    
    const originalText = pushBtn.innerHTML;
    
    try {
        // Show immediate feedback
        console.log('Pushing to Solr...', currentResult);
        
        // Disable button and show loading state
        pushBtn.disabled = true;
        pushBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pushing...';
        
        // Force a UI update
        await new Promise(resolve => setTimeout(resolve, 10));
        
        const response = await fetch('/api/solr/push', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(currentResult)
        });
        
        console.log('Solr push response:', response.status);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to push to Solr');
        }
        
        const result = await response.json();
        console.log('Solr push result:', result);
        
        if (result.success) {
            showSuccess(`Successfully indexed to Solr collection '${result.collection}'`);
            console.log('Solr index result:', result);
        } else {
            throw new Error(result.message || 'Push to Solr failed');
        }
        
    } catch (error) {
        console.error('Error pushing to Solr:', error);
        showError(`Failed to push to Solr: ${error.message}`);
    } finally {
        // Re-enable button
        pushBtn.disabled = false;
        pushBtn.innerHTML = originalText;
    }
}

// Escape HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Initialize event listeners when results are displayed
function attachResultEventListeners() {
    const pushBtn = document.getElementById('pushToSolrBtn');
    if (pushBtn) {
        // Remove any existing listeners
        pushBtn.replaceWith(pushBtn.cloneNode(true));
        const newPushBtn = document.getElementById('pushToSolrBtn');
        
        newPushBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('Push to Solr button clicked!');
            await pushToSolr();
        });
        
        console.log('Push to Solr button event listener attached');
    }
}

