const API_BASE = '/api';
let autoRefreshTimer = null;
let searchQuery = '';
let currentSort = { column: 'id', direction: 'asc' };
let serversData = [];
let isRefreshing = false;

const SERVICES = {
    lmhz: { name: 'ЛМЧЗ', color: '🟢', order: 1 },
    lm: { name: 'ЛМ', color: '🔵', order: 2 },
    piot: { name: 'ПИОТ', color: '🟣', order: 3 }
};

function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.className = `toast ${isError ? 'error' : 'success'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

async function loadServers(showLoadingMsg = false) {
    if (isRefreshing) return;
    isRefreshing = true;
    
    try {
        if (showLoadingMsg) showToast('Загрузка данных...');
        
        const response = await fetch(`${API_BASE}/servers`);
        if (!response.ok) throw new Error('Ошибка загрузки');
        
        serversData = await response.json();
        applyFilterAndSort();
        
        await updateStats();
        
        document.getElementById('lastUpdateInfo').textContent = `🕐 ${new Date().toLocaleTimeString('ru-RU')}`;
    } catch (error) {
        console.error('Error loading servers:', error);
        showToast('Ошибка загрузки серверов', true);
    } finally {
        isRefreshing = false;
    }
}

async function updateStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const stats = await response.json();
        
        document.getElementById('totalCount').textContent = stats.total;
        document.getElementById('lmhzReady').textContent = stats.lmhz.ready;
        document.getElementById('lmhzError').textContent = stats.lmhz.error;
        document.getElementById('lmReady').textContent = stats.lm.ready;
        document.getElementById('lmError').textContent = stats.lm.error;
        document.getElementById('piotReady').textContent = stats.piot.ready;
        document.getElementById('piotError').textContent = stats.piot.error;
        
        console.log('Stats updated:', stats);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function formatLicenseDate(dateStr) {
    if (!dateStr) return '<span class="license-badge" style="background:#f1f5f9;color:#64748b;">—</span>';
    
    const licenseDate = new Date(dateStr);
    const today = new Date();
    const diffDays = Math.ceil((licenseDate - today) / (1000 * 60 * 60 * 24));
    
    let colorClass = '';
    let statusText = '';
    
    if (diffDays < 0) {
        colorClass = 'license-expired';
        statusText = 'ПРОСРОЧЕНА';
    } else if (diffDays <= 30) {
        colorClass = 'license-warning';
        statusText = `Осталось ${diffDays} дн.`;
    } else {
        colorClass = 'license-good';
        statusText = `${diffDays} дн.`;
    }
    
    const formattedDate = new Date(dateStr).toLocaleDateString('ru-RU');
    
    return `<span class="license-badge ${colorClass}" title="До ${formattedDate}">${statusText}<br><small>${formattedDate}</small></span>`;
}

function applyFilterAndSort() {
    let filtered = [...serversData];
    
    if (searchQuery && searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        filtered = filtered.filter(s => 
            s.name.toLowerCase().includes(query) || 
            s.ip_lmhz.includes(query) ||
            (s.ip_piot && s.ip_piot.includes(query))
        );
    }
    
    filtered.sort((a, b) => {
        let aVal, bVal;
        
        switch(currentSort.column) {
            case 'id':
                aVal = a.id;
                bVal = b.id;
                return currentSort.direction === 'asc' ? aVal - bVal : bVal - aVal;
                
            case 'name':
                aVal = a.name.toLowerCase();
                bVal = b.name.toLowerCase();
                return currentSort.direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                
            case 'lmhz':
                const aParts = a.ip_lmhz.split('.').map(n => parseInt(n));
                const bParts = b.ip_lmhz.split('.').map(n => parseInt(n));
                for (let i = 0; i < 4; i++) {
                    if (aParts[i] !== bParts[i]) {
                        return currentSort.direction === 'asc' ? aParts[i] - bParts[i] : bParts[i] - aParts[i];
                    }
                }
                return 0;
                
            case 'piot':
                const aPiotParts = (a.ip_piot || '0.0.0.0').split('.').map(n => parseInt(n));
                const bPiotParts = (b.ip_piot || '0.0.0.0').split('.').map(n => parseInt(n));
                for (let i = 0; i < 4; i++) {
                    if (aPiotParts[i] !== bPiotParts[i]) {
                        return currentSort.direction === 'asc' ? aPiotParts[i] - bPiotParts[i] : bPiotParts[i] - aPiotParts[i];
                    }
                }
                return 0;
                
            case 'lmhz_status':
                const statusOrderLmhz = { 'ready': 1, 'error': 2, 'unknown': 3, null: 4, '': 4 };
                aVal = statusOrderLmhz[a.services.lmhz.status];
                bVal = statusOrderLmhz[b.services.lmhz.status];
                return currentSort.direction === 'asc' ? aVal - bVal : bVal - aVal;
                
            case 'lm_status':
                const statusOrderLm = { 'ready': 1, 'error': 2, 'unknown': 3, null: 4, '': 4 };
                aVal = statusOrderLm[a.services.lm.status];
                bVal = statusOrderLm[b.services.lm.status];
                if (a.services.lm.version && aVal === 4) aVal = 1;
                if (b.services.lm.version && bVal === 4) bVal = 1;
                return currentSort.direction === 'asc' ? aVal - bVal : bVal - aVal;
                
            case 'piot_status':
                const statusOrderPiot = { 'ready': 1, 'error': 2, 'unknown': 3, null: 4, '': 4 };
                aVal = statusOrderPiot[a.services.piot.status];
                bVal = statusOrderPiot[b.services.piot.status];
                return currentSort.direction === 'asc' ? aVal - bVal : bVal - aVal;
                
            case 'license':
                aVal = a.services.piot.license_until || '';
                bVal = b.services.piot.license_until || '';
                if (aVal === '' && bVal === '') return 0;
                if (aVal === '') return 1;
                if (bVal === '') return -1;
                return currentSort.direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                
            default:
                return 0;
        }
    });
    
    renderTable(filtered);
}

function sortByColumn(column) {
    if (currentSort.column === column) {
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort.column = column;
        currentSort.direction = 'asc';
    }
    
    updateSortIndicators();
    applyFilterAndSort();
}

function updateSortIndicators() {
    const headers = document.querySelectorAll('th[data-sort]');
    headers.forEach(th => {
        const column = th.getAttribute('data-sort');
        const indicator = th.querySelector('.sort-indicator');
        if (indicator) {
            if (currentSort.column === column) {
                indicator.textContent = currentSort.direction === 'asc' ? ' ▲' : ' ▼';
                th.classList.add('sort-active');
            } else {
                indicator.textContent = ' ↕️';
                th.classList.remove('sort-active');
            }
        }
    });
}

function renderTable(servers) {
    const tbody = document.getElementById('tableBody');
    
    if (!servers.length) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 40px;">🔍 Ничего не найдено</td></tr>';
        return;
    }
    
    tbody.innerHTML = servers.map(server => {
        const renderService = (service, data) => {
            let status = data.status || 'unknown';
            let version = data.version || '—';
            const error = data.error;
            const errorTitle = error ? ` title="${escapeHtml(error)}"` : '';
            const errorClass = error ? ' error-tooltip' : '';
            
            if (service === 'lm' && version !== '—' && version !== null && version !== undefined && (status === 'unknown' || status === null)) {
                status = 'ready';
            }
            
            let statusClass = 'status-unknown';
            let statusText = status;
            
            if (status === 'ready') {
                statusClass = 'status-ready';
                statusText = 'ready';
            } else if (status === 'error') {
                statusClass = 'status-error';
                statusText = 'error';
            } else if (status === 'unknown') {
                statusClass = 'status-unknown';
                statusText = 'unknown';
            }
            
            const versionDisplay = version !== '—' && version ? version : '—';
            
            return `
                <div class="service-item">
                    <span class="service-name">${SERVICES[service].color}</span>
                    <span class="status-badge ${statusClass}"${errorTitle}>${statusText}</span>
                    <span class="version-cell${errorClass}"${errorTitle}>${escapeHtml(versionDisplay)}</span>
                </div>
            `;
        };
        
        return `
            <tr data-id="${server.id}">
                <td>${server.id}</td>
                <td><strong>${escapeHtml(server.name)}</strong>${!server.enabled ? ' <span style="color:#ef4444;">(откл)</span>' : ''}</td>
                <td class="ip-cell">${escapeHtml(server.ip_lmhz)}</td>
                <td class="ip-cell">${server.ip_piot ? escapeHtml(server.ip_piot) : '—'}</td>
                <td class="service-cell">${renderService('lmhz', server.services.lmhz)}</td>
                <td class="service-cell">${renderService('lm', server.services.lm)}</td>
                <td class="service-cell">${renderService('piot', server.services.piot)}</td>
                <td class="license-cell">${formatLicenseDate(server.services.piot.license_until)}</td>
                <td class="actions-cell">
                    <button class="action-btn refresh-btn" data-id="${server.id}" title="Обновить все">🔄</button>
                    <button class="action-btn edit-btn" data-id="${server.id}" title="Редактировать">✏️</button>
                    <button class="action-btn delete-btn" data-id="${server.id}" title="Удалить">🗑️</button>
                </td>
             </tr>
        `;
    }).join('');
    
    document.querySelectorAll('.refresh-btn').forEach(btn => {
        btn.addEventListener('click', () => checkAllServicesForServer(btn.dataset.id));
    });
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', () => editServer(btn.dataset.id));
    });
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteServer(btn.dataset.id));
    });
}

async function checkAllServicesForServer(serverId) {
    showToast('Проверка всех сервисов...');
    try {
        const response = await fetch(`${API_BASE}/servers/${serverId}/check-all`, { method: 'POST' });
        const results = await response.json();
        
        let successCount = 0;
        for (const [service, result] of Object.entries(results)) {
            if (result.success) successCount++;
        }
        showToast(`Проверено 3 сервиса, успешно: ${successCount}`);
        await loadServers();
    } catch (error) {
        showToast('Ошибка при проверке', true);
    }
}

async function checkAllServers() {
    showToast('Проверка всех серверов...');
    try {
        const response = await fetch(`${API_BASE}/servers/check-all`, { method: 'POST' });
        const results = await response.json();
        const totalServers = results.length;
        showToast(`Проверено ${totalServers} серверов`);
        await loadServers();
    } catch (error) {
        showToast('Ошибка при проверке', true);
    }
}

async function addServer() {
    const name = document.getElementById('serverName').value;
    const ip_lmhz = document.getElementById('serverIpLmhz').value;
    const ip_piot = document.getElementById('serverIpPiot').value || ip_lmhz;
    const port_lmhz = parseInt(document.getElementById('serverPortLmhz').value) || 5995;
    const port_lm = parseInt(document.getElementById('serverPortLm').value) || 5063;
    const port_piot = parseInt(document.getElementById('serverPortPiot').value) || 51077;
    
    if (!name || !ip_lmhz) {
        showToast('Заполните название и IP ЛМЧЗ', true);
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/servers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                name, 
                ip_lmhz, 
                ip_piot, 
                port_lmhz, 
                port_lm, 
                port_piot 
            })
        });
        const result = await response.json();
        if (result.success) {
            showToast('Сервер добавлен');
            closeModal();
            await loadServers();
        } else {
            showToast(result.message, true);
        }
    } catch (error) {
        showToast('Ошибка добавления', true);
    }
}

async function editServer(serverId) {
    const server = serversData.find(s => s.id == serverId);
    if (server) {
        document.getElementById('modalTitle').textContent = '✏️ Редактировать сервер';
        document.getElementById('serverId').value = server.id;
        document.getElementById('serverName').value = server.name;
        document.getElementById('serverIpLmhz').value = server.ip_lmhz;
        document.getElementById('serverIpPiot').value = server.ip_piot || '';
        document.getElementById('serverPortLmhz').value = server.port_lmhz || 5995;
        document.getElementById('serverPortLm').value = server.port_lm || 5063;
        document.getElementById('serverPortPiot').value = server.port_piot || 51077;
        document.getElementById('serverEnabled').checked = server.enabled;
        document.getElementById('serverModal').classList.add('active');
    }
}

async function updateServer(serverId) {
    const name = document.getElementById('serverName').value;
    const ip_lmhz = document.getElementById('serverIpLmhz').value;
    const ip_piot = document.getElementById('serverIpPiot').value || ip_lmhz;
    const port_lmhz = parseInt(document.getElementById('serverPortLmhz').value) || 5995;
    const port_lm = parseInt(document.getElementById('serverPortLm').value) || 5063;
    const port_piot = parseInt(document.getElementById('serverPortPiot').value) || 51077;
    const enabled = document.getElementById('serverEnabled').checked;
    
    try {
        const response = await fetch(`${API_BASE}/servers/${serverId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                name, 
                ip_lmhz, 
                ip_piot, 
                port_lmhz, 
                port_lm, 
                port_piot, 
                enabled 
            })
        });
        const result = await response.json();
        if (result.success) {
            showToast('Сервер обновлен');
            closeModal();
            await loadServers();
        }
    } catch (error) {
        showToast('Ошибка обновления', true);
    }
}

async function deleteServer(serverId) {
    if (!confirm('Удалить сервер?')) return;
    try {
        const response = await fetch(`${API_BASE}/servers/${serverId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            showToast('Сервер удален');
            await loadServers();
        }
    } catch (error) {
        showToast('Ошибка удаления', true);
    }
}

async function importFromJson() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        const text = await file.text();
        try {
            const json = JSON.parse(text);
            const response = await fetch(`${API_BASE}/servers/import`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(json)
            });
            const result = await response.json();
            if (result.success) {
                showToast(result.message);
                await loadServers();
            }
        } catch (error) {
            showToast('Ошибка парсинга JSON', true);
        }
    };
    input.click();
}

function exportToCSV() {
    if (!serversData.length) {
        showToast('Нет данных для экспорта', true);
        return;
    }
    
    const headers = ['ID', 'Название', 'IP ЛМЧЗ', 'IP ПИОТ', 
                     'ЛМЧЗ_статус', 'ЛМЧЗ_версия', 'ЛМЧЗ_ошибка',
                     'ЛМ_статус', 'ЛМ_версия', 'ЛМ_ошибка',
                     'ПИОТ_статус', 'ПИОТ_версия', 'ПИОТ_ошибка', 'ПИОТ_лицензия_до'];
    
    const rows = serversData.map(server => [
        server.id, server.name, server.ip_lmhz, server.ip_piot || '',
        server.services.lmhz.status || '', server.services.lmhz.version || '', server.services.lmhz.error || '',
        server.services.lm.status || '', server.services.lm.version || '', server.services.lm.error || '',
        server.services.piot.status || '', server.services.piot.version || '', server.services.piot.error || '',
        server.services.piot.license_until || ''
    ]);
    
    const csvContent = [headers, ...rows]
        .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
        .join('\n');
    
    const blob = new Blob(["\uFEFF" + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.setAttribute('download', `servers_export_${new Date().toISOString().slice(0,19)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    showToast('Экспорт завершен');
}

function openAddModal() {
    document.getElementById('modalTitle').textContent = '➕ Добавить сервер';
    document.getElementById('serverId').value = '';
    document.getElementById('serverName').value = '';
    document.getElementById('serverIpLmhz').value = '';
    document.getElementById('serverIpPiot').value = '';
    document.getElementById('serverPortLmhz').value = '5995';
    document.getElementById('serverPortLm').value = '5063';
    document.getElementById('serverPortPiot').value = '51077';
    document.getElementById('serverEnabled').checked = true;
    document.getElementById('serverModal').classList.add('active');
}

function closeModal() {
    document.getElementById('serverModal').classList.remove('active');
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

function initEventListeners() {
    const serverForm = document.getElementById('serverForm');
    if (serverForm) {
        serverForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const id = document.getElementById('serverId').value;
            if (id) updateServer(id);
            else addServer();
        });
    }

    document.getElementById('refreshAllBtn').addEventListener('click', checkAllServers);
    document.getElementById('addServerBtn').addEventListener('click', openAddModal);
    document.getElementById('importJsonBtn').addEventListener('click', importFromJson);
    document.getElementById('exportCsvBtn').addEventListener('click', exportToCSV);
    
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value.toLowerCase();
            applyFilterAndSort();
        });
    }
    
    document.querySelectorAll('.close-modal, #cancelModalBtn').forEach(btn => {
        btn.addEventListener('click', closeModal);
    });
    
    const sortableHeaders = document.querySelectorAll('th[data-sort]');
    console.log('Found sortable headers:', sortableHeaders.length);
    sortableHeaders.forEach(th => {
        if (th._sortHandler) {
            th.removeEventListener('click', th._sortHandler);
        }
        const handler = () => {
            const column = th.getAttribute('data-sort');
            sortByColumn(column);
        };
        th._sortHandler = handler;
        th.addEventListener('click', handler);
        th.style.cursor = 'pointer';
    });
}

function startAutoRefresh() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(() => loadServers(false), 30000);
}

async function init() {
    initEventListeners();
    await loadServers(true);
    startAutoRefresh();
    updateSortIndicators();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

window.addEventListener('beforeunload', () => {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
});