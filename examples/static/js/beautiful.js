// Variables globales
let isStreaming = false;
let isCapturing = false;
let captureStreamActive = false;
let capturedPhotoData = null;
let referenceFaces = [];
let referenceFacesData = [];
let currentAnalysis = null;
let lastUnknownAlert = 0;
let audioContext = null;
let fpsCounter = 0;
let lastFpsTime = Date.now();
let monitorInterval = null;

// Elementos del DOM
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const videoStream = document.getElementById('video-stream');
const videoPlaceholder = document.getElementById('video-placeholder');
const referenceCount = document.getElementById('reference-count');
const detectedCount = document.getElementById('detected-count');

// Tab elements
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

// Reference management
const addReferenceBtn = document.getElementById('add-reference-btn');
const captureReferenceBtn = document.getElementById('capture-reference-btn');
const referenceGrid = document.getElementById('reference-grid');
const addReferenceModal = document.getElementById('add-reference-modal');
const captureReferenceModal = document.getElementById('capture-reference-modal');
const referenceFileInput = document.getElementById('reference-file-input');
const referenceNameInput = document.getElementById('reference-name');
const saveReferenceBtn = document.getElementById('save-reference-btn');

// Capture elements
const startCaptureBtn = document.getElementById('start-capture-btn');
const capturePhotoBtn = document.getElementById('capture-photo-btn');
const stopCaptureBtn = document.getElementById('stop-capture-btn');
const captureStream = document.getElementById('capture-stream');
const capturePlaceholder = document.getElementById('capture-placeholder');
const capturedPhoto = document.getElementById('captured-photo');
const capturedImage = document.getElementById('captured-image');
const captureName = document.getElementById('capture-name');
const saveCaptureBtn = document.getElementById('save-capture-btn');
const retakePhotoBtn = document.getElementById('retake-photo-btn');

// Analysis
const analysisUploadArea = document.getElementById('analysis-upload-area');
const analysisFileInput = document.getElementById('analysis-file-input');
const analysisResults = document.getElementById('analysis-results');
const analysisImage = document.getElementById('analysis-image');
const analysisOverlay = document.getElementById('analysis-overlay');
const analysisFacesList = document.getElementById('analysis-faces-list');
const clearAnalysisBtn = document.getElementById('clear-analysis-btn');

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    addAnimations();
});

function initializeApp() {
    // Event listeners para tabs
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Event listeners para video (solo si existen - compatibilidad con nuevo layout)
    if (startBtn) {
        startBtn.addEventListener('click', startStream);
    }
    if (stopBtn) {
        stopBtn.addEventListener('click', stopStream);
    }

    // Event listeners para referencias (solo si existen)
    if (addReferenceBtn) {
        addReferenceBtn.addEventListener('click', openAddReferenceModal);
    }
    if (captureReferenceBtn) {
        captureReferenceBtn.addEventListener('click', openCaptureReferenceModal);
    }
    
    // Event listener para el área de upload de referencia
    const referenceUploadArea = document.getElementById('reference-upload-area');
    if (referenceUploadArea) {
        referenceUploadArea.addEventListener('click', () => referenceFileInput.click());
        referenceUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            referenceUploadArea.classList.add('dragover');
        });
        referenceUploadArea.addEventListener('dragleave', () => {
            referenceUploadArea.classList.remove('dragover');
        });
        referenceUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            referenceUploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                // Crear un DataTransfer para asignar múltiples archivos
                const dataTransfer = new DataTransfer();
                Array.from(files).forEach(file => dataTransfer.items.add(file));
                referenceFileInput.files = dataTransfer.files;
                handleReferenceFileSelect({ target: referenceFileInput });
            }
        });
    }
    
    referenceFileInput.addEventListener('change', handleReferenceFileSelect);
    saveReferenceBtn.addEventListener('click', saveReference);

    // Event listeners para captura
    startCaptureBtn.addEventListener('click', startCaptureStream);
    capturePhotoBtn.addEventListener('click', capturePhoto);
    stopCaptureBtn.addEventListener('click', stopCaptureStream);
    saveCaptureBtn.addEventListener('click', saveCapturedPhoto);
    retakePhotoBtn.addEventListener('click', retakePhoto);

    // Event listeners para análisis
    analysisUploadArea.addEventListener('click', () => analysisFileInput.click());
    analysisUploadArea.addEventListener('dragover', handleDragOver);
    analysisUploadArea.addEventListener('dragleave', handleDragLeave);
    analysisUploadArea.addEventListener('drop', handleDrop);
    analysisFileInput.addEventListener('change', handleAnalysisFileSelect);
    clearAnalysisBtn.addEventListener('click', clearAnalysis);

    // Cargar referencias
    loadReferenceFaces();
    loadPredefinedCameras();
}

// Cargar cámaras predefinidas
async function loadPredefinedCameras() {
    try {
        const response = await fetch('/api/predefined_cameras');
        const data = await response.json();
        
        if (data.success && data.cameras) {
            const select = document.getElementById('predefined-camera');
            if (select) {
                // Limpiar opciones existentes excepto la primera
                select.innerHTML = '<option value="">-- Seleccionar cámara predefinida --</option>';
                
                // Agregar cámaras predefinidas
                data.cameras.forEach(camera => {
                    if (camera.enabled) {
                        const option = document.createElement('option');
                        option.value = JSON.stringify({
                            id: camera.id,
                            url: camera.url,
                            type: camera.type
                        });
                        option.textContent = `${camera.name} (${camera.type.toUpperCase()})`;
                        select.appendChild(option);
                    }
                });
                
                // Event listener para cuando se selecciona una cámara predefinida
                select.addEventListener('change', function() {
                    if (this.value) {
                        const camera = JSON.parse(this.value);
                        
                        // Configurar automáticamente los campos según el tipo
                        const videoSourceType = document.getElementById('video-source-type');
                        const rtspUrl = document.getElementById('rtsp-url');
                        const cameraIndex = document.getElementById('camera-index');
                        
                        if (camera.type === 'rtsp') {
                            videoSourceType.value = 'rtsp';
                            rtspUrl.value = camera.url;
                            // Disparar evento change para mostrar el campo correcto
                            videoSourceType.dispatchEvent(new Event('change'));
                        } else if (camera.type === 'local') {
                            videoSourceType.value = 'local';
                            cameraIndex.value = camera.url;
                            videoSourceType.dispatchEvent(new Event('change'));
                        }
                        
                        showToast(`Cámara configurada: ${camera.id}`, 'info');
                    }
                });
            }
        }
    } catch (error) {
        console.error('Error cargando cámaras predefinidas:', error);
    }
}

function addAnimations() {
    // Animación de entrada para elementos
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeIn 0.6s ease forwards';
            }
        });
    });

    document.querySelectorAll('.stat-card, .reference-card, .face-result-card').forEach(el => {
        observer.observe(el);
    });
}

// Tab switching
function switchTab(tabName) {
    // Remover active de todos los tabs
    tabBtns.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.classList.remove('active'));

    // Activar tab seleccionado
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Cargar datos específicos del tab
    if (tabName === 'reference') {
        // Recargar referencias cuando se cambia al tab de referencias
        loadReferenceFaces();
    }

    // Animación de transición
    const activeContent = document.getElementById(`${tabName}-tab`);
    activeContent.style.opacity = '0';
    activeContent.style.transform = 'translateY(20px)';

    setTimeout(() => {
        activeContent.style.opacity = '1';
        activeContent.style.transform = 'translateY(0)';
    }, 100);
    
    // Cargar datos cuando se cambia de tab
    if (tabName === 'reference') {
        loadReferenceFaces();
    } else if (tabName === 'detections') {
        loadDetections();
    } else if (tabName === 'kpi') {
        loadKPI();
    } else if (tabName === 'settings') {
        loadVideoSourceSettings();
    }
}

// Control del stream
async function startStream() {
    try {
        showLoading(true);
        const response = await fetch('/start_stream');
        
        // Validar respuesta HTTP
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();

        if (data.success) {
            isStreaming = true;
            videoStream.src = '/video_feed';
            videoStream.style.display = 'block';
            videoPlaceholder.style.display = 'none';

            // Inicializar contexto de audio para alertas
            initAudioContext();

            // Agregar evento para contar FPS
            videoStream.onload = function() {
                incrementFPS();
            };
            
            // Monitorear el stream para detectar desconocidos
            monitorVideoStream();

            startBtn.disabled = true;
            stopBtn.disabled = false;

            // Animación de botones
            startBtn.style.transform = 'scale(0.95)';
            setTimeout(() => {
                startBtn.style.transform = 'scale(1)';
            }, 150);

            showToast('🎥 Stream iniciado correctamente', 'success');
        } else {
            showToast('❌ Error iniciando stream: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('❌ Error de conexión: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function stopStream() {
    // Limpiar intervalo de monitoreo
    if (monitorInterval) {
        clearInterval(monitorInterval);
        monitorInterval = null;
    }
    
    try {
        const response = await fetch('/stop_stream');
        
        // Validar respuesta HTTP
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();

        if (data.success) {
            isStreaming = false;
            videoStream.src = '';
            videoStream.style.display = 'none';
            videoPlaceholder.style.display = 'block';

            startBtn.disabled = false;
            stopBtn.disabled = true;

            // Animación de botones
            stopBtn.style.transform = 'scale(0.95)';
            setTimeout(() => {
                stopBtn.style.transform = 'scale(1)';
            }, 150);

            showToast('⏹️ Stream detenido', 'success');
        }
    } catch (error) {
        console.error('Error deteniendo stream:', error);
        showToast('❌ Error deteniendo stream: ' + error.message, 'error');
    }
}

// Gestión de referencias
async function loadReferenceFaces() {
    try {
        const response = await fetch('/api/reference_faces');
        
        // Validar respuesta HTTP
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();

        if (data.success) {
            referenceFaces = data.faces;
            referenceFacesData = data.faces_data || [];
            displayReferenceFaces();
            updateStats();
        } else {
            console.warn('API returned success=false:', data);
        }
    } catch (error) {
        console.error('Error cargando referencias:', error);
        // No mostrar toast aquí para evitar spam en la consola
    }
}

function displayReferenceFaces() {
    referenceGrid.innerHTML = '';

    if (referenceFaces.length === 0) {
        referenceGrid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 4rem; color: var(--text-muted);">
                <div style="width: 100px; height: 100px; background: linear-gradient(135deg, var(--primary-color), var(--accent-color)); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 2rem; animation: pulse 2s infinite;">
                    <i class="fas fa-user-plus" style="font-size: 2rem; color: white;"></i>
                </div>
                <h3 style="font-size: 1.5rem; margin-bottom: 1rem; color: var(--text-primary);">No hay caras de referencia</h3>
                <p style="margin-bottom: 2rem;">Agrega caras de referencia para mejorar el reconocimiento</p>
                <button onclick="openAddReferenceModal()" class="btn btn-primary">
                    <i class="fas fa-plus"></i>
                    <span>Agregar Primera Referencia</span>
                </button>
            </div>
        `;
        return;
    }

    referenceFaces.forEach((face, index) => {
        const faceCard = document.createElement('div');
        faceCard.className = 'reference-card';
        faceCard.style.animationDelay = `${index * 0.1}s`;

        // Buscar los datos de la imagen para esta cara
        const faceData = referenceFacesData.find(f => f.name === face);
        const imageUrl = faceData ? faceData.image_url : '';
        const imageHtml = imageUrl 
            ? `<img src="${imageUrl}" alt="${face}" class="reference-image-img">`
            : `<i class="fas fa-user"></i>`;

        faceCard.innerHTML = `
            <div class="reference-image">
                ${imageHtml}
            </div>
            <div class="reference-name">${face}</div>
            <div class="reference-status">Referencia Activa</div>
            <div class="reference-actions">
                <button class="delete-btn" onclick="deleteReference('${face}')">
                    <i class="fas fa-trash"></i>
                    <span>Eliminar</span>
                </button>
            </div>
        `;

        referenceGrid.appendChild(faceCard);
    });
}

function openAddReferenceModal() {
    addReferenceModal.classList.add('show');
    referenceFileInput.value = '';
    saveReferenceBtn.disabled = true;
    selectedFilesData = [];
    
    // Resetear el área de upload visualmente
    const referenceUploadArea = document.getElementById('reference-upload-area');
    if (referenceUploadArea) {
        referenceUploadArea.classList.remove('dragover');
    }
    
    // Ocultar contenedor de imágenes seleccionadas
    document.getElementById('selected-images-container').style.display = 'none';
    document.getElementById('selected-images-list').innerHTML = '';

    // Animación de entrada del modal
    const modal = addReferenceModal.querySelector('.modal-content');
    modal.style.transform = 'scale(0.9)';
    modal.style.opacity = '0';

    setTimeout(() => {
        modal.style.transform = 'scale(1)';
        modal.style.opacity = '1';
    }, 100);
}

function closeAddReferenceModal() {
    const modal = addReferenceModal.querySelector('.modal-content');
    modal.style.transform = 'scale(0.9)';
    modal.style.opacity = '0';

    setTimeout(() => {
        addReferenceModal.classList.remove('show');
    }, 200);
}

// Funciones para captura de fotos
function openCaptureReferenceModal() {
    captureReferenceModal.classList.add('show');
    captureName.value = '';
    capturedPhotoData = null;
    resetCaptureState();

    // Animación de entrada del modal
    const modal = captureReferenceModal.querySelector('.modal-content');
    modal.style.transform = 'scale(0.9)';
    modal.style.opacity = '0';

    setTimeout(() => {
        modal.style.transform = 'scale(1)';
        modal.style.opacity = '1';
    }, 100);
}

function closeCaptureReferenceModal() {
    stopCaptureStream();

    const modal = captureReferenceModal.querySelector('.modal-content');
    modal.style.transform = 'scale(0.9)';
    modal.style.opacity = '0';

    setTimeout(() => {
        captureReferenceModal.classList.remove('show');
        resetCaptureState();
    }, 200);
}

function resetCaptureState() {
    captureStream.src = '';
    captureStream.style.display = 'none';
    capturePlaceholder.style.display = 'block';
    capturedPhoto.style.display = 'none';
    capturedImage.src = '';

    startCaptureBtn.disabled = false;
    capturePhotoBtn.disabled = true;
    stopCaptureBtn.disabled = true;
    saveCaptureBtn.disabled = true;
    retakePhotoBtn.style.display = 'none';

    isCapturing = false;
    captureStreamActive = false;
    capturedPhotoData = null;
}

async function startCaptureStream() {
    try {
        showLoading(true);
        const response = await fetch('/start_stream');
        const data = await response.json();

        if (data.success) {
            isCapturing = true;
            captureStreamActive = true;
            captureStream.src = '/video_feed';
            captureStream.style.display = 'block';
            capturePlaceholder.style.display = 'none';

            startCaptureBtn.disabled = true;
            capturePhotoBtn.disabled = false;
            stopCaptureBtn.disabled = false;

            showToast('📷 Cámara iniciada para captura', 'success');
        } else {
            showToast('❌ Error iniciando cámara: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('❌ Error de conexión: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function stopCaptureStream() {
    try {
        const response = await fetch('/stop_stream');
        const data = await response.json();

        if (data.success) {
            isCapturing = false;
            captureStreamActive = false;
            captureStream.src = '';
            captureStream.style.display = 'none';
            capturePlaceholder.style.display = 'block';

            startCaptureBtn.disabled = false;
            capturePhotoBtn.disabled = true;
            stopCaptureBtn.disabled = true;

            showToast('⏹️ Cámara detenida', 'success');
        }
    } catch (error) {
        showToast('❌ Error deteniendo cámara: ' + error.message, 'error');
    }
}

function capturePhoto() {
    if (!captureStreamActive || !captureStream.src) {
        showToast('⚠️ La cámara no está activa', 'warning');
        return;
    }

    try {
        // Crear canvas para capturar la foto
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Establecer dimensiones del canvas
        canvas.width = captureStream.videoWidth || captureStream.naturalWidth;
        canvas.height = captureStream.videoHeight || captureStream.naturalHeight;

        // Dibujar el frame actual del video en el canvas
        ctx.drawImage(captureStream, 0, 0, canvas.width, canvas.height);

        // Convertir a base64
        const photoData = canvas.toDataURL('image/jpeg', 0.8);
        capturedPhotoData = photoData;

        // Mostrar la foto capturada
        capturedImage.src = photoData;
        capturedPhoto.style.display = 'block';

        // Actualizar botones
        capturePhotoBtn.disabled = true;
        saveCaptureBtn.disabled = false;
        retakePhotoBtn.style.display = 'inline-flex';

        showToast('📸 Foto capturada correctamente', 'success');

    } catch (error) {
        showToast('❌ Error capturando foto: ' + error.message, 'error');
    }
}

function retakePhoto() {
    capturedPhoto.style.display = 'none';
    capturedImage.src = '';
    capturedPhotoData = null;

    capturePhotoBtn.disabled = false;
    saveCaptureBtn.disabled = true;
    retakePhotoBtn.style.display = 'none';

    showToast('🔄 Listo para tomar otra foto', 'info');
}

async function saveCapturedPhoto() {
    const name = captureName.value.trim();

    if (!name) {
        showToast('⚠️ Por favor ingresa el nombre de la persona', 'warning');
        return;
    }

    if (!capturedPhotoData) {
        showToast('⚠️ No hay foto capturada', 'warning');
        return;
    }

    try {
        showLoading(true);

        // Convertir base64 a blob con tipo MIME correcto
        const response = await fetch(capturedPhotoData);
        const blob = await response.blob();

        // Crear un nuevo blob con tipo MIME explícito
        const imageBlob = new Blob([blob], { type: 'image/jpeg' });

        // Crear FormData
        const formData = new FormData();
        formData.append('file', imageBlob, `${name}_captured.jpg`);
        formData.append('name', name);

        const saveResponse = await fetch('/api/upload_reference', {
            method: 'POST',
            body: formData
        });

        const data = await saveResponse.json();

        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
            closeCaptureReferenceModal();
            await loadReferenceFaces();
        } else {
            showToast('❌ Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('❌ Error de conexión: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

let selectedFilesData = [];

function handleReferenceFileSelect(e) {
    const files = Array.from(e.target.files);
    
    if (files.length === 0) {
        saveReferenceBtn.disabled = true;
        selectedFilesData = [];
        document.getElementById('selected-images-container').style.display = 'none';
        return;
    }
    
    // Validar que todos sean imágenes
    const invalidFiles = files.filter(file => !file.type.startsWith('image/'));
    if (invalidFiles.length > 0) {
        showToast('⚠️ Algunos archivos no son imágenes válidas', 'warning');
        e.target.value = '';
        saveReferenceBtn.disabled = true;
        selectedFilesData = [];
        document.getElementById('selected-images-container').style.display = 'none';
        return;
    }
    
    // Procesar todas las imágenes seleccionadas
    selectedFilesData = [];
    const container = document.getElementById('selected-images-container');
    const list = document.getElementById('selected-images-list');
    container.style.display = 'block';
    list.innerHTML = '';
    
    files.forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = function(event) {
            const fileData = {
                file: file,
                preview: event.target.result,
                name: '',
                index: index
            };
            selectedFilesData.push(fileData);
            
            // Crear elemento para cada imagen
            const imageItem = document.createElement('div');
            imageItem.className = 'selected-image-item';
            imageItem.style.cssText = 'display: flex; gap: 1rem; align-items: center; padding: 1rem; background: var(--bg-secondary); border-radius: var(--radius); border: 1px solid var(--border);';
            
            imageItem.innerHTML = `
                <img src="${event.target.result}" alt="Preview" style="width: 80px; height: 80px; object-fit: cover; border-radius: var(--radius);">
                <div style="flex: 1;">
                    <input type="text" 
                           class="image-name-input" 
                           data-index="${index}"
                           placeholder="Nombre de la persona (ej: Juan Pérez)" 
                           style="width: 100%; padding: 0.75rem; border: 1px solid var(--border); border-radius: var(--radius); font-size: 0.9375rem;"
                           onchange="updateFileName(${index}, this.value)">
                    <p style="margin-top: 0.5rem; font-size: 0.875rem; color: var(--text-secondary);">${file.name}</p>
                </div>
            `;
            
            list.appendChild(imageItem);
            
            // Verificar si todas las imágenes tienen nombre
            checkAllNamesFilled();
        };
        reader.readAsDataURL(file);
    });
    
    showToast(`📷 ${files.length} imagen(es) seleccionada(s). Ingresa los nombres y guarda.`, 'success');
}

function updateFileName(index, name) {
    const fileData = selectedFilesData.find(f => f.index === index);
    if (fileData) {
        fileData.name = name.trim();
        checkAllNamesFilled();
    }
}

function checkAllNamesFilled() {
    const allFilled = selectedFilesData.length > 0 && selectedFilesData.every(f => f.name.length > 0);
    saveReferenceBtn.disabled = !allFilled;
    
    if (allFilled) {
        saveReferenceBtn.style.transform = 'scale(1.05)';
        setTimeout(() => {
            saveReferenceBtn.style.transform = 'scale(1)';
        }, 150);
    }
}

async function saveReference() {
    if (selectedFilesData.length === 0) {
        showToast('⚠️ Por favor selecciona al menos una imagen', 'warning');
        return;
    }
    
    // Verificar que todos tengan nombre
    const filesWithoutName = selectedFilesData.filter(f => !f.name || f.name.trim().length === 0);
    if (filesWithoutName.length > 0) {
        showToast('⚠️ Por favor ingresa el nombre para todas las imágenes', 'warning');
        return;
    }
    
    try {
        showLoading(true);
        let successCount = 0;
        let errorCount = 0;
        const errors = [];
        
        // Procesar cada imagen
        for (const fileData of selectedFilesData) {
            const formData = new FormData();
            formData.append('file', fileData.file);
            formData.append('name', fileData.name.trim());
            
            try {
                const response = await fetch('/api/upload_reference', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    successCount++;
                } else {
                    errorCount++;
                    errors.push(`${fileData.name}: ${data.error}`);
                }
            } catch (error) {
                errorCount++;
                errors.push(`${fileData.name}: Error de conexión`);
            }
        }
        
        // Mostrar resultados
        if (successCount > 0) {
            showToast(`✅ ${successCount} referencia(s) guardada(s) correctamente`, 'success');
        }
        
        if (errorCount > 0) {
            const errorMsg = errors.slice(0, 3).join(', ');
            const moreErrors = errors.length > 3 ? ` y ${errors.length - 3} más` : '';
            showToast(`⚠️ ${errorCount} error(es): ${errorMsg}${moreErrors}`, 'warning');
        }
        
        if (successCount > 0) {
            closeAddReferenceModal();
            await loadReferenceFaces();
        }
    } catch (error) {
        showToast('❌ Error procesando las imágenes: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function deleteReference(name) {
    if (!confirm(`¿Estás seguro de que quieres eliminar la referencia "${name}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/delete_reference/${name}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
            loadReferenceFaces();
        } else {
            showToast('❌ Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('❌ Error de conexión: ' + error.message, 'error');
    }
}

// Análisis de imágenes
function handleDragOver(e) {
    e.preventDefault();
    analysisUploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    analysisUploadArea.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    analysisUploadArea.classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleAnalysisFile(files[0]);
    }
}

function handleAnalysisFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleAnalysisFile(file);
    }
}

function handleAnalysisFile(file) {
    if (!file.type.startsWith('image/')) {
        showToast('⚠️ Por favor selecciona un archivo de imagen válido', 'error');
        return;
    }

    analyzeImage(file);
}

async function analyzeImage(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        showLoading(true);

        const response = await fetch('/api/analyze_image', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            currentAnalysis = data;
            displayAnalysisResults(data);
            showToast(`🔍 Análisis completado: ${data.faces_count} cara(s) detectada(s)`, 'success');
        } else {
            showToast('❌ Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('❌ Error de conexión: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function displayAnalysisResults(data) {
    // Mostrar imagen
    analysisImage.src = data.image;

    // Configurar canvas para overlay
    const canvas = analysisOverlay;
    const ctx = canvas.getContext('2d');

    analysisImage.onload = function() {
        canvas.width = analysisImage.offsetWidth;
        canvas.height = analysisImage.offsetHeight;
        drawFaceBoxes(data.faces, data.image_size);
    };

    // Mostrar detalles de caras
    displayAnalysisFaces(data.faces);

    // Mostrar resultados con animación
    analysisResults.style.display = 'block';
    analysisResults.style.opacity = '0';
    analysisResults.style.transform = 'translateY(20px)';

    setTimeout(() => {
        analysisResults.style.opacity = '1';
        analysisResults.style.transform = 'translateY(0)';
    }, 100);
}

function drawFaceBoxes(faces, imageSize) {
    const canvas = analysisOverlay;
    const ctx = canvas.getContext('2d');

    // Limpiar canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Calcular escala
    const scaleX = canvas.width / imageSize.width;
    const scaleY = canvas.height / imageSize.height;

    faces.forEach((face, index) => {
        const { top, right, bottom, left } = face.location;

        // Escalar coordenadas
        const x = left * scaleX;
        const y = top * scaleY;
        const width = (right - left) * scaleX;
        const height = (bottom - top) * scaleY;

        // Determinar color y etiqueta
        let color, label;
        if (face.is_known) {
            color = '#4ade80'; // Verde para conocido
            label = `${face.match} (${(face.confidence * 100).toFixed(1)}%)`;
        } else {
            color = '#f87171'; // Rojo para desconocido
            label = 'Desconocido';
        }

        // Dibujar caja con animación
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, width, height);

        // Dibujar fondo semi-transparente
        ctx.fillStyle = color + '20';
        ctx.fillRect(x, y, width, height);

        // Dibujar etiqueta con fondo
        ctx.fillStyle = color;
        ctx.font = 'bold 12px Poppins, sans-serif';
        const textWidth = ctx.measureText(label).width;
        ctx.fillRect(x, y - 25, textWidth + 10, 20);
        ctx.fillStyle = 'white';
        ctx.fillText(label, x + 5, y - 10);
    });
}

function displayAnalysisFaces(faces) {
    analysisFacesList.innerHTML = '';

    faces.forEach((face, index) => {
        const faceCard = document.createElement('div');
        faceCard.className = `face-result-card ${face.is_known ? 'known' : 'unknown'}`;
        faceCard.style.animationDelay = `${index * 0.1}s`;

        const confidenceClass = face.confidence > 0.8 ? '' :
                              face.confidence > 0.6 ? 'low' : 'very-low';

        faceCard.innerHTML = `
            <div class="face-result-header">
                <div class="face-result-name">
                    ${face.is_known ? face.match : 'Desconocido'}
                </div>
                <div class="face-result-confidence ${confidenceClass}">
                    ${face.is_known ? (face.confidence * 100).toFixed(1) + '%' : 'N/A'}
                </div>
            </div>
            <div class="face-result-info">
                <div class="face-result-info-item">
                    <span>ID:</span>
                    <span>${face.id}</span>
                </div>
                <div class="face-result-info-item">
                    <span>Estado:</span>
                    <span>${face.is_known ? 'Conocido' : 'Desconocido'}</span>
                </div>
                <div class="face-result-info-item">
                    <span>Posición X:</span>
                    <span>${face.location.left}px</span>
                </div>
                <div class="face-result-info-item">
                    <span>Posición Y:</span>
                    <span>${face.location.top}px</span>
                </div>
                <div class="face-result-info-item">
                    <span>Ancho:</span>
                    <span>${face.location.right - face.location.left}px</span>
                </div>
                <div class="face-result-info-item">
                    <span>Alto:</span>
                    <span>${face.location.bottom - face.location.top}px</span>
                </div>
            </div>
        `;

        analysisFacesList.appendChild(faceCard);
    });
}

function clearAnalysis() {
    analysisImage.src = '';
    analysisOverlay.getContext('2d').clearRect(0, 0, analysisOverlay.width, analysisOverlay.height);
    analysisFacesList.innerHTML = '';
    analysisResults.style.display = 'none';
    analysisFileInput.value = '';
    currentAnalysis = null;

    showToast('🗑️ Análisis limpiado', 'success');
}

function updateStats() {
    referenceCount.textContent = referenceFaces.length;
    if (currentAnalysis) {
        detectedCount.textContent = currentAnalysis.faces_count;
    }
}

function showLoading(show) {
    // Implementar loading state con animación
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loading-overlay';
    loadingOverlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
        backdrop-filter: blur(10px);
    `;

    if (show) {
        loadingOverlay.innerHTML = `
            <div style="text-align: center; color: white;">
                <div style="width: 60px; height: 60px; border: 4px solid rgba(255, 255, 255, 0.3); border-top: 4px solid white; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 1rem;"></div>
                <h3 style="margin-bottom: 0.5rem;">Procesando...</h3>
                <p>Por favor espera</p>
            </div>
        `;
        document.body.appendChild(loadingOverlay);
    } else {
        const existing = document.getElementById('loading-overlay');
        if (existing) {
            existing.remove();
        }
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = getToastIcon(type);
    toast.innerHTML = `
        <i class="${icon}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    // Auto-remover después de 5 segundos
    setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        toast.style.opacity = '0';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}

function getToastIcon(type) {
    switch (type) {
        case 'success': return 'fas fa-check-circle';
        case 'error': return 'fas fa-exclamation-circle';
        case 'warning': return 'fas fa-exclamation-triangle';
        default: return 'fas fa-info-circle';
    }
}

// Event listeners adicionales
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeAddReferenceModal();
        closeCaptureReferenceModal();
    }
});

// Cerrar modal al hacer clic fuera
addReferenceModal.addEventListener('click', function(e) {
    if (e.target === addReferenceModal) {
        closeAddReferenceModal();
    }
});

captureReferenceModal.addEventListener('click', function(e) {
    if (e.target === captureReferenceModal) {
        closeCaptureReferenceModal();
    }
});

// Enter para guardar referencia (solo si el elemento existe)
if (referenceNameInput) {
    referenceNameInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            saveReference();
        }
    });
}

captureName.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
        saveCapturedPhoto();
    }
});

// Funciones para el header mejorado
function updateHeaderTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const timeElement = document.getElementById('header-time');
    if (timeElement) {
        timeElement.textContent = timeString;
    }
}

function updateFPS() {
    const now = Date.now();
    const fpsElement = document.getElementById('fps-count');
    if (fpsElement) {
        fpsElement.textContent = fpsCounter;
    }
    fpsCounter = 0;
    lastFpsTime = now;
}

function incrementFPS() {
    if (isStreaming) {
        fpsCounter++;
    }
}

// Actualizar reloj cada segundo
setInterval(updateHeaderTime, 1000);
updateHeaderTime();

// Actualizar FPS cada segundo
setInterval(updateFPS, 1000);

// Funciones para alerta sonora
function initAudioContext() {
    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
    } catch (e) {
        console.warn('AudioContext no disponible:', e);
    }
}

function playAlertSound() {
    if (!audioContext) {
        initAudioContext();
    }
    
    if (!audioContext) return;
    
    try {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Frecuencia de alerta (tono de advertencia)
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
        
        // Repetir el sonido 2 veces
        setTimeout(() => {
            if (audioContext) {
                const oscillator2 = audioContext.createOscillator();
                const gainNode2 = audioContext.createGain();
                
                oscillator2.connect(gainNode2);
                gainNode2.connect(audioContext.destination);
                
                oscillator2.frequency.value = 800;
                oscillator2.type = 'sine';
                
                gainNode2.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                
                oscillator2.start(audioContext.currentTime);
                oscillator2.stop(audioContext.currentTime + 0.5);
            }
        }, 300);
    } catch (e) {
        console.warn('Error reproduciendo sonido:', e);
    }
}

// Monitorear el stream de video para detectar desconocidos
function monitorVideoStream() {
    // Limpiar intervalo anterior si existe
    if (monitorInterval) {
        clearInterval(monitorInterval);
    }
    
    // Verificar cada 1.5 segundos si hay desconocidos
    monitorInterval = setInterval(() => {
        if (!isStreaming || !videoStream.src) {
            if (monitorInterval) {
                clearInterval(monitorInterval);
                monitorInterval = null;
            }
            return;
        }
        
        // Analizar el frame actual buscando el texto "Desconocido"
        // Usamos un canvas para analizar el contenido
        try {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = videoStream.videoWidth || 640;
            canvas.height = videoStream.videoHeight || 480;
            
            if (canvas.width > 0 && canvas.height > 0) {
                ctx.drawImage(videoStream, 0, 0, canvas.width, canvas.height);
                
                // Buscar píxeles rojos en la parte inferior (donde está la etiqueta "Desconocido")
                // Método simple: buscar área roja en la parte inferior del frame
                const imageData = ctx.getImageData(0, canvas.height - 100, canvas.width, 100);
                const data = imageData.data;
                let redPixels = 0;
                
                // Contar píxeles rojos (R > 200, G < 50, B < 50)
                for (let i = 0; i < data.length; i += 4) {
                    const r = data[i];
                    const g = data[i + 1];
                    const b = data[i + 2];
                    if (r > 200 && g < 50 && b < 50) {
                        redPixels++;
                    }
                }
                
                // Si hay suficientes píxeles rojos, probablemente hay un desconocido
                if (redPixels > 500) {
                    const timeSinceLastAlert = Date.now() - lastUnknownAlert;
                    if (timeSinceLastAlert > 3000) { // Evitar spam de alertas (3 segundos)
                        playAlertSound();
                        lastUnknownAlert = Date.now();
                        showToast('⚠️ ALERTA: Persona desconocida detectada', 'warning');
                    }
                }
            }
        } catch (e) {
            // Ignorar errores silenciosamente
        }
    }, 1500);
}

// Añadir estilos CSS para animaciones
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .reference-card, .face-result-card {
        opacity: 0;
        transform: translateY(20px);
        animation: fadeInUp 0.6s ease forwards;
    }

    @keyframes fadeInUp {
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes pulse-alert {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
`;
document.head.appendChild(style);
