const API_BASE = '/api';

let devicesData = [];
let autoRefreshInterval = null;

function formatTimestamp(ts) {
    if (!ts) return '--';
    const date = new Date(ts * 1000);
    return date.toLocaleString('zh-CN');
}

function formatValue(value, unit) {
    if (value === null || value === undefined) return '--';
    const formatted = typeof value === 'number' ? value.toFixed(2) : String(value);
    return unit ? `${formatted} ${unit}` : formatted;
}

function getQualityClass(quality) {
    if (!quality) return '';
    return `quality-${quality.toLowerCase()}`;
}

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (connected) {
        statusEl.textContent = '已连接';
        statusEl.className = 'status-indicator connected';
    } else {
        statusEl.textContent = '未连接';
        statusEl.className = 'status-indicator disconnected';
    }
}

function updateLastUpdate() {
    const el = document.getElementById('last-update');
    el.textContent = `最后更新: ${new Date().toLocaleTimeString('zh-CN')}`;
}

async function fetchStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        if (!response.ok) throw new Error('Failed to fetch stats');
        const stats = await response.json();
        
        document.getElementById('reading-count').textContent = 
            stats.storage?.total_readings || 0;
        
        return stats;
    } catch (error) {
        console.error('Error fetching stats:', error);
        return null;
    }
}

async function fetchDevices() {
    try {
        const response = await fetch(`${API_BASE}/devices/latest`);
        if (!response.ok) throw new Error('Failed to fetch devices');
        const data = await response.json();
        
        devicesData = data.devices || [];
        updateDevicesGrid(devicesData);
        updateConnectionStatus(true);
        updateLastUpdate();
        
        document.getElementById('device-count').textContent = devicesData.length;
        
        let totalPoints = 0;
        devicesData.forEach(device => {
            totalPoints += (device.standard_points?.length || 0);
        });
        document.getElementById('point-count').textContent = totalPoints;
        
    } catch (error) {
        console.error('Error fetching devices:', error);
        updateConnectionStatus(false);
        document.getElementById('devices-container').innerHTML = 
            '<div class="no-data">加载失败，请检查服务状态</div>';
    }
}

function updateDevicesGrid(devices) {
    const container = document.getElementById('devices-container');
    
    if (!devices || devices.length === 0) {
        container.innerHTML = '<div class="no-data">暂无设备数据</div>';
        return;
    }
    
    const filterText = document.getElementById('device-filter').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    
    const filteredDevices = devices.filter(device => {
        const matchText = !filterText || 
            device.asset.toLowerCase().includes(filterText) ||
            device.service_name?.toLowerCase().includes(filterText);
        
        const matchStatus = !statusFilter || 
            device.device_status?.toLowerCase() === statusFilter;
        
        return matchText && matchStatus;
    });
    
    if (filteredDevices.length === 0) {
        container.innerHTML = '<div class="no-data">没有匹配的设备</div>';
        return;
    }
    
    container.innerHTML = filteredDevices.map(device => {
        const status = device.device_status || 'unknown';
        const statusClass = status.toLowerCase();
        const points = device.standard_points || [];
        const previewPoints = points.slice(0, 3);
        
        return `
            <div class="device-card" data-device='${JSON.stringify(device).replace(/'/g, "&#39;")}'>
                <div class="device-header">
                    <span class="device-name">${device.asset}</span>
                    <span class="device-status ${statusClass}">${status}</span>
                </div>
                <div class="device-info">
                    <div>服务: ${device.service_name || '--'}</div>
                    <div>点位数: ${points.length}</div>
                    <div>更新: ${formatTimestamp(device.timestamp)}</div>
                </div>
                ${previewPoints.length > 0 ? `
                    <div class="device-points-preview">
                        ${previewPoints.map(p => `
                            <div class="point-preview">
                                <span class="point-name">${p.point_name}</span>
                                <span class="point-value">${formatValue(p.value, p.unit)}</span>
                            </div>
                        `).join('')}
                        ${points.length > 3 ? `<div style="color: #6c757d; font-size: 12px;">还有 ${points.length - 3} 个点位...</div>` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
    
    container.querySelectorAll('.device-card').forEach(card => {
        card.addEventListener('click', () => {
            const device = JSON.parse(card.dataset.device);
            showDeviceModal(device);
        });
    });
}

function showDeviceModal(device) {
    const modal = document.getElementById('device-modal');
    
    document.getElementById('modal-device-name').textContent = device.asset;
    document.getElementById('modal-device-id').textContent = device.asset;
    document.getElementById('modal-service-name').textContent = device.service_name || '--';
    document.getElementById('modal-device-status').textContent = device.device_status || 'unknown';
    document.getElementById('modal-last-update').textContent = formatTimestamp(device.timestamp);
    
    const pointsContainer = document.getElementById('points-container');
    const points = device.standard_points || [];
    
    if (points.length === 0) {
        pointsContainer.innerHTML = '<div class="no-data">暂无点位数据</div>';
    } else {
        pointsContainer.innerHTML = points.map(p => `
            <div class="point-item">
                <div>
                    <div class="point-item-name">${p.point_name}</div>
                    <div class="point-item-meta">
                        类型: ${p.data_type || '--'} | 
                        质量: <span class="${getQualityClass(p.quality)}">${p.quality || '--'}</span>
                    </div>
                </div>
                <div class="point-item-value">${formatValue(p.value, p.unit)}</div>
            </div>
        `).join('');
    }
    
    modal.classList.add('show');
}

function closeModal() {
    document.getElementById('device-modal').classList.remove('show');
}

function showConfigMessage(message, isError = false) {
    const msgEl = document.getElementById('config-message');
    msgEl.textContent = message;
    msgEl.className = `config-message ${isError ? 'error' : 'success'}`;
    msgEl.style.display = 'block';
    setTimeout(() => {
        msgEl.style.display = 'none';
    }, 5000);
}

function getApiToken() {
    return document.getElementById('api-token').value.trim();
}

async function uploadConfig(file) {
    const token = getApiToken();
    if (!token) {
        showConfigMessage('请输入 API Token', true);
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/config/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        const result = await response.json();

        if (response.ok && result.success) {
            showConfigMessage(result.message);
            if (result.validation_errors && result.validation_errors.length > 0) {
                console.warn('配置警告:', result.validation_errors);
            }
        } else {
            showConfigMessage(result.message || result.detail || '上传失败', true);
            if (result.validation_errors) {
                console.error('验证错误:', result.validation_errors);
            }
        }
    } catch (error) {
        showConfigMessage(`上传失败: ${error.message}`, true);
    }
}

async function downloadConfig() {
    const token = getApiToken();
    if (!token) {
        showConfigMessage('请输入 API Token', true);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/config/download`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const error = await response.json();
            showConfigMessage(error.detail || '下载失败', true);
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'config.yaml';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        showConfigMessage('配置文件下载成功');
    } catch (error) {
        showConfigMessage(`下载失败: ${error.message}`, true);
    }
}

function initEventListeners() {
    document.getElementById('refresh-btn').addEventListener('click', () => {
        fetchDevices();
        fetchStats();
    });
    
    document.getElementById('device-filter').addEventListener('input', () => {
        updateDevicesGrid(devicesData);
    });
    
    document.getElementById('status-filter').addEventListener('change', () => {
        updateDevicesGrid(devicesData);
    });
    
    document.querySelector('.modal-close').addEventListener('click', closeModal);
    
    document.getElementById('device-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            closeModal();
        }
    });
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });

    document.getElementById('upload-config-btn').addEventListener('click', () => {
        document.getElementById('config-file-input').click();
    });

    document.getElementById('config-file-input').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            uploadConfig(file);
            e.target.value = '';
        }
    });

    document.getElementById('download-config-btn').addEventListener('click', downloadConfig);
}

function startAutoRefresh(interval = 10000) {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    autoRefreshInterval = setInterval(() => {
        fetchDevices();
        fetchStats();
    }, interval);
}

async function init() {
    initEventListeners();
    await fetchDevices();
    await fetchStats();
    startAutoRefresh();
    
    const loadingEl = document.getElementById('initial-loading');
    if (loadingEl) {
        loadingEl.classList.add('hidden');
        setTimeout(() => loadingEl.remove(), 300);
    }
}

document.addEventListener('DOMContentLoaded', init);
