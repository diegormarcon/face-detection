// ========== GESTIÓN DE DETECCIONES ==========

let currentDetectionsPage = 0;
const detectionsPerPage = 12;

async function loadDetections() {
    const typeFilter = document.getElementById('detection-type-filter')?.value || '';
    const statusFilter = document.getElementById('detection-status-filter')?.value || '';
    
    let url = '/api/detections?limit=' + detectionsPerPage + '&offset=' + (currentDetectionsPage * detectionsPerPage);
    if (typeFilter) url += '&type=' + typeFilter;
    if (statusFilter) url += '&status=' + statusFilter;
    
    try {
        const response = await fetch(url);
        
        // Validar respuesta HTTP
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            displayDetections(data.detections);
            updateDetectionsPagination(data.total);
        }
    } catch (error) {
        console.error('Error cargando detecciones:', error);
        showToast('Error cargando detecciones', 'error');
    }
}

function displayDetections(detections) {
    const grid = document.getElementById('detections-grid');
    if (!grid) return;
    
    if (detections.length === 0) {
        grid.innerHTML = '<p style="text-align: center; color: #666; grid-column: 1/-1;">No hay detecciones</p>';
        return;
    }
    
    grid.innerHTML = detections.map(det => {
        // Construir URL de imagen correctamente
        let imageUrl = '';
        if (det.image_path) {
            // Si image_path es una ruta completa, extraer solo el nombre del archivo
            const filename = det.image_path.split('/').pop() || det.image_path.split('\\').pop();
            if (filename) {
                imageUrl = `/api/unknown_image/${encodeURIComponent(filename)}`;
            }
        }
        
        const date = new Date(det.timestamp).toLocaleString('es-AR');
        const statusBadge = getStatusBadge(det.status);
        const typeBadge = det.type === 'unknown' 
            ? '<span class="badge badge-danger">Desconocido</span>' 
            : '<span class="badge badge-success">Conocido</span>';
        
        const confidenceText = det.confidence !== null && det.confidence !== undefined 
            ? `<p style="margin: 5px 0; color: #666; font-size: 12px;"><strong>Confianza:</strong> ${(det.confidence * 100).toFixed(1)}%</p>` 
            : '';
        
        return `
            <div class="detection-card">
                ${imageUrl ? `
                    <img src="${imageUrl}" alt="Detección" class="detection-image" 
                         onerror="this.onerror=null; this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22%3E%3Crect fill=%22%23ddd%22 width=%22200%22 height=%22200%22/%3E%3Ctext fill=%22%23999%22 font-family=%22sans-serif%22 font-size=%2214%22 dy=%2210.5%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22%3ESin imagen%3C/text%3E%3C/svg%3E';"
                         style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px;">
                ` : `
                    <div style="width: 100%; height: 200px; background: #ddd; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #999;">
                        <i class="fas fa-image" style="font-size: 2rem;"></i>
                    </div>
                `}
                <div style="margin-top: 10px;">
                    ${typeBadge} ${statusBadge}
                    <p style="margin: 10px 0; color: #666; font-size: 12px;">${date}</p>
                    ${det.name ? `<p style="margin: 5px 0;"><strong>Nombre:</strong> ${det.name}</p>` : ''}
                    ${confidenceText}
                    ${det.notes ? `<p style="margin: 5px 0;"><strong>Notas:</strong> ${det.notes}</p>` : ''}
                    <div style="margin-top: 10px; display: flex; gap: 5px;">
                        <button onclick="editDetection('${det.id}')" class="btn btn-sm btn-primary">
                            <i class="fas fa-edit"></i> Editar
                        </button>
                        <button onclick="deleteDetection('${det.id}')" class="btn btn-sm btn-danger">
                            <i class="fas fa-trash"></i> Eliminar
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function getStatusBadge(status) {
    const badges = {
        'pending': '<span class="badge badge-warning">Pendiente</span>',
        'reviewed': '<span class="badge badge-info">Revisado</span>',
        'archived': '<span class="badge badge-secondary">Archivado</span>'
    };
    return badges[status] || badges['pending'];
}

function updateDetectionsPagination(total) {
    const pagination = document.getElementById('detections-pagination');
    if (!pagination) return;
    
    const totalPages = Math.ceil(total / detectionsPerPage);
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    pagination.innerHTML = `
        <button onclick="changeDetectionsPage(${currentDetectionsPage - 1})" 
                ${currentDetectionsPage === 0 ? 'disabled' : ''} class="btn btn-sm">
            <i class="fas fa-chevron-left"></i> Anterior
        </button>
        <span>Página ${currentDetectionsPage + 1} de ${totalPages}</span>
        <button onclick="changeDetectionsPage(${currentDetectionsPage + 1})" 
                ${currentDetectionsPage >= totalPages - 1 ? 'disabled' : ''} class="btn btn-sm">
            Siguiente <i class="fas fa-chevron-right"></i>
        </button>
    `;
}

function changeDetectionsPage(page) {
    currentDetectionsPage = page;
    loadDetections();
}

async function deleteDetection(id) {
    if (!confirm('¿Estás seguro de eliminar esta detección?')) return;
    
    try {
        const response = await fetch(`/api/detections/${id}`, { method: 'DELETE' });
        const data = await response.json();
        
        if (data.success) {
            showToast('Detección eliminada', 'success');
            loadDetections();
        } else {
            showToast('Error eliminando detección', 'error');
        }
    } catch (error) {
        console.error('Error eliminando detección:', error);
        showToast('Error eliminando detección', 'error');
    }
}

function editDetection(id) {
    // TODO: Implementar modal de edición
    showToast('Función de edición próximamente', 'info');
}

// ========== ESTADÍSTICAS KPI ==========

async function loadKPI() {
    try {
        const response = await fetch('/api/kpi');
        
        // Validar respuesta HTTP
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success && data.stats) {
            displayKPI(data.stats);
        }
    } catch (error) {
        console.error('Error cargando KPI:', error);
        showToast('Error cargando estadísticas', 'error');
    }
}

function displayKPI(stats) {
    const totalEl = document.getElementById('kpi-total');
    const unknownEl = document.getElementById('kpi-unknown');
    const knownEl = document.getElementById('kpi-known');
    const todayEl = document.getElementById('kpi-today');
    const weekEl = document.getElementById('kpi-week');
    const monthEl = document.getElementById('kpi-month');
    
    if (totalEl) totalEl.textContent = stats.total || 0;
    if (unknownEl) unknownEl.textContent = stats.unknown || 0;
    if (knownEl) knownEl.textContent = stats.known || 0;
    if (todayEl) todayEl.textContent = stats.today || 0;
    if (weekEl) weekEl.textContent = stats.this_week || 0;
    if (monthEl) monthEl.textContent = stats.this_month || 0;
}

// ========== CONFIGURACIÓN RTSP ==========

function loadVideoSourceSettings() {
    fetch('/api/get_video_source')
        .then(res => res.json())
        .then(data => {
            if (data.source) {
                if (typeof data.source === 'string') {
                    if (data.source.startsWith('rtsp://')) {
                        document.getElementById('video-source-type').value = 'rtsp';
                        document.getElementById('rtsp-url').value = data.source;
                    } else if (data.source.startsWith('http://') || data.source.startsWith('https://')) {
                        document.getElementById('video-source-type').value = 'http';
                        document.getElementById('http-url').value = data.source;
                    } else if (data.source.includes('/')) {
                        document.getElementById('video-source-type').value = 'file';
                        document.getElementById('video-file').value = data.source;
                    }
                } else {
                    document.getElementById('video-source-type').value = 'local';
                    document.getElementById('camera-index').value = data.source;
                }
                updateSourceTypeUI();
            }
        })
        .catch(err => console.error('Error cargando configuración:', err));
}

function updateSourceTypeUI() {
    const type = document.getElementById('video-source-type')?.value;
    if (!type) return;
    
    const localGroup = document.getElementById('local-camera-group');
    const rtspGroup = document.getElementById('rtsp-url-group');
    const httpGroup = document.getElementById('http-url-group');
    const fileGroup = document.getElementById('file-path-group');
    
    if (localGroup) localGroup.style.display = type === 'local' ? 'block' : 'none';
    if (rtspGroup) rtspGroup.style.display = type === 'rtsp' ? 'block' : 'none';
    if (httpGroup) httpGroup.style.display = type === 'http' ? 'block' : 'none';
    if (fileGroup) fileGroup.style.display = type === 'file' ? 'block' : 'none';
}

async function saveVideoSource() {
    const type = document.getElementById('video-source-type')?.value;
    if (!type) return;
    
    let source;
    
    switch(type) {
        case 'local':
            source = parseInt(document.getElementById('camera-index')?.value || 0);
            break;
        case 'rtsp':
            source = document.getElementById('rtsp-url')?.value || '';
            break;
        case 'http':
            source = document.getElementById('http-url')?.value || '';
            break;
        case 'file':
            source = document.getElementById('video-file')?.value || '';
            break;
    }
    
    if (!source && source !== 0) {
        showToast('Por favor completa todos los campos', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/set_video_source', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                source: source,
                auto_start: true  // Iniciar automáticamente
            })
        });
        
        const data = await response.json();
        const statusDiv = document.getElementById('video-source-status');
        
        if (data.success) {
            if (statusDiv) {
                statusDiv.className = 'status-message success';
                statusDiv.textContent = '✅ Fuente de video configurada correctamente';
            }
            showToast('Configuración guardada. Redirigiendo a Detección en Vivo...', 'success');
            
            // NUEVO: Cambiar automáticamente a la pestaña de Detección en Vivo
            setTimeout(() => {
                if (typeof window.switchTab === 'function') {
                    window.switchTab('stream');
                }
                // Actualizar el stream de video
                const videoStream = document.getElementById('video-stream');
                if (videoStream) {
                    videoStream.src = '/video_feed?' + new Date().getTime();
                }
            }, 1000);  // Esperar 1 segundo para que el usuario vea el mensaje
        } else {
            if (statusDiv) {
                statusDiv.className = 'status-message error';
                statusDiv.textContent = '❌ Error: ' + (data.error || 'No se pudo configurar');
            }
            showToast('Error guardando configuración', 'error');
        }
    } catch (error) {
        console.error('Error guardando configuración:', error);
        showToast('Error guardando configuración', 'error');
    }
}

// Modificar switchTab para cargar datos cuando se cambia de tab
const originalSwitchTab = window.switchTab || function(tabName) {};
window.switchTab = function(tabName) {
    originalSwitchTab(tabName);
    
    // Cargar datos cuando se cambia de tab
    if (tabName === 'detections') {
        loadDetections();
    } else if (tabName === 'kpi') {
        loadKPI();
    } else if (tabName === 'settings') {
        loadVideoSourceSettings();
    }
};

// Event listeners para nuevas funcionalidades
document.addEventListener('DOMContentLoaded', () => {
    // Detecciones
    const refreshDetections = document.getElementById('refresh-detections');
    if (refreshDetections) {
        refreshDetections.addEventListener('click', loadDetections);
    }
    
    const typeFilter = document.getElementById('detection-type-filter');
    const statusFilter = document.getElementById('detection-status-filter');
    if (typeFilter) typeFilter.addEventListener('change', loadDetections);
    if (statusFilter) statusFilter.addEventListener('change', loadDetections);
    
    // KPI
    const refreshKPI = document.getElementById('refresh-kpi');
    if (refreshKPI) {
        refreshKPI.addEventListener('click', loadKPI);
    }
    
    // Settings
    const videoSourceType = document.getElementById('video-source-type');
    if (videoSourceType) {
        videoSourceType.addEventListener('change', updateSourceTypeUI);
        updateSourceTypeUI();
    }
    
    const saveVideoSourceBtn = document.getElementById('save-video-source');
    if (saveVideoSourceBtn) {
        saveVideoSourceBtn.addEventListener('click', saveVideoSource);
    }
    
    const testVideoSourceBtn = document.getElementById('test-video-source');
    if (testVideoSourceBtn) {
        testVideoSourceBtn.addEventListener('click', () => {
            showToast('Probando conexión...', 'info');
            saveVideoSource();
        });
    }
});



