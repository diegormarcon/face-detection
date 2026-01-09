# 🚀 Sistema de Detección YOLOv8 - GEO CAM

Sistema profesional de detección en tiempo real usando YOLOv8 (Ultralytics) diseñado para videovigilancia y sistemas de infracciones.

## 📋 Características

- ✅ **Detección precisa** de personas, autos, motos, buses y camiones
- ✅ **Filtrado avanzado** de falsos positivos
- ✅ **Estabilización temporal** de detecciones
- ✅ **Estilo profesional** tipo videovigilancia (Hikvision/iVMS)
- ✅ **HUD completo** con información en tiempo real
- ✅ **Soporte múltiple**: Webcam, archivos de video, streams RTSP
- ✅ **Optimizado** para producción
- ✅ **Listo para GEO CAM** - Sistema de infracciones

## 🛠️ Instalación

```bash
# Instalar dependencias
pip install -r requirements_yolo.txt

# O instalar manualmente
pip install ultralytics opencv-python torch numpy cvzone
```

## 🚀 Uso

### Webcam (cámara por defecto)
```bash
python3 examples/yolo_detection_system.py --source 0
```

### Archivo de video
```bash
python3 examples/yolo_detection_system.py --source video.mp4
```

### Stream RTSP
```bash
python3 examples/yolo_detection_system.py --source rtsp://usuario:password@ip:puerto/stream
```

### Con umbral de confianza personalizado
```bash
python3 examples/yolo_detection_system.py --source 0 --conf 0.6
```

## ⚙️ Configuración

### Parámetros de línea de comandos

- `--source`: Fuente de video
  - `0` o número: Índice de cámara USB
  - Ruta de archivo: `video.mp4`, `ruta/video.avi`
  - URL RTSP: `rtsp://...`
  - URL HTTP: `http://...`

- `--model`: Ruta al modelo YOLO (opcional)
  - Por defecto usa `yolov8n.pt` (se descarga automáticamente)
  - Otros modelos: `yolov8s.pt`, `yolov8m.pt`, `yolov8l.pt`, `yolov8x.pt`

- `--conf`: Umbral de confianza (0.0 - 1.0)
  - Por defecto: `0.5`
  - Mayor valor = menos falsos positivos pero puede perder detecciones

### Configuración en código

Editar `CONFIG` en `yolo_detection_system.py`:

```python
CONFIG = {
    'confidence_threshold': 0.5,  # Umbral mínimo
    'iou_threshold': 0.45,  # Umbral IoU para NMS
    'target_classes': ['person', 'car', 'motorcycle', 'bus', 'truck'],
    'min_area_ratio': 0.01,  # Área mínima (1% del frame)
    'stabilization_frames': 5,  # Frames para estabilización
}
```

## 🎨 Características Visuales

### Colores por Clase
- 🔴 **Personas**: Rojo
- 🟠 **Autos**: Naranja
- 🟣 **Motos**: Magenta
- 🔵 **Buses/Camiones**: Cyan

### HUD (Head-Up Display)
- **Panel Superior Izquierdo**:
  - FPS en tiempo real
  - Timestamp
  - Contador de detecciones por clase

- **Panel Inferior Derecho**:
  - Información del sistema
  - Estado GEO CAM

## 🔧 Optimizaciones

### Reducción de Falsos Positivos
1. **Umbrales de confianza diferenciados**:
   - Personas: 0.55 (más estricto)
   - Vehículos: 0.5
   - Otros: 0.5

2. **Filtro de área mínima**: Elimina detecciones muy pequeñas (< 1% del frame)

3. **Estabilización temporal**: Requiere que una detección aparezca en múltiples frames

4. **Filtrado por clases objetivo**: Solo detecta clases configuradas

### Rendimiento
- Procesamiento optimizado con YOLOv8
- Estabilización eficiente con deque
- Cálculo de FPS optimizado
- Soporte GPU (CUDA) si está disponible

## 📊 Modelos Disponibles

El sistema descarga automáticamente el modelo si no existe:

- `yolov8n.pt` - Nano (más rápido, menos preciso) - **Recomendado para tiempo real**
- `yolov8s.pt` - Small (balanceado)
- `yolov8m.pt` - Medium (más preciso)
- `yolov8l.pt` - Large (muy preciso, más lento)
- `yolov8x.pt` - XLarge (máxima precisión, muy lento)

## 🔌 Integración GEO CAM

El sistema está preparado para integrarse con GEO CAM:

```python
# Ejemplo de integración
from yolo_detection_system import YOLODetectionSystem

system = YOLODetectionSystem(source=0)

# En el loop de detección, puedes agregar:
for det in detections:
    if det['class'] == 'car' and det['confidence'] > 0.7:
        # Enviar a sistema de infracciones
        geo_cam.process_violation(det)
```

## ⌨️ Controles

- `q`: Salir del sistema
- `s`: Guardar captura del frame actual

## 📝 Notas

- El modelo YOLOv8n se descarga automáticamente la primera vez (~6MB)
- Para mejor rendimiento, usar GPU con CUDA
- El sistema funciona mejor con buena iluminación
- Ajustar `confidence_threshold` según necesidades

## 🐛 Solución de Problemas

### Error: "No se pudo abrir la fuente de video"
- Verificar que la cámara esté conectada
- Verificar permisos de acceso a la cámara
- Para RTSP, verificar credenciales y URL

### Falsos positivos
- Aumentar `--conf` (ej: `--conf 0.6`)
- Ajustar `min_area_ratio` en CONFIG
- Aumentar `stabilization_frames`

### Rendimiento bajo
- Usar modelo más pequeño (`yolov8n.pt`)
- Reducir resolución de entrada
- Usar GPU si está disponible

## 📄 Licencia

Sistema desarrollado para GEO CAM - Detección de Infracciones

---

**Versión**: 1.0  
**Última actualización**: 2025




