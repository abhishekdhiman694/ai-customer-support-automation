

const state = {
    activeTab: 'inbox',
    tickets: [],
    kbArticles: [],
    activeTicketId: null,
    settings: {
        gemini_api_key: '',
        model_name: 'gemini-1.5-flash',
        temperature: 0.2
    }
};

document.addEventListener('DOMContentLoaded', () => {
    loadSettingsFromStorage();
    fetchTickets();
    fetchKB();
    
    
    window.addEventListener('click', (e) => {
        const modalTicket = document.getElementById('modal-new-ticket');
        const modalKB = document.getElementById('modal-new-article');
        if (e.target === modalTicket) closeNewTicketModal();
        if (e.target === modalKB) closeNewArticleModal();
    });
});

function loadSettingsFromStorage() {
    const saved = localStorage.getItem('ff_ai_settings');
    if (saved) {
        try {
            state.settings = JSON.parse(saved);
            
            
            document.getElementById('gemini-api-key').value = state.settings.gemini_api_key || '';
            document.getElementById('model-selector').value = state.settings.model_name || 'gemini-1.5-flash';
            document.getElementById('temp-slider').value = state.settings.temperature ?? 0.2;
            document.getElementById('temp-display-val').innerText = state.settings.temperature ?? 0.2;
            
            updateAPIStatusIndicator();
        } catch (e) {
            console.error('Error loading cached settings:', e);
        }
    }
}

function updateAPIStatusIndicator() {
    const dot = document.getElementById('api-status-dot');
    const text = document.getElementById('api-status-text');
    
    if (state.settings.gemini_api_key && state.settings.gemini_api_key.trim().length > 0) {
        dot.className = 'status-dot online';
        text.innerText = `Gemini API Active (${getShortModelName(state.settings.model_name)})`;
    } else {
        dot.className = 'status-dot offline';
        text.innerText = 'Using Local Mock Engine';
    }
}

function getShortModelName(fullName) {
    if (fullName.includes('pro')) return '1.5 Pro';
    if (fullName.includes('2.0')) return '2.0 Flash';
    return '1.5 Flash';
}

function switchTab(tabName) {
    state.activeTab = tabName;
    
    
    document.querySelectorAll('.menu-item').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(`menu-${tabName}`).classList.add('active');
    
    
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    
    const titles = {
        'inbox': 'Ticket Inbox',
        'kb': 'Knowledge Base Reference Desk',
        'analytics': 'Operational Analytics',
        'settings': 'Model Playground Settings'
    };
    document.getElementById('page-title').innerText = titles[tabName] || 'Dashboard';
    
    
    if (tabName === 'analytics') {
        renderAnalytics();
    } else if (tabName === 'kb') {
        renderKB();
    } else if (tabName === 'inbox') {
        fetchTickets();
    }
}

async function fetchTickets() {
    try {
        const res = await fetch('/api/tickets');
        state.tickets = await res.json();
        renderTickets();
        
        
        const newCount = state.tickets.filter(t => t.status === 'New').length;
        const badge = document.getElementById('inbox-count');
        badge.innerText = newCount;
        badge.style.display = newCount > 0 ? 'inline-block' : 'none';
    } catch (e) {
        console.error('Error fetching tickets:', e);
        showToast('Could not load support tickets.', 'error');
    }
}

function renderTickets() {
    const container = document.getElementById('ticket-list-container');
    container.innerHTML = '';
    
    const searchVal = document.getElementById('search-tickets').value.toLowerCase();
    const filterCat = document.getElementById('filter-category').value;
    const filterPrio = document.getElementById('filter-priority').value;
    
    const filtered = state.tickets.filter(t => {
        const matchesSearch = t.customer_name.toLowerCase().includes(searchVal) || 
                              t.subject.toLowerCase().includes(searchVal) || 
                              t.message.toLowerCase().includes(searchVal);
        const matchesCat = filterCat === '' || t.category === filterCat;
        const matchesPrio = filterPrio === '' || t.priority === filterPrio;
        
        return matchesSearch && matchesCat && matchesPrio;
    });
    
    if (filtered.length === 0) {
        container.innerHTML = '<p class="neutral-placeholder" style="padding: 20px; text-align: center;">No tickets match filters.</p>';
        return;
    }
    
    filtered.forEach(ticket => {
        const div = document.createElement('div');
        div.className = `ticket-item ${state.activeTicketId === ticket.id ? 'active' : ''}`;
        div.onclick = () => selectTicket(ticket.id);
        
        
        const desc = ticket.message.length > 55 ? ticket.message.substring(0, 55) + '...' : ticket.message;
        
        
        const statusClass = `status-${ticket.status.toLowerCase()}`;
        const prioClass = `prio-${ticket.priority.toLowerCase()}`;
        const sentClass = `sent-${ticket.sentiment.toLowerCase()}`;
        
        div.innerHTML = `
            <div class="ticket-item-header">
                <h4>${ticket.subject}</h4>
                <span class="ticket-item-date">${formatDate(ticket.created_at)}</span>
            </div>
            <p class="ticket-item-desc">${desc}</p>
            <div class="ticket-tags-row">
                <span class="status-badge tag ${statusClass}">${ticket.status}</span>
                <span class="tag ${prioClass}">${ticket.priority}</span>
                <span class="tag ${sentClass}">${ticket.sentiment}</span>
                <span class="kb-tag-mini" style="font-size: 9px; margin-left: auto;">${ticket.category}</span>
            </div>
        `;
        container.appendChild(div);
    });
}

function selectTicket(id) {
    state.activeTicketId = id;
    
    
    document.querySelectorAll('.ticket-item').forEach(el => el.classList.remove('active'));
    
    renderTickets();
    
    const ticket = state.tickets.find(t => t.id === id);
    if (!ticket) return;
    
    
    document.getElementById('empty-ticket-view').style.display = 'none';
    document.getElementById('active-ticket-view').style.display = 'block';
    
    
    document.getElementById('ticket-subject').innerText = ticket.subject;
    document.getElementById('ticket-customer').innerText = ticket.customer_name;
    document.getElementById('ticket-email').innerText = ticket.email;
    document.getElementById('ticket-time').innerText = formatDateFull(ticket.created_at);
    
    const statusBadge = document.getElementById('ticket-status-badge');
    statusBadge.innerText = ticket.status;
    statusBadge.className = `status-badge status-${ticket.status.toLowerCase()}`;
    
    document.getElementById('ticket-message-text').innerText = ticket.message;
    
    
    document.getElementById('ticket-confidence').innerText = `Confidence: ${(ticket.confidence * 100).toFixed(0)}%`;
    document.getElementById('ticket-ai-category').innerText = ticket.category;
    document.getElementById('ticket-ai-priority').innerText = ticket.priority;
    
    const prioLabel = document.getElementById('ticket-ai-priority');
    prioLabel.className = `value-tag tag prio-${ticket.priority.toLowerCase()}`;
    
    const sentLabel = document.getElementById('ticket-ai-sentiment');
    sentLabel.innerText = ticket.sentiment;
    sentLabel.className = `value-tag tag sent-${ticket.sentiment.toLowerCase()}`;
    
    document.getElementById('ticket-ai-reasoning').innerText = ticket.ai_reasoning;
    
    
    const ragContainer = document.getElementById('rag-articles-list');
    ragContainer.innerHTML = '';
    
    if (ticket.rag_sources && ticket.rag_sources.length > 0) {
        ticket.rag_sources.forEach(src => {
            const srcDiv = document.createElement('div');
            srcDiv.className = 'rag-source-item';
            srcDiv.innerHTML = `
                <h4>📚 ${src.title} (${src.category})</h4>
                <p>${src.content.substring(0, 180)}...</p>
            `;
            ragContainer.appendChild(srcDiv);
        });
    } else {
        ragContainer.innerHTML = '<p class="neutral-placeholder">No matching RAG articles found. Classifying based on general context.</p>';
    }
    
    
    const composer = document.getElementById('email-draft-body');
    composer.value = ticket.draft_response || '';
    
    
    const approveBtn = document.getElementById('approve-btn');
    if (ticket.status === 'Resolved') {
        composer.disabled = true;
        approveBtn.disabled = true;
        approveBtn.innerText = 'Draft Sent & Approved';
        approveBtn.style.opacity = '0.6';
    } else {
        composer.disabled = false;
        approveBtn.disabled = false;
        approveBtn.innerText = 'Approve & Send Draft';
        approveBtn.style.opacity = '1';
    }
}

function filterTickets() {
    renderTickets();
}

async function approveResponse() {
    if (!state.activeTicketId) return;
    
    const draftText = document.getElementById('email-draft-body').value;
    
    try {
        const res = await fetch(`/api/tickets/${state.activeTicketId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ draft_response: draftText })
        });
        
        if (res.ok) {
            const updated = await res.json();
            showToast('Email reply approved and sent successfully!', 'success');
            
            
            const index = state.tickets.findIndex(t => t.id === updated.id);
            if (index !== -1) {
                state.tickets[index] = updated;
            }
            
            
            fetchTickets().then(() => {
                selectTicket(updated.id);
            });
        } else {
            showToast('Failed to approve the ticket.', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('Server connection failed.', 'error');
    }
}

async function reAnalyzeTicket() {
    if (!state.activeTicketId) return;
    
    showToast('Regenerating AI classification and draft email...', 'info');
    
    const detailsContainer = document.getElementById('ticket-detail-pane');
    const prevContent = detailsContainer.innerHTML;
    
    
    const composer = document.getElementById('email-draft-body');
    composer.value = 'Running AI Pipeline Analysis... Please wait...';
    composer.disabled = true;
    
    try {
        const res = await fetch(`/api/tickets/${state.activeTicketId}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gemini_api_key: state.settings.gemini_api_key,
                model_name: state.settings.model_name,
                temperature: parseFloat(state.settings.temperature)
            })
        });
        
        if (res.ok) {
            const updated = await res.json();
            showToast('Analysis completed!', 'success');
            
            
            const index = state.tickets.findIndex(t => t.id === updated.id);
            if (index !== -1) {
                state.tickets[index] = updated;
            }
            
            selectTicket(updated.id);
        } else {
            showToast('Error during re-analysis.', 'error');
            selectTicket(state.activeTicketId); 
        }
    } catch (e) {
        console.error(e);
        showToast('Server connection error.', 'error');
        selectTicket(state.activeTicketId);
    }
}

function openNewTicketModal() {
    document.getElementById('modal-new-ticket').classList.add('active');
}

function closeNewTicketModal() {
    document.getElementById('modal-new-ticket').classList.remove('active');
    document.getElementById('new-ticket-form').reset();
}

async function submitNewTicket(event) {
    event.preventDefault();
    
    const name = document.getElementById('new-customer-name').value;
    const email = document.getElementById('new-customer-email').value;
    const subject = document.getElementById('new-ticket-subject').value;
    const msg = document.getElementById('new-ticket-message').value;
    
    const btn = document.getElementById('ticket-submit-btn');
    btn.disabled = true;
    btn.innerText = 'AI Agent Classifying...';
    
    try {
        const headers = {
            'Content-Type': 'application/json',
            'X-Model-Name': state.settings.model_name,
            'X-Temperature': state.settings.temperature.toString()
        };
        
        if (state.settings.gemini_api_key) {
            headers['X-Gemini-Key'] = state.settings.gemini_api_key;
        }
        
        const res = await fetch('/api/tickets', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                customer_name: name,
                email: email,
                subject: subject,
                message: msg
            })
        });
        
        if (res.ok) {
            const created = await res.json();
            showToast('New ticket ingested and analyzed by AI!', 'success');
            closeNewTicketModal();
            
            
            await fetchTickets();
            selectTicket(created.id);
        } else {
            showToast('Failed to ingest ticket.', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('Server communication failure.', 'error');
    } finally {
        btn.disabled = false;
        btn.innerText = 'Ingest & Run AI Pipeline';
    }
}

async function fetchKB() {
    try {
        const res = await fetch('/api/kb');
        state.kbArticles = await res.json();
    } catch (e) {
        console.error('Error fetching KB:', e);
    }
}

function renderKB() {
    const container = document.getElementById('kb-grid-container');
    container.innerHTML = '';
    
    const searchVal = document.getElementById('search-kb').value.toLowerCase();
    
    const filtered = state.kbArticles.filter(art => {
        return art.title.toLowerCase().includes(searchVal) || 
               art.content.toLowerCase().includes(searchVal) || 
               art.tags.some(tag => tag.toLowerCase().includes(searchVal));
    });
    
    if (filtered.length === 0) {
        container.innerHTML = '<p class="neutral-placeholder" style="grid-column: 1/-1; text-align: center; padding: 40px;">No KB articles found matching search criteria.</p>';
        return;
    }
    
    filtered.forEach(art => {
        const card = document.createElement('div');
        card.className = 'kb-article-card';
        
        
        const tagsHTML = art.tags.map(t => `<span class="kb-tag-mini">${t}</span>`).join('');
        
        card.innerHTML = `
            <div class="kb-card-header">
                <h3>${art.title}</h3>
                <span class="kb-category-tag">${art.category}</span>
            </div>
            <div class="kb-card-body">
                <p>${art.content}</p>
            </div>
            <div class="kb-card-footer">
                <div class="kb-tags-list">
                    ${tagsHTML}
                </div>
                <div class="kb-actions">
                    <button class="btn-icon-only" onclick="deleteKBArticle(${art.id})" title="Delete Article">
                        <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

function openNewArticleModal() {
    document.getElementById('modal-new-article').classList.add('active');
}

function closeNewArticleModal() {
    document.getElementById('modal-new-article').classList.remove('active');
    document.getElementById('new-article-form').reset();
}

async function submitNewArticle(event) {
    event.preventDefault();
    
    const title = document.getElementById('kb-article-title').value;
    const cat = document.getElementById('kb-article-category').value;
    const tagsStr = document.getElementById('kb-article-tags').value;
    const content = document.getElementById('kb-article-content').value;
    
    
    const tags = tagsStr.split(',')
                         .map(t => t.trim())
                         .filter(t => t.length > 0);
                         
    try {
        const res = await fetch('/api/kb', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                category: cat,
                tags: tags,
                content: content
            })
        });
        
        if (res.ok) {
            showToast('Knowledge FAQ article added to RAG database!', 'success');
            closeNewArticleModal();
            await fetchKB();
            renderKB();
        } else {
            showToast('Failed to save article.', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('Server communication failed.', 'error');
    }
}

async function deleteKBArticle(id) {
    if (!confirm('Are you sure you want to delete this knowledge base reference article? It will no longer be available for RAG lookups.')) {
        return;
    }
    
    try {
        const res = await fetch(`/api/kb/${id}`, {
            method: 'DELETE'
        });
        
        if (res.ok) {
            showToast('Article removed from RAG index.', 'success');
            await fetchKB();
            renderKB();
        } else {
            showToast('Failed to delete KB article.', 'error');
        }
    } catch (e) {
        console.error(e);
        showToast('Server communication failed.', 'error');
    }
}

async function renderAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();
        
        
        document.getElementById('metric-total-tickets').innerText = data.summary.total;
        document.getElementById('metric-automation-rate').innerText = `${data.summary.automation_rate}%`;
        document.getElementById('metric-cost-saved').innerText = `$${data.summary.cost_saved_usd.toFixed(2)}`;
        
        
        const categoryBars = document.getElementById('category-bars');
        categoryBars.innerHTML = '';
        const catKeys = Object.keys(data.by_category);
        const maxCatVal = Math.max(...Object.values(data.by_category), 1);
        
        if (catKeys.length === 0) {
            categoryBars.innerHTML = '<p class="neutral-placeholder">No ticket statistics logged yet.</p>';
        } else {
            catKeys.forEach(cat => {
                const count = data.by_category[cat];
                const pct = (count / maxCatVal) * 100;
                
                const row = document.createElement('div');
                row.className = 'chart-bar-row';
                row.innerHTML = `
                    <span class="chart-bar-label">${cat}</span>
                    <div class="chart-bar-track">
                        <div class="chart-bar-fill fill-blue" style="width: ${pct}%"></div>
                    </div>
                    <span class="chart-bar-value">${count}</span>
                `;
                categoryBars.appendChild(row);
            });
        }
        
        
        const sentimentBars = document.getElementById('sentiment-bars');
        sentimentBars.innerHTML = '';
        const sentKeys = Object.keys(data.by_sentiment);
        const maxSentVal = Math.max(...Object.values(data.by_sentiment), 1);
        
        if (sentKeys.length === 0) {
            sentimentBars.innerHTML = '<p class="neutral-placeholder">No ticket statistics logged yet.</p>';
        } else {
            sentKeys.forEach(sent => {
                const count = data.by_sentiment[sent];
                const pct = (count / maxSentVal) * 100;
                
                
                let colorClass = 'fill-blue';
                if (sent === 'Angry') colorClass = 'fill-red';
                else if (sent === 'Frustrated') colorClass = 'fill-purple';
                else if (sent === 'Positive') colorClass = 'fill-green';
                
                const row = document.createElement('div');
                row.className = 'chart-bar-row';
                row.innerHTML = `
                    <span class="chart-bar-label">${sent}</span>
                    <div class="chart-bar-track">
                        <div class="chart-bar-fill ${colorClass}" style="width: ${pct}%"></div>
                    </div>
                    <span class="chart-bar-value">${count}</span>
                `;
                sentimentBars.appendChild(row);
            });
        }
        
        
        const tableBody = document.getElementById('model-comparison-rows');
        tableBody.innerHTML = '';
        data.model_comparison.forEach(m => {
            const tr = document.createElement('tr');
            
            
            const resolvedCount = data.summary.resolved;
            
            const estCost = resolvedCount * ( (1000/1000 * m.cost_per_1k_in) + (350/1000 * m.cost_per_1k_out) );
            
            tr.innerHTML = `
                <td><strong>${m.model}</strong></td>
                <td>$${m.cost_per_1k_in * 1000} per 1M</td>
                <td>$${m.cost_per_1k_out * 1000} per 1M</td>
                <td><span class="tag prio-medium">${m.avg_latency}</span></td>
                <td><span class="tag sent-neutral">${m.accuracy}</span></td>
            `;
            tableBody.appendChild(tr);
        });
        
    } catch (e) {
        console.error('Error rendering analytics:', e);
    }
}

function updateTempDisplay(val) {
    document.getElementById('temp-display-val').innerText = val;
}

function saveSettings(event) {
    event.preventDefault();
    
    const key = document.getElementById('gemini-api-key').value;
    const model = document.getElementById('model-selector').value;
    const temp = parseFloat(document.getElementById('temp-slider').value);
    
    state.settings = {
        gemini_api_key: key,
        model_name: model,
        temperature: temp
    };
    
    localStorage.setItem('ff_ai_settings', JSON.stringify(state.settings));
    updateAPIStatusIndicator();
    showToast('AI Model config preferences updated & saved successfully.', 'success');
}

function clearSettings() {
    document.getElementById('gemini-api-key').value = '';
    state.settings.gemini_api_key = '';
    
    localStorage.setItem('ff_ai_settings', JSON.stringify(state.settings));
    updateAPIStatusIndicator();
    showToast('Cached API key credentials erased.', 'warning');
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function formatDateFull(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, { 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit'
    });
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let label = '✓';
    if (type === 'error') label = '✗';
    if (type === 'warning') label = '⚠';
    if (type === 'info') label = 'ℹ';
    
    toast.innerHTML = `
        <span>${label} &nbsp; ${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    container.appendChild(toast);
    
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.4s ease';
        setTimeout(() => toast.remove(), 400);
    }, 4500);
}
