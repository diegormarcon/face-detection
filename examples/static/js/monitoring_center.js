// Centro de Monitoreo Multi-Cámara
// Gestión de múltiples streams de video

// Estado global de cámaras
let cameras = [];
let activeCamera = null;
let gridLayout = 4;

// Cargar cámaras al iniciar
document.addEventListener('DOMContentLoaded', function() {
    loadCameras();
    initializeMonitoringCenter();
});

// Inicializar Centro de Monitoreo
function initializeMonitoringCenter() {
    // Botón agregar cámara
    const addCameraBtn = document.getElementById('add-camera-btn');
    if (addCameraBtn) {
        addCameraBtn.addEventListener('click', () => openAddCameraModal());
    }
    
    // Selector de layout
    const gridLayoutSelect = document.getElementById('grid-layout-select');
    if (gridLayoutSelect) {
        gridLayoutSelect.addEventListener('change', (e) => {
            changeGridLayout(parseInt(e.target.value));
        });
    }
    
    // Botón pantalla completa
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', toggleFullscreen);
    }
    
    // Modal de agregar cámara
    setupAddCameraModal();
    
    // Inicializar grid
    renderStreamsGrid();
}

// Cargar cámaras guardadas
async function loadCameras() {
    // Intentar cargar cámaras predefinidas del servidor primero
    try {
        const response = await fetch('/api/predefined_cameras');
        const data = await response.json();
        
        if (data.success && data.cameras && data.cameras.length > 0) {
            // Convertir cámaras predefinidas al formato del monitoring center
            cameras = data.cameras.map((cam, index) => ({
                id: cam.id || `predefined_${index}`,
                name: cam.name,
                type: cam.type,
                source: cam.type === 'local' ? parseInt(cam.url) : cam.url,
                active: cam.enabled && index === 0, // Solo la primera cámara activa automáticamente
                autoStart: cam.enabled
            }));
            console.log('✅ Cámaras predefinidas cargadas:', cameras.length);
        } else {
            // Fallback: intentar cargar desde localStorage
            const savedCameras = localStorage.getItem('monitoring_cameras');
            if (savedCameras) {
                cameras = JSON.parse(savedCameras);
            } else {
                // Cámara por defecto
                cameras = [{
                    id: Date.now(),
                    name: 'Cámara Principal',
                    type: 'local',
                    source: 0,
                    active: false,
                    autoStart: true
                }];
            }
        }
        saveCameras();
    } catch (error) {
        console.error('Error cargando cámaras predefinidas:', error);
        // Fallback a localStorage
        const savedCameras = localStorage.getItem('monitoring_cameras');
        if (savedCameras) {
            cameras = JSON.parse(savedCameras);
        } else {
            cameras = [{
                id: Date.now(),
                name: 'Cámara Principal',
                type: 'local',
                source: 0,
                active: false,
                autoStart: true
            }];
            saveCameras();
        }
    }
    
    renderCamerasList();
    renderStreamsGrid();
}

// Guardar cámaras
function saveCameras() {
    localStorage.setItem('monitoring_cameras', JSON.stringify(cameras));
}

// Renderizar lista de cámaras (sidebar)
function renderCamerasList() {
    const camerasList = document.getElementById('cameras-list');
    if (!camerasList) return;
    
    camerasList.innerHTML = '';
    
    cameras.forEach(camera => {
        const cameraItem = document.createElement('div');
        cameraItem.className = `camera-item ${camera.active ? 'active' : ''}`;
        cameraItem.innerHTML = `
            <div class="camera-item-header">
                <span class="camera-item-name">${camera.name}</span>
                <span class="camera-item-status ${camera.active ? 'online' : 'offline'}">
                    ${camera.active ? 'Activa' : 'Inactiva'}
                </span>
            </div>
            <div class="camera-item-details">
                <i class="fas fa-${getCameraIcon(camera.type)}"></i>
                ${getCameraSourceLabel(camera)}
            </div>
            <div class="camera-item-controls">
                <button class="btn-toggle btn-${camera.active ? 'danger' : 'success'}" data-camera-id="${camera.id}">
                    <i class="fas fa-${camera.active ? 'stop' : 'play'}"></i>
                    ${camera.active ? 'Detener' : 'Iniciar'}
                </button>
                <button class="btn-edit btn-primary" data-camera-id="${camera.id}">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn-delete btn-danger" data-camera-id="${camera.id}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        camerasList.appendChild(cameraItem);
        
        // Event listeners para los botones
        const toggleBtn = cameraItem.querySelector('.btn-toggle');
        const editBtn = cameraItem.querySelector('.btn-edit');
        const deleteBtn = cameraItem.querySelector('.btn-delete');
        
        if (toggleBtn) toggleBtn.addEventListener('click', () => toggleCamera(camera.id));
        if (editBtn) editBtn.addEventListener('click', () => editCamera(camera.id));
        if (deleteBtn) deleteBtn.addEventListener('click', () => deleteCamera(camera.id));
    });
    
    updateActiveCamerasCount();
}

// Renderizar grid de streams
function renderStreamsGrid() {
    const streamsGrid = document.getElementById('streams-grid');
    if (!streamsGrid) return;
    
    streamsGrid.innerHTML = '';
    streamsGrid.setAttribute('data-layout', gridLayout);
    
    // Crear slots según el layout
    for (let i = 0; i < gridLayout; i++) {
        const streamCard = document.createElement('div');
        const camera = cameras[i];
        
        if (camera && camera.active) {
            streamCard.className = 'stream-card';
            streamCard.innerHTML = `
                <div class="stream-card-header">
                    <span class="stream-card-title">${camera.name}</span>
                    <div class="stream-card-controls">
                        <button class="btn-maximize" data-camera-id="${camera.id}" title="Maximizar">
                            <i class="fas fa-expand"></i>
                        </button>
                        <button class="btn-stop" data-camera-id="${camera.id}" title="Detener">
                            <i class="fas fa-stop"></i>
                        </button>
                    </div>
                </div>
                <img src="/video_feed?source=${encodeURIComponent(camera.source)}&camera_id=${camera.id}&t=${Date.now()}" 
                     alt="${camera.name}" 
                     onerror="handleStreamError(this, '${camera.id}')">
            `;
            
            // Event listeners para los controles
            const maxBtn = streamCard.querySelector('.btn-maximize');
            const stopBtn = streamCard.querySelector('.btn-stop');
            if (maxBtn) maxBtn.addEventListener('click', () => maximizeStream(camera.id));
            if (stopBtn) stopBtn.addEventListener('click', () => toggleCamera(camera.id));
            
        } else if (camera) {
            streamCard.className = 'stream-card empty';
            streamCard.innerHTML = `
                <div class="empty-slot">
                    <i class="fas fa-video-slash"></i>
                    <p>${camera.name}</p>
                    <button class="btn btn-primary btn-sm btn-start" data-camera-id="${camera.id}">
                        <i class="fas fa-play"></i> Iniciar
                    </button>
                </div>
            `;
            
            // Event listener para el botón de iniciar
            const startBtn = streamCard.querySelector('.btn-start');
            if (startBtn) startBtn.addEventListener('click', () => toggleCamera(camera.id));
            
        } else {
            streamCard.className = 'stream-card empty';
            streamCard.innerHTML = `
                <div class="empty-slot">
                    <i class="fas fa-plus-circle"></i>
                    <p>Slot vacío</p>
                    <button class="btn btn-success btn-sm btn-add-camera">
                        <i class="fas fa-plus"></i> Agregar Cámara
                    </button>
                </div>
            `;
            
            // Event listener para agregar cámara
            const addBtn = streamCard.querySelector('.btn-add-camera');
            if (addBtn) addBtn.addEventListener('click', () => openAddCameraModal());
        }
        
        streamsGrid.appendChild(streamCard);
    }
}

// Toggle cámara (activar/desactivar)
async function toggleCamera(cameraId) {
    const camera = cameras.find(c => c.id === cameraId);
    if (!camera) return;
    
    camera.active = !camera.active;
    
    if (camera.active) {
        // Iniciar stream (el stream se inicia automáticamente cuando se carga la imagen)
        showToast(`${camera.name} iniciada`, 'success');
    } else {
        // Detener stream
        showToast(`${camera.name} detenida`, 'info');
    }
    
    saveCameras();
    renderCamerasList();
    renderStreamsGrid();
}

// Cambiar layout del grid
function changeGridLayout(newLayout) {
    gridLayout = newLayout;
    renderStreamsGrid();
}

// Abrir modal de agregar cámara
function openAddCameraModal() {
    const modal = document.getElementById('add-camera-modal');
    if (modal) {
        modal.style.display = 'flex';
        document.getElementById('camera-name').value = '';
        document.getElementById('camera-type').value = 'local';
        updateCameraSourceFields();
    }
}

// Setup modal de agregar cámara
function setupAddCameraModal() {
    const modal = document.getElementById('add-camera-modal');
    if (!modal) return;
    
    // Cerrar modal
    const closeButtons = modal.querySelectorAll('.modal-close');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    });
    
    // Click fuera del modal
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // Cambio de tipo de cámara
    const cameraType = document.getElementById('camera-type');
    if (cameraType) {
        cameraType.addEventListener('change', updateCameraSourceFields);
    }
    
    // Guardar cámara
    const saveCameraBtn = document.getElementById('save-camera-btn');
    if (saveCameraBtn) {
        saveCameraBtn.addEventListener('click', saveNewCamera);
    }
}

// Actualizar campos según tipo de cámara
function updateCameraSourceFields() {
    const type = document.getElementById('camera-type')?.value;
    
    // Ocultar todos
    document.getElementById('camera-source-local').style.display = 'none';
    document.getElementById('camera-source-rtsp').style.display = 'none';
    document.getElementById('camera-source-http').style.display = 'none';
    document.getElementById('camera-source-file').style.display = 'none';
    
    // Mostrar el correspondiente
    if (type) {
        document.getElementById(`camera-source-${type}`).style.display = 'block';
    }
}

// Guardar nueva cámara
function saveNewCamera() {
    const name = document.getElementById('camera-name')?.value.trim();
    const type = document.getElementById('camera-type')?.value;
    const autoStart = document.getElementById('camera-auto-start')?.checked;
    
    if (!name) {
        showToast('El nombre es requerido', 'error');
        return;
    }
    
    let source;
    switch(type) {
        case 'local':
            source = parseInt(document.getElementById('camera-index-modal')?.value || 0);
            break;
        case 'rtsp':
            source = document.getElementById('camera-rtsp-url')?.value || '';
            break;
        case 'http':
            source = document.getElementById('camera-http-url')?.value || '';
            break;
        case 'file':
            source = document.getElementById('camera-file-path')?.value || '';
            break;
    }
    
    if (!source && source !== 0) {
        showToast('La fuente es requerida', 'error');
        return;
    }
    
    // Crear nueva cámara
    const newCamera = {
        id: Date.now(),
        name: name,
        type: type,
        source: source,
        active: false,
        autoStart: autoStart
    };
    
    cameras.push(newCamera);
    saveCameras();
    renderCamerasList();
    renderStreamsGrid();
    
    // Cerrar modal
    document.getElementById('add-camera-modal').style.display = 'none';
    showToast(`Cámara "${name}" agregada correctamente`, 'success');
    
    // Auto-iniciar si está marcado
    if (autoStart) {
        setTimeout(() => toggleCamera(newCamera.id), 500);
    }
}

// Eliminar cámara
function deleteCamera(cameraId) {
    if (!confirm('¿Estás seguro de eliminar esta cámara?')) return;
    
    const camera = cameras.find(c => c.id === cameraId);
    if (camera && camera.active) {
        toggleCamera(cameraId); // Detener si está activa
    }
    
    cameras = cameras.filter(c => c.id !== cameraId);
    saveCameras();
    renderCamerasList();
    renderStreamsGrid();
    showToast('Cámara eliminada', 'info');
}

// Editar cámara
function editCamera(cameraId) {
    showToast('Función de edición próximamente', 'info');
}

// Maximizar stream
function maximizeStream(cameraId) {
    const camera = cameras.find(c => c.id === cameraId);
    if (!camera) return;
    
    // Cambiar a layout de 1 cámara y mover esta cámara al inicio
    const cameraIndex = cameras.indexOf(camera);
    if (cameraIndex > 0) {
        cameras.splice(cameraIndex, 1);
        cameras.unshift(camera);
    }
    
    gridLayout = 1;
    document.getElementById('grid-layout-select').value = '1';
    renderStreamsGrid();
}

// Manejar error de stream
function handleStreamError(img, cameraId) {
    console.error(`Error cargando stream de cámara ${cameraId}`);
    img.src = '';
    img.alt = 'Error al cargar stream';
}

// Pantalla completa
function toggleFullscreen() {
    const container = document.querySelector('.streams-grid-container');
    if (!document.fullscreenElement) {
        container.requestFullscreen().catch(err => {
            console.error('Error al activar pantalla completa:', err);
        });
    } else {
        document.exitFullscreen();
    }
}

// Utilidades
function getCameraIcon(type) {
    const icons = {
        'local': 'video',
        'rtsp': 'broadcast-tower',
        'http': 'globe',
        'file': 'file-video'
    };
    return icons[type] || 'video';
}

function getCameraSourceLabel(camera) {
    switch(camera.type) {
        case 'local':
            return `Cámara ${camera.source}`;
        case 'rtsp':
        case 'http':
            return camera.source.substring(0, 30) + '...';
        case 'file':
            return camera.source.split('/').pop();
        default:
            return 'Fuente desconocida';
    }
}

function updateActiveCamerasCount() {
    const activeCount = cameras.filter(c => c.active).length;
    const countElement = document.getElementById('active-cameras-count');
    if (countElement) {
        countElement.textContent = activeCount;
    }
}

// Exportar funciones globales
window.toggleCamera = toggleCamera;
window.deleteCamera = deleteCamera;
window.editCamera = editCamera;
window.maximizeStream = maximizeStream;
window.handleStreamError = handleStreamError;
window.openAddCameraModal = openAddCameraModal;

