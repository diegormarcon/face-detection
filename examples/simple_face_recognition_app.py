#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import face_recognition
import cv2
import numpy as np
import base64
import io
import os

# Solucionar conflictos de librerías en macOS (OpenMP/BLAS)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1" # Limitar hilos para evitar trace traps

from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from PIL import Image
import json
import threading
import time
import gc
from datetime import datetime
import subprocess
import shutil

# Importar Ultralytics YOLO de forma diferida para evitar conflictos en macOS
YOLO_AVAILABLE = False
YOLO = None

def init_yolo():
    """Inicializar YOLO de forma diferida"""
    global YOLO, YOLO_AVAILABLE, yolo_model
    try:
        from ultralytics import YOLO as YOLO_CLS
        YOLO = YOLO_CLS
        YOLO_AVAILABLE = True
        print("✅ Ultralytics YOLO cargado exitosamente")
        
        # Inicializar el modelo aquí forzando CPU para evitar conflictos en macOS
        model_path = "yolov8n-seg.pt"
        if os.path.exists(model_path):
            yolo_model = YOLO(model_path)
            yolo_model.to('cpu') # Forzar CPU
            print(f"✅ Modelo YOLOv8-seg cargado en CPU desde: {model_path}")
        else:
            print("📥 Descargando modelo YOLOv8n-seg...")
            yolo_model = YOLO('yolov8n-seg.pt')
            yolo_model.to('cpu') # Forzar CPU
            print("✅ Modelo YOLOv8n-seg descargado y cargado en CPU")
            
    except ImportError:
        YOLO_AVAILABLE = False
        print("⚠️ Ultralytics no disponible")
    except Exception as e:
        print(f"⚠️ Error inicializando YOLO: {e}")

# Importar soporte para HEIF
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
    print("Soporte HEIF habilitado")
except ImportError:
    HEIF_SUPPORT = False
    print("Soporte HEIF no disponible")

# Importar MediaPipe Face Mesh para mejor detección y segmentación
MEDIAPIPE_AVAILABLE = False
mp_face_mesh = None
mp_drawing = None
mp_drawing_styles = None
face_mesh = None  # Instancia global de FaceMesh

# MediaPipe desactivado para evitar inestabilidad en macOS
"""
try:
    # Intentar importar MediaPipe (versión estándar)
    import mediapipe as mp
    # ... (resto del código de mediapipe comentado)
"""

app = Flask(__name__)

# Configuración - Usar rutas absolutas basadas en la ubicación del script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
REFERENCE_FOLDER = os.path.join(BASE_DIR, 'reference_faces')
UNKNOWN_FACES_FOLDER = os.path.join(BASE_DIR, 'unknown_faces')
DETECTIONS_DB = os.path.join(BASE_DIR, 'detections_db.json')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Crear directorios si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REFERENCE_FOLDER, exist_ok=True)
os.makedirs(UNKNOWN_FACES_FOLDER, exist_ok=True)

# Variables globales para la cámara
camera = None
camera_source = 0  # Por defecto webcam local (0), puede ser RTSP URL
camera_lock = threading.Lock()
is_streaming = False

# Control para activar/desactivar la detección de objetos
OBJECT_DETECTION_ENABLED = True 

# Lock para inferencia YOLO (evitar segmentation faults en multi-threading)
yolo_lock = threading.Lock()

# Lock para reconocimiento facial (evitar trace traps en macOS con dlib)
face_lock = threading.Lock()

# Sistema Multi-Cámara para Centro de Monitoreo
active_cameras = {}  # {camera_id: {'cap': cv2.VideoCapture, 'source': source, 'lock': threading.Lock()}}
cameras_lock = threading.Lock()
MAX_ACTIVE_CAMERAS = 4 # Límite para evitar agotar memoria en Mac

# Pool de cámaras compartidas para evitar conflictos en macOS
camera_pool = {} # {source: {'cap': cap, 'lock': lock, 'users': count}}
pool_lock = threading.Lock()

def get_shared_cap(source):
    """Obtener una instancia compartida de VideoCapture para una fuente específica"""
    with pool_lock:
        if source not in camera_pool:
            print(f"🔌 Abriendo nueva conexión compartida para: {source}")
            if isinstance(source, str) and source.startswith('rtsp://'):
                # Usar backend FFmpeg para RTSP
                cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
            elif isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
                # Usar AVFoundation para cámaras locales en macOS
                idx = int(source)
                cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            else:
                cap = cv2.VideoCapture(source)
            
            if not cap or not cap.isOpened():
                print(f"❌ No se pudo abrir la fuente: {source}")
                return None, None
            
            camera_pool[source] = {
                'cap': cap, 
                'lock': threading.Lock(), 
                'users': 0,
                'last_frame': None,
                'last_time': 0
            }
        
        camera_pool[source]['users'] += 1
        return camera_pool[source]['cap'], camera_pool[source]['lock']

def release_shared_cap(source):
    """Liberar el uso de una cámara compartida"""
    with pool_lock:
        if source in camera_pool:
            camera_pool[source]['users'] -= 1
            if camera_pool[source]['users'] <= 0:
                print(f"🔌 Cerrando conexión compartida: {source}")
                camera_pool[source]['cap'].release()
                del camera_pool[source]

# Lista de cámaras RTSP predefinidas
PREDEFINED_CAMERAS = [
    {
        'id': 'hikvision_1',
        'name': 'Hikvision Cámara Principal',
        'url': 'rtsp://admin:IXGQBU@192.168.1.218:554/Streaming/Channels/0101',
        'type': 'rtsp',
        'enabled': True
    },
    {
        'id': 'local_0',
        'name': 'Cámara Local',
        'url': 0,
        'type': 'local',
        'enabled': True
    }
]

# Información adicional de personas (Biografía)
PERSON_DETAILS = {
    "Diego": [
        "CEO de Geo Software ltd",
        "Localizacion: Piso 12 Corporate Tower",
        "Santa Fe, Argentina"
    ],
    "German Ferrari": [
        "Gerente de STE SEGURIDAD",
        "SANTA FE CAPITAL"
    ],
    "Germa": [ # Alias por si acaso
        "Gerente de STE SEGURIDAD",
        "SANTA FE CAPITAL"
    ]
}

# Base de datos de caras de referencia
reference_faces = {}
reference_encodings = []

def allowed_file(filename):
    if not filename:
        return False

    # Obtener extensión
    if '.' not in filename:
        return False

    extension = filename.rsplit('.', 1)[1].lower()

    # Extensiones permitidas (incluyendo HEIF)
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'heic', 'heif'}

    return extension in allowed_extensions

def init_camera(source=None):
    """Inicializar cámara desde webcam local o RTSP (local/WAN)"""
    global camera, camera_source
    
    if source is not None:
        camera_source = source
    
    try:
        # Liberar cámara anterior si existe
        if camera is not None:
            try:
                camera.release()
            except:
                pass
            camera = None

        # Si es una URL RTSP o HTTP
        if isinstance(camera_source, str) and (camera_source.startswith('rtsp://') or 
                                                camera_source.startswith('http://') or 
                                                camera_source.startswith('https://')):
            try:
                print(f"🌐 Conectando a stream RTSP/HTTP: {camera_source}")
                
                # Para RTSP, usar backend FFmpeg con parámetros optimizados
                if camera_source.startswith('rtsp://'):
                    # Configuración específica para RTSP (Hikvision/Dahua)
                    # Usar backend FFmpeg si está disponible
                    try:
                        # Intentar con backend FFmpeg primero
                        camera = cv2.VideoCapture(camera_source, cv2.CAP_FFMPEG)
                    except:
                        # Fallback a backend por defecto
                        camera = cv2.VideoCapture(camera_source)
                    
                    # Configuraciones críticas para RTSP
                    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Buffer mínimo para reducir latencia
                    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))  # Codec H264
                    
                    # Para cámaras Hikvision, puede necesitar estas propiedades
                    # camera.set(cv2.CAP_PROP_FPS, 25)  # FPS común en cámaras IP
                    
                else:
                    # Para HTTP streams
                    camera = cv2.VideoCapture(camera_source)
                    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                # Esperar un momento para que se establezca la conexión
                import time
                time.sleep(1)
                
                # Verificar si se abrió correctamente
                if not camera.isOpened():
                    print(f"⚠️ No se pudo abrir el stream, intentando método alternativo...")
                    camera.release()
                    camera = None
                    
                    # Método alternativo: agregar parámetros RTSP a la URL
                    if camera_source.startswith('rtsp://'):
                        # Agregar parámetros para mejor compatibilidad
                        rtsp_url = camera_source
                        if '?' not in rtsp_url:
                            rtsp_url += '?tcp'  # Usar TCP en lugar de UDP para mejor estabilidad
                        print(f"🔄 Reintentando con URL optimizada: {rtsp_url}")
                        camera = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        time.sleep(1)
                
                # Probar lectura de frame con múltiples intentos
                max_retries = 3
                for attempt in range(max_retries):
                    ret, test_frame = camera.read()
                    if ret and test_frame is not None:
                        print(f"✅ Stream RTSP/HTTP conectado exitosamente (intento {attempt + 1})")
                        return True
                    else:
                        if attempt < max_retries - 1:
                            print(f"⚠️ Intento {attempt + 1} fallido, reintentando...")
                            time.sleep(1)
                        else:
                            print(f"⚠️ No se pudo leer del stream después de {max_retries} intentos")
                            camera.release()
                            camera = None
                            
            except Exception as e:
                print(f"❌ Error conectando a stream: {e}")
                import traceback
                traceback.print_exc()
                if camera is not None:
                    try:
                        camera.release()
                    except:
                        pass
                    camera = None
        
        # Si es un número (índice de cámara local)
        elif isinstance(camera_source, int) or (isinstance(camera_source, str) and camera_source.isdigit()):
            camera_index = int(camera_source) if isinstance(camera_source, str) else camera_source
            
            try:
                print(f"📹 Intentando abrir cámara local en índice {camera_index}")
                
                # En macOS, intentar primero con AVFoundation (mejor compatibilidad)
                try:
                    camera = cv2.VideoCapture(camera_index, cv2.CAP_AVFOUNDATION)
                    print(f"  Usando backend AVFoundation")
                except:
                    camera = cv2.VideoCapture(camera_index)
                    print(f"  Usando backend por defecto")

                if camera.isOpened():
                    # Configurar propiedades de la cámara
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    camera.set(cv2.CAP_PROP_FPS, 30)
                    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    # Dar tiempo a que se apliquen las configuraciones
                    time.sleep(1)

                    # Probar lectura de frame
                    ret, test_frame = camera.read()
                    if ret and test_frame is not None:
                        actual_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                        actual_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        actual_fps = camera.get(cv2.CAP_PROP_FPS)
                        print(f"✅ Cámara local inicializada correctamente en índice {camera_index}")
                        print(f"   Resolución: {actual_width}x{actual_height}")
                        print(f"   FPS: {actual_fps}")
                        return True
                    else:
                        print(f"⚠️ No se pudo leer de la cámara en índice {camera_index}")
                        camera.release()
                        camera = None
                else:
                    print(f"⚠️ No se pudo abrir cámara en índice {camera_index}")
                    if camera is not None:
                        try:
                            camera.release()
                        except Exception:
                            pass
                        camera = None
            except Exception as e:
                print(f"❌ Error con cámara local: {e}")
                if camera is not None:
                    try:
                        camera.release()
                    except Exception:
                        pass
                    camera = None

        # Si es una ruta de archivo de video
        elif isinstance(camera_source, str) and os.path.exists(camera_source):
            try:
                print(f"📁 Abriendo archivo de video: {camera_source}")
                camera = cv2.VideoCapture(camera_source)
                if camera.isOpened():
                    print(f"✅ Archivo de video abierto correctamente")
                    return True
            except Exception as e:
                print(f"❌ Error abriendo archivo de video: {e}")
                camera = None

        # Si no se especificó nada, intentar cámaras locales por defecto
        if camera is None:
            for camera_index in [0, 1, 2]:
                try:
                    print(f"📹 Intentando cámara local en índice {camera_index}")
                    camera = cv2.VideoCapture(camera_index)
                    if camera.isOpened():
                        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        camera.set(cv2.CAP_PROP_FPS, 30)
                        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        ret, test_frame = camera.read()
                        if ret and test_frame is not None:
                            print(f"✅ Cámara local inicializada en índice {camera_index}")
                            camera_source = camera_index
                            return True
                        else:
                            camera.release()
                            camera = None
                except Exception:
                    pass
        print("❌ No se pudo inicializar ninguna fuente de video")
        return False

    except Exception as e:
        print(f"❌ Error general inicializando fuente de video: {e}")
        return False

def load_reference_faces():
    """Cargar caras de referencia desde archivos"""
    global reference_faces, reference_encodings
    reference_faces = {}
    reference_encodings = []

    if not os.path.exists(REFERENCE_FOLDER):
        print("📁 Carpeta de referencias no existe, se creará automáticamente")
        return

    print(f"📁 Cargando referencias desde: {REFERENCE_FOLDER}")
    files = os.listdir(REFERENCE_FOLDER)
    print(f"   Encontrados {len(files)} archivos")
    
    for filename in files:
        if allowed_file(filename):
            filepath = os.path.join(REFERENCE_FOLDER, filename)
            try:
                print(f"   → Procesando: {filename}")
                image = face_recognition.load_image_file(filepath)
                print(f"     Imagen cargada, detectando caras...")
                # OPTIMIZACIÓN MEMORIA: Usar HOG por defecto (mucho más eficiente que CNN)
                # CNN consume ~500MB+ de memoria, HOG solo ~50MB
                with face_lock:
                    face_locations = face_recognition.face_locations(image, model="hog")
                
                print(f"     Encontradas {len(face_locations)} caras, generando encodings...")
                if len(face_locations) > 0:
                    # MEJORA: Usar num_jitters=2 para mejor precisión en referencias
                    # Las referencias deben ser de alta calidad para mejor matching
                    with face_lock:
                        face_encodings = face_recognition.face_encodings(
                            image, 
                            face_locations,
                            num_jitters=2  # Mejor precisión para referencias
                        )
                    print(f"     Encodings generados.")
                    # Liberar imagen después de procesar
                    del image
                else:
                    face_encodings = []
                    del image

                if len(face_encodings) > 0:
                    name = os.path.splitext(filename)[0]
                    
                    # MEJORA: Almacenar múltiples encodings si hay múltiples caras
                    if name not in reference_faces:
                        reference_faces[name] = {
                            'encodings': [],
                            'image_paths': [],
                            'face_locations': []
                        }
                    
                    # Agregar todos los encodings encontrados
                    for encoding, location in zip(face_encodings, face_locations):
                        reference_faces[name]['encodings'].append(encoding)
                        reference_faces[name]['image_paths'].append(filepath)
                        reference_faces[name]['face_locations'].append(location)
                    
                    # OPTIMIZACIÓN MEMORIA: Limitar número de encodings por persona
                    MAX_ENCODINGS_PER_PERSON = 3  # Máximo 3 encodings por persona
                    if len(reference_faces[name]['encodings']) > MAX_ENCODINGS_PER_PERSON:
                        # Mantener solo los primeros N encodings (los más antiguos)
                        reference_faces[name]['encodings'] = reference_faces[name]['encodings'][:MAX_ENCODINGS_PER_PERSON]
                        reference_faces[name]['image_paths'] = reference_faces[name]['image_paths'][:MAX_ENCODINGS_PER_PERSON]
                        reference_faces[name]['face_locations'] = reference_faces[name]['face_locations'][:MAX_ENCODINGS_PER_PERSON]
                    
                    # Reconstruir lista plana de encodings para matching rápido
                    reference_encodings = []
                    for face_name, face_data in reference_faces.items():
                        reference_encodings.extend(face_data['encodings'])
                    
                    print(f"✅ Cara de referencia cargada: {name} ({len(face_encodings)} encodings, Total refs: {len(reference_faces)})")
            except Exception as e:
                print(f"⚠️ Error cargando {filename}: {e}")
                import traceback
                traceback.print_exc()
    
    print(f"✅ Carga de referencias completada: {len(reference_faces)} personas registradas")

def save_face_detection(frame, face_location, face_encoding, is_known=False, name=None, confidence=None):
    """Guardar captura de cara (conocida o desconocida)"""
    try:
        if frame is None:
            print("❌ ERROR: frame es None en save_face_detection")
            return None
        
        top, right, bottom, left = face_location
        
        # Validar coordenadas
        if top < 0 or left < 0 or bottom > frame.shape[0] or right > frame.shape[1]:
            print(f"⚠️ Coordenadas fuera de rango: top={top}, left={left}, bottom={bottom}, right={right}, frame_shape={frame.shape}")
            # Ajustar coordenadas a los límites del frame
            top = max(0, top)
            left = max(0, left)
            bottom = min(frame.shape[0], bottom)
            right = min(frame.shape[1], right)
        
        if bottom <= top or right <= left:
            print(f"❌ ERROR: Coordenadas inválidas después de ajuste: top={top}, left={left}, bottom={bottom}, right={right}")
            return None
        
        # Extraer región de la cara con padding
        padding = 20
        y1 = max(0, top - padding)
        y2 = min(frame.shape[0], bottom + padding)
        x1 = max(0, left - padding)
        x2 = min(frame.shape[1], right + padding)
        
        if y2 <= y1 or x2 <= x1:
            print(f"❌ ERROR: Región de recorte inválida: y1={y1}, y2={y2}, x1={x1}, x2={x2}")
            return None
        
        face_crop = frame[y1:y2, x1:x2]
        
        if face_crop.size == 0:
            print(f"❌ ERROR: face_crop está vacío")
            return None
        
        # Crear nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        if is_known and name:
            # Limpiar nombre para usar en archivo
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            filename = f"known_{safe_name}_{timestamp}.jpg"
            folder = UNKNOWN_FACES_FOLDER  # Usar misma carpeta para todas las detecciones
        else:
            filename = f"unknown_{timestamp}.jpg"
            folder = UNKNOWN_FACES_FOLDER
        
        filepath = os.path.join(folder, filename)
        
        # Asegurar que la carpeta existe
        os.makedirs(folder, exist_ok=True)
        
        # Guardar imagen con alta calidad (95% JPEG quality)
        success = cv2.imwrite(filepath, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            print(f"❌ ERROR: No se pudo guardar imagen en {filepath}")
            return None
        
        # Verificar que el archivo se guardó
        if not os.path.exists(filepath):
            print(f"❌ ERROR: El archivo no existe después de guardar")
            return None
        
        file_size = os.path.getsize(filepath)
        print(f"✅ Imagen guardada: {filename} ({file_size} bytes) - {'conocida' if is_known else 'desconocida'}")
        
        # Guardar detección en base de datos
        detection = {
            'id': timestamp,
            'timestamp': datetime.now().isoformat(),
            'type': 'known' if is_known else 'unknown',
            'image_path': filepath,
            'image_filename': filename,
            'face_location': face_location,
            'confidence': confidence,
            'name': name if name else 'Desconocido',
            'notes': '',
            'status': 'pending'  # pending, reviewed, archived
        }
        
        save_detection(detection)
        return detection
    except Exception as e:
        print(f"❌ ERROR guardando cara: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_unknown_face(frame, face_location, face_encoding):
    """Guardar captura de cara desconocida (compatibilidad hacia atrás)"""
    return save_face_detection(frame, face_location, face_encoding, is_known=False)

def load_detections():
    """Cargar detecciones desde base de datos JSON"""
    if os.path.exists(DETECTIONS_DB):
        try:
            with open(DETECTIONS_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_detection(detection):
    """Guardar detección en base de datos JSON"""
    detections = load_detections()
    detections.append(detection)
    
    # Mantener solo las últimas 10000 detecciones
    if len(detections) > 10000:
        detections = detections[-10000:]
    
    try:
        with open(DETECTIONS_DB, 'w', encoding='utf-8') as f:
            json.dump(detections, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando detección: {e}")

def update_detection(detection_id, updates):
    """Actualizar detección existente"""
    detections = load_detections()
    for i, det in enumerate(detections):
        if det.get('id') == detection_id:
            detections[i].update(updates)
            try:
                with open(DETECTIONS_DB, 'w', encoding='utf-8') as f:
                    json.dump(detections, f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                print(f"Error actualizando detección: {e}")
                return False
    return False

def delete_detection(detection_id):
    """Eliminar detección"""
    detections = load_detections()
    for i, det in enumerate(detections):
        if det.get('id') == detection_id:
            # Eliminar imagen si existe
            if 'image_path' in det and os.path.exists(det['image_path']):
                try:
                    os.remove(det['image_path'])
                except:
                    pass
            
            detections.pop(i)
            try:
                with open(DETECTIONS_DB, 'w', encoding='utf-8') as f:
                    json.dump(detections, f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                print(f"Error eliminando detección: {e}")
                return False
    return False

def get_kpi_stats():
    """Obtener estadísticas KPI"""
    detections = load_detections()
    
    if not detections:
        return {
            'total': 0,
            'unknown': 0,
            'known': 0,
            'today': 0,
            'this_week': 0,
            'this_month': 0,
            'by_hour': {},
            'by_day': {}
        }
    
    now = datetime.now()
    today = now.date()
    week_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)
    month_ago = datetime.now().timestamp() - (30 * 24 * 60 * 60)
    
    stats = {
        'total': len(detections),
        'unknown': sum(1 for d in detections if d.get('type') == 'unknown'),
        'known': sum(1 for d in detections if d.get('type') == 'known'),
        'today': 0,
        'this_week': 0,
        'this_month': 0,
        'by_hour': {},
        'by_day': {}
    }
    
    for det in detections:
        try:
            det_time = datetime.fromisoformat(det['timestamp'])
            det_timestamp = det_time.timestamp()
            det_date = det_time.date()
            
            # Contar por día
            day_key = det_date.isoformat()
            stats['by_day'][day_key] = stats['by_day'].get(day_key, 0) + 1
            
            # Contar por hora
            hour_key = det_time.hour
            stats['by_hour'][hour_key] = stats['by_hour'].get(hour_key, 0) + 1
            
            # Contar períodos
            if det_date == today:
                stats['today'] += 1
            if det_timestamp >= week_ago:
                stats['this_week'] += 1
            if det_timestamp >= month_ago:
                stats['this_month'] += 1
        except:
            pass
    
    return stats

# Cargar modelo de segmentación semántica DeepLabV3 para máscaras precisas
segmentation_net = None
segmentation_classes = []
segmentation_input_size = 513

# Clases COCO para segmentación (mismo orden que YOLO)
segmentation_classes = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
    'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
    'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
    'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

# Cargar modelo de segmentación DeepLabV3
"""
try:
    deeplab_prototxt = "deeplabv3_mobilenet_v3_large.pbtxt"
    deeplab_model = "deeplabv3_mobilenet_v3_large.pb"
    
    if os.path.exists(deeplab_prototxt) and os.path.exists(deeplab_model):
        segmentation_net = cv2.dnn.readNetFromTensorflow(deeplab_model, deeplab_prototxt)
        segmentation_input_size = 513
        print("✅ Modelo DeepLabV3 para segmentación cargado")
    else:
        print("⚠️ Modelo DeepLabV3 no encontrado. Descargando...")
        # Descargar modelo DeepLabV3
        deeplab_url = "https://github.com/ayoolaolafenwa/PixelLib/releases/download/1.1/deeplabv3_mobilenet_v3_large.pb"
        print(f"   URL: {deeplab_url}")
        print("   Usando máscaras mejoradas basadas en bounding boxes")
except Exception as e:
    print(f"⚠️ No se pudo cargar modelo de segmentación: {e}")
"""

# Cargar modelo de detección de objetos YOLO
yolo_net = None
yolo_classes = []
yolo_input_size = 416
yolo_confidence_threshold = 0.5
yolo_nms_threshold = 0.4

# Clases COCO para YOLO (80 clases)
yolo_classes = segmentation_classes.copy()

# Cargar modelo YOLO de Ultralytics (prioridad)
yolo_model = None
yolo_net = None
object_net = None

def init_models():
    """Inicializar todos los modelos de detección de forma diferida"""
    global yolo_model, yolo_net, object_net, yolo_input_size, object_classes
    
    # 1. Intentar YOLOv8 (Ultralytics)
    init_yolo()
    
    # 2. Fallback YOLOv3 (OpenCV DNN)
    if yolo_model is None:
        try:
            yolo_config_path = "yolov3.cfg"
            yolo_weights_path = "yolov3.weights"
            if os.path.exists(yolo_config_path) and os.path.exists(yolo_weights_path):
                yolo_net = cv2.dnn.readNetFromDarknet(yolo_config_path, yolo_weights_path)
                yolo_input_size = 416
                print("✅ Modelo YOLOv3 (fallback) cargado")
        except Exception as e:
            print(f"⚠️ No se pudo cargar modelo YOLO fallback: {e}")

    # 3. Fallback MobileNet-SSD
    try:
        prototxt_path = "MobileNetSSD_deploy.prototxt"
        model_path = "MobileNetSSD_deploy.caffemodel"
        if os.path.exists(prototxt_path) and os.path.exists(model_path):
            object_net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
            print("✅ Modelo MobileNet-SSD cargado como respaldo")
    except Exception as e:
        pass

# Cache para el detector HOG (evitar recrearlo cada frame)
_hog_detector = None

def get_hog_detector():
    """Obtener detector HOG (singleton)"""
    global _hog_detector
    if _hog_detector is None:
        _hog_detector = cv2.HOGDescriptor()
        _hog_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return _hog_detector

def non_max_suppression(boxes, scores, overlap_threshold=0.3):
    """Eliminar detecciones duplicadas usando Non-Maximum Suppression"""
    if len(boxes) == 0:
        return []
    
    # Convertir a formato numpy
    boxes = np.array(boxes)
    scores = np.array(scores)
    
    # Obtener coordenadas
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    
    # Calcular áreas
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    
    # Ordenar por score (mayor a menor)
    indices = np.argsort(scores)[::-1]
    
    keep = []
    while len(indices) > 0:
        i = indices[0]
        keep.append(i)
        
        if len(indices) == 1:
            break
        
        # Calcular intersección
        xx1 = np.maximum(x1[i], x1[indices[1:]])
        yy1 = np.maximum(y1[i], y1[indices[1:]])
        xx2 = np.minimum(x2[i], x2[indices[1:]])
        yy2 = np.minimum(y2[i], y2[indices[1:]])
        
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        intersection = w * h
        
        # Calcular IoU (Intersection over Union)
        iou = intersection / (areas[i] + areas[indices[1:]] - intersection)
        
        # Mantener solo las cajas con IoU menor al umbral
        indices = indices[1:][iou <= overlap_threshold]
    
    return keep

# Cache para estabilización temporal de detecciones mejorada
object_detection_cache = []
CACHE_SIZE = 2  # Reducido para ahorrar memoria (era 3)
person_detection_history = []  # Historial específico para personas
PERSON_HISTORY_SIZE = 3  # Reducido para ahorrar memoria (era 5)
MAX_DETECTIONS_PER_FRAME = 20  # Límite de detecciones por frame para evitar memoria excesiva

# Cache para encodings de referencia (cargar una vez)
_cached_reference_encodings = None
_cached_reference_names = None

def calculate_iou(box1, box2):
    """Calcular Intersection over Union (IoU) entre dos cajas"""
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # Calcular intersección
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)
    
    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0
    
    intersection = (x2_i - x1_i) * (y2_i - y1_i)
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0.0

def stabilize_detections(new_detections):
    """Estabilizar detecciones usando promedio temporal mejorado (especialmente para personas)"""
    global object_detection_cache, person_detection_history
    
    # LIMITAR DETECCIONES PARA AHORRAR MEMORIA
    if len(new_detections) > MAX_DETECTIONS_PER_FRAME:
        # Ordenar por confianza y tomar solo las mejores
        new_detections = sorted(new_detections, key=lambda x: x['confidence'], reverse=True)[:MAX_DETECTIONS_PER_FRAME]
    
    if not new_detections:
        # Si no hay detecciones nuevas, usar historial para suavizar
        if person_detection_history:
            return person_detection_history[-1] if person_detection_history else []
        return []
    
    # Separar personas de otros objetos
    person_detections = [d for d in new_detections if d['class'] == 'person']
    other_detections = [d for d in new_detections if d['class'] != 'person']
    
    # LIMITAR PERSONAS POR FRAME
    if len(person_detections) > 10:
        person_detections = sorted(person_detections, key=lambda x: x['confidence'], reverse=True)[:10]
    
    # Estabilizar personas con historial más largo
    stabilized_persons = []
    if person_detections:
        person_detection_history.append(person_detections)
        if len(person_detection_history) > PERSON_HISTORY_SIZE:
            person_detection_history.pop(0)
        
        # Promediar posiciones de personas usando IoU matching
        if len(person_detection_history) >= 2:
            # Agrupar personas por proximidad espacial usando IoU
            person_groups = []
            MAX_GROUPS = 15  # Límite de grupos para evitar memoria excesiva
            for frame_dets in person_detection_history:
                for det in frame_dets:
                    matched = False
                    for group in person_groups:
                        # Calcular IoU con el promedio del grupo
                        if len(group) > 0:
                            avg_box = np.mean([g['box'] for g in group], axis=0)
                            iou = calculate_iou(det['box'], tuple(avg_box))
                            if iou > 0.3:  # Umbral de matching
                                group.append(det)
                                matched = True
                                break
                    if not matched:
                        if len(person_groups) < MAX_GROUPS:
                            person_groups.append([det])
            
            # Promediar cada grupo con umbral más alto para reducir falsos positivos
            for group in person_groups:
                if len(group) >= 2:  # Al menos 2 detecciones
                    avg_box = np.mean([d['box'] for d in group], axis=0)
                    avg_conf = np.mean([d['confidence'] for d in group])
                    # Umbral más alto (0.45) para estabilización de personas
                    if avg_conf > 0.45:
                        stabilized_persons.append({
                            'class': 'person',
                            'confidence': avg_conf,
                            'box': tuple(avg_box.astype(int))
                        })
        else:
            stabilized_persons = person_detections
    else:
        # Si no hay personas nuevas, mantener las anteriores con decaimiento
        if person_detection_history:
            last_persons = person_detection_history[-1]
            # Reducir confianza para detecciones antiguas
            stabilized_persons = [{
                'class': 'person',
                'confidence': p['confidence'] * 0.8,
                'box': p['box']
            } for p in last_persons if p['confidence'] * 0.8 > 0.2]
    
    # Estabilizar otros objetos con cache normal
    object_detection_cache.append(other_detections)
    if len(object_detection_cache) > CACHE_SIZE:
        object_detection_cache.pop(0)
    
    stabilized_others = []
    if len(object_detection_cache) >= 2:
        # Agrupar por clase usando método mejorado
        stabilized = {}
        for frame_detections in object_detection_cache:
            for det in frame_detections:
                x1, y1, x2, y2 = det['box']
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                width = x2 - x1
                height = y2 - y1
                
                # Crear clave única basada en posición y tamaño
                key = f"{det['class']}_{int(center_x/50)}_{int(center_y/50)}_{int(width/50)}_{int(height/50)}"
                
                if key not in stabilized:
                    stabilized[key] = {
                        'class': det['class'],
                        'boxes': [],
                        'confidences': []
                    }
                
                stabilized[key]['boxes'].append([x1, y1, x2, y2])
                stabilized[key]['confidences'].append(det['confidence'])
        
        for key, data in stabilized.items():
            if len(data['confidences']) >= 2:
                avg_box = np.mean(data['boxes'], axis=0).astype(int)
                avg_confidence = np.mean(data['confidences'])
                if avg_confidence > 0.4:
                    stabilized_others.append({
                        'class': data['class'],
                        'confidence': avg_confidence,
                        'box': tuple(avg_box)
                    })
    else:
        stabilized_others = other_detections
    
    return stabilized_persons + stabilized_others

def detect_objects_opencv(frame):
    """Detección mejorada de objetos usando OpenCV HOG"""
    detections = []
    
    try:
        # Redimensionar frame para mejor rendimiento (si es muy grande)
        h, w = frame.shape[:2]
        max_dimension = 800
        scale = 1.0
        
        if max(h, w) > max_dimension:
            scale = max_dimension / max(h, w)
            frame_resized = cv2.resize(frame, (int(w * scale), int(h * scale)))
        else:
            frame_resized = frame
        
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
        
        # Aplicar ecualización de histograma para mejorar detección
        gray = cv2.equalizeHist(gray)
        
        # Obtener detector HOG
        hog = get_hog_detector()
        
        # Detectar personas con múltiples escalas y parámetros optimizados
        boxes, weights = hog.detectMultiScale(
            gray,
            winStride=(4, 4),  # Paso más pequeño para mejor detección
            padding=(16, 16),  # Padding reducido
            scale=1.05,  # Escala de pirámide
            finalThreshold=2.0,  # Umbral final más estricto
            useMeanshiftGrouping=False  # Más rápido
        )
        
        # Filtrar y escalar de vuelta las detecciones
        valid_boxes = []
        valid_scores = []
        
        for (x, y, w_box, h_box), weight in zip(boxes, weights):
            if weight > 0.3:  # Umbral de confianza más bajo inicialmente
                # Escalar de vuelta si fue redimensionado
                if scale != 1.0:
                    x = int(x / scale)
                    y = int(y / scale)
                    w_box = int(w_box / scale)
                    h_box = int(h_box / scale)
                
                # Validar que la caja esté dentro del frame
                if x >= 0 and y >= 0 and x + w_box <= frame.shape[1] and y + h_box <= frame.shape[0]:
                    valid_boxes.append([x, y, x + w_box, y + h_box])
                    valid_scores.append(float(weight))
        
        # Aplicar Non-Maximum Suppression para eliminar duplicados
        if len(valid_boxes) > 0:
            keep_indices = non_max_suppression(valid_boxes, valid_scores, overlap_threshold=0.3)
            
            for idx in keep_indices:
                x1, y1, x2, y2 = valid_boxes[idx]
                confidence = valid_scores[idx]
                
                # Filtrar por confianza final
                if confidence > 0.5:
                    detections.append({
                        'class': 'person',
                        'confidence': confidence,
                        'box': (x1, y1, x2, y2)
                    })
        
    except Exception as e:
        print(f"Error en detección OpenCV: {e}")
        import traceback
        traceback.print_exc()
    
    return detections

def detect_objects_yolo(frame):
    """Detección de objetos usando Ultralytics YOLO (mejor para personas)"""
    # Priorizar Ultralytics YOLO si está disponible
    if yolo_model is not None:
        detections = []
        try:
            # Usar lock para evitar fallos de segmentación en entornos multi-hilo
            with yolo_lock:
                # MEJORA DETECCIÓN A DISTANCIA: Umbral más bajo para detectar personas a 7 metros
                # Reducido conf para detectar personas más pequeñas a distancia
                results = yolo_model(frame, conf=0.25, iou=0.45, verbose=False)
            
            h, w = frame.shape[:2]
            min_area = (w * h) * 0.01  # Área mínima del 1% del frame
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Obtener coordenadas
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0].cpu().numpy())
                        class_id = int(box.cls[0].cpu().numpy())
                        
                        # Obtener nombre de clase
                        if class_id < len(yolo_classes):
                            class_name = yolo_classes[class_id]
                        else:
                            class_name = f"class_{class_id}"
                        
                        # Validar coordenadas
                        x1 = max(0, min(int(x1), w))
                        y1 = max(0, min(int(y1), h))
                        x2 = max(0, min(int(x2), w))
                        y2 = max(0, min(int(y2), h))
                        
                        # Filtrar por tamaño mínimo y confianza más alta para personas
                        box_area = (x2 - x1) * (y2 - y1)
                        
                        if x2 > x1 and y2 > y1 and box_area >= min_area:
                            # Umbral más estricto para personas (0.5) para reducir falsos positivos
                            if class_name == 'person':
                                if confidence >= 0.5:
                                    detections.append({
                                        'class': class_name,
                                        'confidence': confidence,
                                        'box': (x1, y1, x2, y2)
                                    })
                            else:
                                # Otros objetos con umbral más bajo (0.4)
                                if confidence >= 0.4:
                                    detections.append({
                                        'class': class_name,
                                        'confidence': confidence,
                                        'box': (x1, y1, x2, y2)
                                    })
            
            return detections
        except Exception as e:
            print(f"Error en detección Ultralytics YOLO: {e}")
            # Fallback a métodos anteriores
            pass
    
    # Fallback a modelos anteriores si Ultralytics no está disponible
    if yolo_net is None:
        return None
    
    detections = []
    try:
        h, w = frame.shape[:2]
        
        # Crear blob para YOLO
        blob = cv2.dnn.blobFromImage(
            frame,
            1/255.0,  # Escala
            (yolo_input_size, yolo_input_size),  # Tamaño de entrada
            [0, 0, 0],  # Media (BGR)
            swapRB=True,  # Convertir RGB a BGR
            crop=False
        )
        
        yolo_net.setInput(blob)
        
        # Detectar tipo de modelo
        is_onnx = os.path.exists("yolov8n.onnx") or os.path.exists("yolov5s.onnx")
        
        boxes_list = []
        scores_list = []
        classes_list = []
        
        if is_onnx:
            # YOLOv5/v8 (ONNX)
            outputs = yolo_net.forward()
            
            # Formato puede ser [1, N, 85] o [N, 85]
            if len(outputs.shape) == 3:
                output = outputs[0]
            else:
                output = outputs
            
            for detection in output:
                if len(detection) >= 85:
                    # Formato YOLO estándar: [x, y, w, h, conf, class_scores...]
                    x_center, y_center, box_w, box_h = detection[0:4]
                    confidence = detection[4]
                    class_scores = detection[5:85]
                    
                    if confidence > yolo_confidence_threshold:
                        class_id = np.argmax(class_scores)
                        class_confidence = class_scores[class_id]
                        
                        # Convertir coordenadas normalizadas a píxeles
                        x1 = int((x_center - box_w / 2) * w)
                        y1 = int((y_center - box_h / 2) * h)
                        x2 = int((x_center + box_w / 2) * w)
                        y2 = int((y_center + box_h / 2) * h)
                        
                        # Validar coordenadas
                        x1 = max(0, min(x1, w))
                        y1 = max(0, min(y1, h))
                        x2 = max(0, min(x2, w))
                        y2 = max(0, min(y2, h))
                        
                        if x2 > x1 and y2 > y1 and class_id < len(yolo_classes):
                            final_confidence = float(confidence * class_confidence)
                            boxes_list.append([x1, y1, x2, y2])
                            scores_list.append(final_confidence)
                            classes_list.append(yolo_classes[class_id])
        else:
            # YOLOv3 (Darknet)
            layer_names = yolo_net.getLayerNames()
            output_layers = [layer_names[i - 1] for i in yolo_net.getUnconnectedOutLayers()]
            outputs = yolo_net.forward(output_layers)
            
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    if confidence > yolo_confidence_threshold:
                        center_x = int(detection[0] * w)
                        center_y = int(detection[1] * h)
                        box_width = int(detection[2] * w)
                        box_height = int(detection[3] * h)
                        
                        x1 = int(center_x - box_width / 2)
                        y1 = int(center_y - box_height / 2)
                        x2 = int(center_x + box_width / 2)
                        y2 = int(center_y + box_height / 2)
                        
                        x1 = max(0, min(x1, w))
                        y1 = max(0, min(y1, h))
                        x2 = max(0, min(x2, w))
                        y2 = max(0, min(y2, h))
                        
                        if x2 > x1 and y2 > y1 and class_id < len(yolo_classes):
                            boxes_list.append([x1, y1, x2, y2])
                            scores_list.append(float(confidence))
                            classes_list.append(yolo_classes[class_id])
        
        # Aplicar Non-Maximum Suppression
        if len(boxes_list) > 0:
            keep_indices = non_max_suppression(boxes_list, scores_list, overlap_threshold=yolo_nms_threshold)
            
            for idx in keep_indices:
                detections.append({
                    'class': classes_list[idx],
                    'confidence': scores_list[idx],
                    'box': tuple(boxes_list[idx])
                })
        
    except Exception as e:
        print(f"Error en detección YOLO: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    return detections

def detect_objects_dnn(frame):
    """Detección de objetos usando YOLO primero, luego MobileNet-SSD como respaldo"""
    # Intentar YOLO primero
    yolo_detections = detect_objects_yolo(frame)
    if yolo_detections is not None:
        return yolo_detections
    
    # Si YOLO no está disponible, usar MobileNet-SSD
    if object_net is None:
        return detect_objects_opencv(frame)
    
    detections = []
    try:
        h, w = frame.shape[:2]
        
        # Preparar imagen para la red
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
        object_net.setInput(blob)
        detections_dnn = object_net.forward()
        
        # Procesar detecciones
        for i in range(detections_dnn.shape[2]):
            confidence = detections_dnn[0, 0, i, 2]
            
            if confidence > 0.5:  # Umbral de confianza
                class_id = int(detections_dnn[0, 0, i, 1])
                if class_id < len(object_classes):
                    class_name = object_classes[class_id]
                    
                    # Coordenadas normalizadas
                    x1 = int(detections_dnn[0, 0, i, 3] * w)
                    y1 = int(detections_dnn[0, 0, i, 4] * h)
                    x2 = int(detections_dnn[0, 0, i, 5] * w)
                    y2 = int(detections_dnn[0, 0, i, 6] * h)
                    
                    detections.append({
                        'class': class_name,
                        'confidence': float(confidence),
                        'box': (x1, y1, x2, y2)
                    })
    except Exception as e:
        print(f"Error en detección DNN: {e}")
        return detect_objects_opencv(frame)
    
    return detections

def draw_basic_landmarks(frame, face_landmarks, left, top, right, bottom, scale_back, color):
    """Dibujar landmarks básicos de face_recognition cuando MediaPipe no está disponible"""
    try:
        if not face_landmarks:
            return
        
        # scale_back es el factor de escalado (ej: 2 si scale_factor era 0.5)
        # Los landmarks están en coordenadas del frame pequeño, necesitamos escalarlos
        scale = float(scale_back) if scale_back > 0 else 1.0
        
        # Dibujar puntos clave de la cara
        landmark_parts = ['chin', 'left_eyebrow', 'right_eyebrow', 'nose_bridge', 
                         'nose_tip', 'left_eye', 'right_eye', 'top_lip', 'bottom_lip']
        
        for part in landmark_parts:
            if part in face_landmarks:
                points = face_landmarks[part]
                if len(points) > 0:
                    # Convertir puntos a coordenadas del frame original
                    scaled_points = []
                    for point in points:
                        x = int(point[0] * scale)
                        y = int(point[1] * scale)
                        scaled_points.append((x, y))
                    
                    # Dibujar líneas conectando los puntos
                    if len(scaled_points) > 1:
                        for i in range(len(scaled_points) - 1):
                            cv2.line(frame, scaled_points[i], scaled_points[i + 1], color, 1)
                    
                    # Dibujar puntos clave
                    for point in scaled_points:
                        cv2.circle(frame, point, 2, color, -1)
    except Exception as e:
        # Si hay error, simplemente no dibujar landmarks
        pass

def generate_frames_multicam(source, camera_id=None):
    """Generador de frames para sistema multi-cámara con detección de objetos y rostros."""
    global reference_encodings, reference_faces, active_cameras, cameras_lock, yolo_model

    cap = None
    cap_lock = None
    try:
        # --- Verificar Límite de Cámaras ---
        with cameras_lock:
            if len(active_cameras) >= MAX_ACTIVE_CAMERAS and camera_id not in active_cameras:
                print(f"⚠️ Límite de cámaras alcanzado ({MAX_ACTIVE_CAMERAS}). No se puede iniciar {camera_id}")
                return

        print(f"📹 Inicializando stream: {camera_id} - Fuente: {source}")

        # --- Obtener Cámara del Pool Compartido ---
        cap, cap_lock = get_shared_cap(source)
        if not cap:
            raise ConnectionError(f"No se pudo abrir la fuente de video: {source}")

        with cameras_lock:
            active_cameras[camera_id] = {'cap': cap, 'source': source, 'lock': cap_lock}
        print(f"✅ Stream iniciado: {camera_id}")

        frame_count = 0
        error_count = 0
        max_errors = 30
        
        # Cache para persistir los marcos entre frames procesados y evitar intermitencia
        last_yolo_detections = [] # [{'box': (x1, y1, x2, y2), 'conf': conf}]
        last_face_detections = [] # [{'box': (t, r, b, l), 'label': label, 'color': color}]

        # --- Bucle Principal de Procesamiento ---
        while camera_id in active_cameras:
            try:
                cam_data = active_cameras.get(camera_id)
                if not cam_data: break

                with cam_data['lock']:
                    success, frame = cap.read()

                if not success or frame is None:
                    error_count += 1
                    if error_count > max_errors:
                        print(f"❌ Demasiados errores en {camera_id}. Cerrando stream.")
                        break
                    time.sleep(0.1)
                    continue
                
                error_count = 0

                # --- Procesamiento de Detección (cada 3 frames para rendimiento) ---
                if frame_count % 3 == 0:
                    # OPTIMIZACIÓN: Liberar memoria periódicamente
                    if frame_count % 150 == 0:
                        gc.collect()

                    h, w = frame.shape[:2]
                    # Usar 0.5x para YOLO (suficiente para objetos grandes)
                    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                    
                    # OPTIMIZACIÓN ROSTROS: Redimensionar a un ancho fijo (ej: 640px)
                    # Esto hace que la detección sea consistente sin importar la resolución de la cámara
                    target_width = 640
                    face_scale = target_width / w
                    face_frame = cv2.resize(frame, (target_width, int(h * face_scale)))
                    rgb_face_frame = cv2.cvtColor(face_frame, cv2.COLOR_BGR2RGB)
                    
                    # Limpiar cache para nueva detección
                    new_yolo_detections = []
                    new_face_detections = []

                    # 1. Detección de Objetos (YOLO)
                    if OBJECT_DETECTION_ENABLED and yolo_model:
                        try:
                            with yolo_lock:
                                # OPTIMIZACIÓN: imgsz=320 reduce drásticamente el uso de RAM y CPU
                                yolo_results = yolo_model(small_frame, conf=0.3, iou=0.5, imgsz=320, verbose=False)
                            
                            for result in yolo_results:
                                if result.boxes:
                                    for i, box in enumerate(result.boxes):
                                        # Escalar coordenadas de vuelta (small_frame es 0.5x)
                                        x1, y1, x2, y2 = [int(c * 2) for c in box.xyxy[0].cpu().numpy()]
                                        conf = float(box.conf[0].cpu().numpy())
                                        class_id = int(box.cls[0].cpu().numpy())
                                        
                                        # Obtener nombre de clase dinámico
                                        class_name = yolo_classes[class_id].upper() if class_id < len(yolo_classes) else f"OBJETO {class_id}"
                                        
                                        # Extraer máscara si el modelo es de segmentación
                                        mask_data = None
                                        if hasattr(result, 'masks') and result.masks is not None:
                                            m = result.masks.xy[i]
                                            if len(m) > 0:
                                                mask_data = (m * 2).astype(np.int32)
                                        
                                        new_yolo_detections.append({
                                            'box': (x1, y1, x2, y2), 
                                            'conf': conf,
                                            'class_name': class_name,
                                            'mask': mask_data
                                        })
                            
                            # Liberar resultados de YOLO explícitamente
                            del yolo_results
                        except Exception as yolo_error:
                            print(f"❌ Error en YOLO para {camera_id}: {yolo_error}")

                    # 2. Detección de Rostros
                    with face_lock:
                        # Upsample=1 con 640px de ancho es ideal para HOG
                        face_locations = face_recognition.face_locations(rgb_face_frame, number_of_times_to_upsample=1, model="hog")
                        face_encodings = face_recognition.face_encodings(rgb_face_frame, face_locations)
                    
                    # MEJORA DISTANCIA: Si detectamos personas con YOLO pero no caras, 
                    # intentamos buscar caras dentro de los recuadros de las personas a mayor resolución
                    if OBJECT_DETECTION_ENABLED and yolo_model:
                        for det in new_yolo_detections:
                            if "PERSON" in det['class_name']:
                                x1, y1, x2, y2 = det['box']
                                # Verificar si ya hay una cara en esta área
                                face_already_detected = False
                                for (f_top, f_right, f_bottom, f_left) in face_locations:
                                    # Escalar coordenadas de cara a resolución original
                                    f_top_orig = int(f_top / face_scale)
                                    f_right_orig = int(f_right / face_scale)
                                    f_bottom_orig = int(f_bottom / face_scale)
                                    f_left_orig = int(f_left / face_scale)
                                    
                                    # Calcular IoU o simplemente ver si el centro de la cara está en el box de la persona
                                    f_center_x = (f_left_orig + f_right_orig) / 2
                                    f_center_y = (f_top_orig + f_bottom_orig) / 2
                                    if x1 <= f_center_x <= x2 and y1 <= f_center_y <= y2:
                                        face_already_detected = True
                                        break
                                
                                if not face_already_detected:
                                    # Extraer ROI de la persona del frame original (alta res)
                                    # Añadir un poco de margen arriba para la cabeza
                                    roi_y1 = max(0, y1 - int((y2-y1)*0.1))
                                    roi_y2 = min(h, y1 + int((y2-y1)*0.4)) # Solo la parte superior (cabeza/hombros)
                                    roi_x1 = max(0, x1)
                                    roi_x2 = min(w, x2)
                                    
                                    if roi_y2 > roi_y1 and roi_x2 > roi_x1:
                                        person_roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
                                        if person_roi.size > 0:
                                            # Redimensionar ROI para que sea lo suficientemente grande para HOG
                                            roi_h, roi_w = person_roi.shape[:2]
                                            if roi_w < 160: # Si es muy pequeño, agrandar
                                                scale = 160 / roi_w
                                                person_roi = cv2.resize(person_roi, (0,0), fx=scale, fy=scale)
                                            else:
                                                scale = 1.0
                                            
                                            rgb_roi = cv2.cvtColor(person_roi, cv2.COLOR_BGR2RGB)
                                            with face_lock:
                                                roi_face_locs = face_recognition.face_locations(rgb_roi, model="hog")
                                                roi_face_encs = face_recognition.face_encodings(rgb_roi, roi_face_locs)
                                            
                                            for (r_top, r_right, r_bottom, r_left), r_enc in zip(roi_face_locs, roi_face_encs):
                                                # Convertir coordenadas de ROI a coordenadas originales
                                                orig_top = int(r_top / scale) + roi_y1
                                                orig_right = int(r_right / scale) + roi_x1
                                                orig_bottom = int(r_bottom / scale) + roi_y1
                                                orig_left = int(r_left / scale) + roi_x1
                                                
                                                # Añadir a la lista de caras (en escala de face_frame para el loop siguiente)
                                                face_locations.append((
                                                    int(orig_top * face_scale),
                                                    int(orig_right * face_scale),
                                                    int(orig_bottom * face_scale),
                                                    int(orig_left * face_scale)
                                                ))
                                                face_encodings.append(r_enc)
                                                print(f"🎯 [{camera_id}] Cara detectada mediante ZOOM en persona a distancia")

                    # DEBUG: Siempre imprimir si se está procesando
                    if frame_count % 30 == 0:
                        print(f"🔍 [{camera_id}] Res: {w}x{h} | FaceRes: {face_frame.shape[1]}x{face_frame.shape[0]} | Caras: {len(face_locations)}")

                    if len(face_locations) > 0:
                        print(f"👤 [{camera_id}] Detectadas {len(face_locations)} caras")

                    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                        # Escalar de vuelta a la resolución original (1/face_scale)
                        top = int(top / face_scale)
                        right = int(right / face_scale)
                        bottom = int(bottom / face_scale)
                        left = int(left / face_scale)
                        
                        color = (0, 0, 255); label = "Desconocido"; is_known = False; matched_name = None; confidence = None

                        if reference_encodings:
                            with face_lock:
                                matches = face_recognition.compare_faces(reference_encodings, face_encoding, tolerance=0.6)
                                face_distances = face_recognition.face_distance(reference_encodings, face_encoding)
                            
                            if True in matches:
                                best_match_index = np.argmin(face_distances)
                                if matches[best_match_index]:
                                    confidence = 1.0 - face_distances[best_match_index]
                                    is_known = True
                                    color = (0, 255, 0)
                                    
                                    current_index = 0
                                    for person_name, person_data in reference_faces.items():
                                        num_encodings = len(person_data['encodings'])
                                        if best_match_index < current_index + num_encodings:
                                            # Extraer nombre base (antes de guiones o números)
                                            matched_name = person_name.split('_')[0].split('-')[0].strip()
                                            label = f"{matched_name} ({confidence:.2f})"
                                            break
                                        current_index += num_encodings
                        else:
                            if frame_count % 30 == 0:
                                print(f"⚠️ [{camera_id}] No hay encodings de referencia cargados")
                        
                        # Obtener información adicional si existe
                        details = PERSON_DETAILS.get(matched_name, []) if matched_name else []
                        new_face_detections.append({
                            'box': (top, right, bottom, left), 
                            'label': label, 
                            'color': color,
                            'details': details
                        })
                    
                    # Liberar frames temporales
                    del small_frame
                    del face_frame
                    del rgb_face_frame
                    
                    # Actualizar cache persistente
                    last_yolo_detections = new_yolo_detections
                    last_face_detections = new_face_detections

                # --- Dibujar Detecciones (en CADA frame para evitar parpadeo) ---
                # Colores estilo TRON ARES (Cyan eléctrico y Blanco)
                TRON_CYAN = (255, 255, 0)
                TRON_GLOW = (255, 150, 0)
                TRON_WHITE = (255, 255, 255)

                # Dibujar YOLO (Segmentación y Enmarcado Estético)
                for det in last_yolo_detections:
                    x1, y1, x2, y2 = det['box']
                    # Color dinámico: Cyan para personas, Verde para otros objetos
                    color = TRON_CYAN if "PERSON" in det.get('class_name', '') else (0, 255, 0)
                    
                    # 1. Dibujar Máscara de Segmentación (si existe)
                    if det.get('mask') is not None:
                        overlay = frame.copy()
                        cv2.fillPoly(overlay, [det['mask']], color)
                        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
                        cv2.polylines(frame, [det['mask']], True, color, 1)

                    # 2. Dibujar Enmarcado Estético Tron (Esquinas reforzadas con brillo)
                    length = int(min(x2-x1, y2-y1) * 0.15)
                    
                    for c, t in [(TRON_GLOW, 4), (color, 2)]: # Efecto Glow
                        # Top-left
                        cv2.line(frame, (x1, y1), (x1 + length, y1), c, t)
                        cv2.line(frame, (x1, y1), (x1, y1 + length), c, t)
                        # Top-right
                        cv2.line(frame, (x2, y1), (x2 - length, y1), c, t)
                        cv2.line(frame, (x2, y1), (x2, y1 + length), c, t)
                        # Bottom-left
                        cv2.line(frame, (x1, y2), (x1 + length, y2), c, t)
                        cv2.line(frame, (x1, y2), (x1, y2 - length), c, t)
                        # Bottom-right
                        cv2.line(frame, (x2, y2), (x2 - length, y2), c, t)
                        cv2.line(frame, (x2, y2), (x2, y2 - length), c, t)

                    # Rectángulo base muy fino
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)

                    # Etiqueta estilo TRON
                    class_label = det.get('class_name', 'OBJETO').upper()
                    label = f"// {class_label} > {int(det['conf']*100)}%"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    
                    # Fondo semi-transparente para el texto
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (x1, y1 - th - 15), (x1 + tw + 15, y1), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
                    
                    # Texto con sombra ligera para legibilidad
                    cv2.putText(frame, label, (x1 + 6, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, TRON_WHITE, 1, cv2.LINE_AA)
                
                # Dibujar Rostros
                for det in last_face_detections:
                    top, right, bottom, left = det['box']
                    
                    # Glow para el cuadro de la cara
                    cv2.rectangle(frame, (left, top), (right, bottom), TRON_GLOW, 3, cv2.LINE_AA)
                    cv2.rectangle(frame, (left, top), (right, bottom), TRON_CYAN, 1, cv2.LINE_AA)
                    
                    # Nombre y Confianza (Header)
                    label_text = det['label'].upper()
                    (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                    
                    # Fondo header
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (left, top - th - 20), (left + tw + 20, top), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                    
                    cv2.putText(frame, label_text, (left + 10, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, TRON_WHITE, 2, cv2.LINE_AA)
                    
                    # Información Adicional (Biografía)
                    if det.get('details'):
                        for i, line in enumerate(det['details']):
                            # Barra lateral estilo glitch/técnico
                            cv2.line(frame, (left - 5, bottom + 25 + (i * 20)), (left - 5, bottom + 40 + (i * 20)), TRON_CYAN, 2)
                            cv2.putText(frame, line.upper(), (left + 5, bottom + 35 + (i * 20)), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 255, 255), 1, cv2.LINE_AA)

                frame_count += 1
                
                # --- Envío del Frame ---
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if not ret: continue
                
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                time.sleep(0.03)

            except Exception as e:
                print(f"❌ Error en bucle de stream {camera_id}: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)
                continue

    finally:
        print(f"🧹 Limpiando y cerrando stream: {camera_id}")
        # Liberar del pool compartido en lugar de cerrar directamente
        if source:
            release_shared_cap(source)
            
        with cameras_lock:
            if camera_id in active_cameras:
                active_cameras.pop(camera_id)
        print(f"🔚 Stream finalizado: {camera_id}")


def generate_frames():
    """Generador de frames para la cámara principal (compatibilidad hacia atrás)"""
    global camera, camera_lock, is_streaming
    
    frame_count = 0
    last_detection_time = 0
    detection_interval = 1  # segundos
    
    while True:
        with camera_lock:
            if not is_streaming or camera is None or not camera.isOpened():
                # Si el stream está detenido, enviar un frame negro
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(black_frame, "Stream Detenido", (180, 240), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                ret, buffer = cv2.imencode('.jpg', black_frame)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                          b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(1)
                continue

            success, frame = camera.read()
            if not success:
                print("Error leyendo frame de la cámara principal")
                time.sleep(0.5)
                continue

        # Procesamiento de frames
        current_time = time.time()
        if current_time - last_detection_time > detection_interval:
            last_detection_time = current_time
            
            # Detección de objetos
            if OBJECT_DETECTION_ENABLED:
                try:
                    detections = detect_objects_dnn(frame)
                    if detections:
                        # Estabilizar detecciones
                        detections = stabilize_detections(detections)
                        
                        for det in detections:
                            x1, y1, x2, y2 = det['box']
                            label = f"{det['class']} ({det['confidence']:.2f})"
                            
                            # Color diferente para personas
                            color = (255, 255, 0) if det['class'] == 'person' else (0, 255, 0)
                            
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                except Exception as e:
                    print(f"Error en detección de objetos: {e}")

            # Detección de caras
            rgb_small_frame = cv2.cvtColor(cv2.resize(frame, (0, 0), fx=0.25, fy=0.25), cv2.COLOR_BGR2RGB)
            with face_lock:
                face_locations = face_recognition.face_locations(rgb_small_frame)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                with face_lock:
                    matches = face_recognition.compare_faces(reference_encodings, face_encoding)
                name = "Desconocido"
                color = (0, 0, 255)

                if True in matches:
                    first_match_index = matches.index(True)
                    
                    current_index = 0
                    for person_name, person_data in reference_faces.items():
                        num_encodings = len(person_data['encodings'])
                        if first_match_index < current_index + num_encodings:
                            name = person_name.split('_')[0].split('-')[0].strip()
                            color = (0, 255, 0)
                            break
                        current_index += num_encodings
                else:
                    # ...existing code...
                    if time.time() - save_unknown_face.last_save_time > 5:
                        save_unknown_face(frame, (top, right, bottom, left), face_encoding)
                        save_unknown_face.last_save_time = time.time()

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # Etiqueta de nombre
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)
                
                # Información Adicional (Biografía) para compatibilidad
                details = PERSON_DETAILS.get(name, [])
                for i, line in enumerate(details):
                    cv2.putText(frame, line, (left, bottom + 20 + (i * 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Comprimir y enviar frame
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ret:
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                  b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.03) # Limitar a ~30 FPS


@app.route('/')
def index():
    """Página principal"""
    return render_template('beautiful.html')

@app.route('/video_feed')
def video_feed():
    # Stream individual con parámetro de fuente
    source_param = request.args.get('source')
    camera_id = request.args.get('camera_id')
    
    print(f"🎥 video_feed llamado - source_param: {source_param}, camera_id: {camera_id}")
    
    if source_param or camera_id:
        # Stream multi-cámara
        try:
            source = None
            if source_param:
                # Limpiar y decodificar la URL
                source = source_param.strip().strip('"').strip("'")
                # Si es un número (cámara local), convertir a int
                if source.isdigit():
                    source = int(source)
                    print(f"  → Source es cámara local: {source}")
                else:
                    print(f"  → Source es URL/RTSP: {source}")
            elif camera_id:
                # Si solo tenemos camera_id, buscar en las cámaras activas
                with cameras_lock:
                    if camera_id in active_cameras:
                        source = active_cameras[camera_id]['source']
                        print(f"  → Cámara {camera_id} encontrada en activas con source: {source}")
                    else:
                        print(f"⚠️ Cámara {camera_id} no encontrada en activas")
                        return Response(b'', mimetype='multipart/x-mixed-replace; boundary=frame')
            
            if source is not None:
                print(f"📹 Iniciando stream para cámara {camera_id} con fuente: {source} (tipo: {type(source).__name__})")
                return Response(generate_frames_multicam(source, camera_id),
                              mimetype='multipart/x-mixed-replace; boundary=frame')
            else:
                print(f"⚠️ No se pudo determinar la fuente para cámara {camera_id}")
                return Response(b'', mimetype='multipart/x-mixed-replace; boundary=frame')
        except Exception as e:
            print(f"❌ Error en video_feed multi-cámara: {e}")
            import traceback
            traceback.print_exc()
            return Response(b'', mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        # Stream principal (compatibilidad)
        return Response(generate_frames(),
                      mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_stream')
def start_stream():
    global is_streaming, camera
    try:
        if camera is None or not camera.isOpened():
            print("Inicializando cámara para stream...")
            if not init_camera():
                return jsonify({'success': False, 'error': 'No se pudo inicializar la cámara'})

        is_streaming = True
        print("Stream iniciado correctamente")
        return jsonify({'success': True, 'message': 'Stream iniciado'})

    except Exception as e:
        print(f"Error iniciando stream: {e}")
        return jsonify({'success': False, 'error': f'Error iniciando stream: {str(e)}'})

@app.route('/stop_stream')
def stop_stream():
    global is_streaming, camera
    try:
        is_streaming = False
        print("Deteniendo stream...")

        with camera_lock:
            if camera is not None:
                try:
                    camera.release()
                    print("Cámara liberada correctamente")
                except Exception as e:
                    print(f"Error liberando cámara: {e}")
                finally:
                    camera = None

        return jsonify({'success': True, 'message': 'Stream detenido'})
    except Exception as e:
        print(f"Error deteniendo stream: {e}")
        return jsonify({'success': False, 'error': f'Error deteniendo stream: {str(e)}'})

@app.route('/api/upload_reference', methods=['POST'])
def upload_reference():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se seleccionó ningún archivo'}), 400

        file = request.files['file']
        name = request.form.get('name', '').strip()

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No se seleccionó ningún archivo'}), 400

        if not name:
            return jsonify({'success': False, 'error': 'El nombre es requerido'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Tipo de archivo no permitido'}), 400

        # Leer la imagen
        try:
            # Intentar cargar con face_recognition primero
            image = face_recognition.load_image_file(file)
        except Exception as e:
            print(f"Error cargando imagen con face_recognition: {e}")
            # Si falla, intentar con PIL y convertir
            try:
                file.seek(0)  # Resetear posición del archivo
                pil_image = Image.open(file)
                # Convertir a RGB si es necesario
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                # Convertir PIL a numpy array
                image = np.array(pil_image)
            except Exception as e2:
                print(f"Error cargando imagen con PIL: {e2}")
                return jsonify({'success': False, 'error': f'No se pudo cargar la imagen: {str(e2)}'}), 400

        # MEJORA: Detectar caras con modelo CNN para mejor precisión
        try:
            face_locations = face_recognition.face_locations(image, model="cnn")
        except:
            face_locations = face_recognition.face_locations(image, model="hog")

        if len(face_locations) == 0:
            # Fallback a HOG si CNN no detecta
            face_locations = face_recognition.face_locations(image, model="hog")

            if len(face_locations) == 0:
                return jsonify({'success': False, 'error': 'No se detectaron caras en la imagen. Asegúrate de que la imagen contenga una cara visible y bien iluminada.'}), 400

        # MEJORA: Usar num_jitters para mejor encoding de referencias
        face_encodings = face_recognition.face_encodings(
            image, 
            face_locations,
            num_jitters=3  # Múltiples pasadas para mejor precisión
        )

        # Si hay múltiples caras, usar solo la más grande (probablemente la principal)
        if len(face_encodings) > 1:
            print(f"Advertencia: Se detectaron {len(face_encodings)} caras. Usando la cara más grande.")
            # Calcular el tamaño de cada cara y seleccionar la más grande
            face_sizes = [(b - t) * (r - l) for (t, r, b, l) in face_locations]
            sorted_indices = sorted(range(len(face_sizes)), key=lambda i: face_sizes[i], reverse=True)
            face_locations = [face_locations[i] for i in sorted_indices[:1]]
            face_encodings = [face_encodings[i] for i in sorted_indices[:1]]

        # Guardar imagen de referencia
        filename = f"{name}_{int(time.time())}.jpg"
        filepath = os.path.join(REFERENCE_FOLDER, filename)

        pil_image = Image.fromarray(image)
        pil_image.save(filepath, 'JPEG')

        # MEJORA: Guardar múltiples encodings si hay múltiples caras
        if name not in reference_faces:
            reference_faces[name] = {
                'encodings': [],
                'image_paths': [],
                'face_locations': []
            }
        
        # Agregar todos los encodings encontrados
        for encoding, location in zip(face_encodings, face_locations):
            reference_faces[name]['encodings'].append(encoding)
            reference_faces[name]['image_paths'].append(filepath)
            reference_faces[name]['face_locations'].append(location)
        
        # Reconstruir lista plana de encodings para matching rápido
        reference_encodings = []
        for face_name, face_data in reference_faces.items():
            reference_encodings.extend(face_data['encodings'])

        # Convertir imagen a base64 para mostrar
        buffered = io.BytesIO()
        pil_image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return jsonify({
            'success': True,
            'message': f'Cara de referencia "{name}" guardada correctamente',
            'name': name,
            'image': f"data:image/jpeg;base64,{img_str}",
            'face_location': {
                'top': int(face_locations[0][0]),
                'right': int(face_locations[0][1]),
                'bottom': int(face_locations[0][2]),
                'left': int(face_locations[0][3])
            }
        })

    except Exception as e:
        print(f"Error en upload_reference: {e}")
        return jsonify({'success': False, 'error': f'Error procesando la imagen: {str(e)}'}), 500

@app.route('/api/reference_faces')
def get_reference_faces():
    faces_data = []
    for name, face_data in reference_faces.items():
        # Manejar estructura con múltiples imágenes por persona
        # face_data tiene: 'encodings', 'image_paths', 'face_locations'
        image_paths = face_data.get('image_paths', [])
        
        # Usar la primera imagen si hay múltiples
        if len(image_paths) > 0:
            # Obtener solo el nombre del archivo sin la ruta completa
            filename = os.path.basename(image_paths[0])
            faces_data.append({
                'name': name,
                'image_filename': filename,
                'image_url': f'/api/reference_image/{filename}',
                'num_images': len(image_paths),
                'num_encodings': len(face_data.get('encodings', []))
            })
        else:
            # Si no hay imágenes, aún así incluir la persona
            faces_data.append({
                'name': name,
                'image_filename': None,
                'image_url': None,
                'num_images': 0,
                'num_encodings': len(face_data.get('encodings', []))
            })
    
    return jsonify({
        'success': True,
        'faces': list(reference_faces.keys()),
        'faces_data': faces_data,
        'count': len(reference_faces)
    })

@app.route('/api/reference_image/<filename>')
def get_reference_image(filename):
    """Servir imágenes de referencia"""
    try:
        filepath = os.path.join(REFERENCE_FOLDER, filename)
        if os.path.exists(filepath):
            return send_from_directory(REFERENCE_FOLDER, filename)
        else:
            return jsonify({'error': 'Imagen no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_reference/<name>', methods=['DELETE'])
def delete_reference(name):
    global reference_faces, reference_encodings
    try:
        if name in reference_faces:
            # Eliminar todas las imágenes asociadas a esta persona
            image_paths = reference_faces[name].get('image_paths', [])
            for image_path in image_paths:
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as e:
                        print(f"⚠️ Error eliminando {image_path}: {e}")

            # Eliminar la persona del diccionario
            del reference_faces[name]
            
            # Reconstruir lista plana de encodings para matching rápido
            reference_encodings = []
            for face_name, face_data in reference_faces.items():
                reference_encodings.extend(face_data.get('encodings', []))

            return jsonify({'success': True, 'message': f'Cara "{name}" eliminada'})
        else:
            return jsonify({'success': False, 'error': 'Cara no encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== ENDPOINTS PARA RTSP Y CONFIGURACIÓN DE FUENTE ==========

@app.route('/api/set_video_source', methods=['POST'])
def set_video_source():
    """Configurar fuente de video (webcam local o RTSP)"""
    global camera, camera_source, is_streaming
    
    try:
        data = request.get_json()
        source = data.get('source', 0)
        auto_start = data.get('auto_start', True)  # Por defecto iniciar automáticamente
        
        # Detener stream si está activo
        if is_streaming:
            is_streaming = False
            time.sleep(0.5)
        
        # Cerrar cámara actual
        if camera is not None:
            camera.release()
            camera = None
        
        # Configurar nueva fuente
        camera_source = source
        
        # Inicializar nueva fuente
        if init_camera(source):
            # NUEVO: Iniciar stream automáticamente después de configurar
            if auto_start:
                is_streaming = True
                print(f"✅ Stream iniciado automáticamente para fuente: {source}")
            
            return jsonify({
                'success': True,
                'message': f'Fuente de video configurada: {source}',
                'source': camera_source,
                'stream_started': auto_start
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo inicializar la fuente de video'
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get_video_source', methods=['GET'])
def get_video_source():
    """Obtener fuente de video actual"""
    return jsonify({
        'source': camera_source,
        'is_streaming': is_streaming
    })

@app.route('/api/predefined_cameras', methods=['GET'])
def get_predefined_cameras():
    """Obtener lista de cámaras RTSP predefinidas"""
    try:
        return jsonify({
            'success': True,
            'cameras': PREDEFINED_CAMERAS
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== ENDPOINTS PARA CRUD DE DETECCIONES ==========

@app.route('/api/detections', methods=['GET'])
def get_detections():
    """Obtener todas las detecciones con filtros opcionales"""
    try:
        detections = load_detections()
        
        # Filtros opcionales
        detection_type = request.args.get('type')  # 'unknown', 'known'
        status = request.args.get('status')  # 'pending', 'reviewed', 'archived'
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Aplicar filtros
        filtered = detections
        if detection_type:
            filtered = [d for d in filtered if d.get('type') == detection_type]
        if status:
            filtered = [d for d in filtered if d.get('status') == status]
        
        # Ordenar por timestamp (más recientes primero)
        filtered.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Paginación
        total = len(filtered)
        if limit:
            filtered = filtered[offset:offset+limit]
        else:
            filtered = filtered[offset:]
        
        return jsonify({
            'success': True,
            'detections': filtered,
            'total': total,
            'offset': offset,
            'limit': limit
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/detections/<detection_id>', methods=['GET'])
def get_detection(detection_id):
    """Obtener una detección específica"""
    try:
        detections = load_detections()
        detection = next((d for d in detections if d.get('id') == detection_id), None)
        
        if detection:
            return jsonify({'success': True, 'detection': detection})
        else:
            return jsonify({'success': False, 'error': 'Detección no encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/detections/<detection_id>', methods=['PUT'])
def update_detection_endpoint(detection_id):
    """Actualizar una detección"""
    try:
        data = request.get_json()
        
        # Campos permitidos para actualizar
        allowed_fields = ['name', 'notes', 'status', 'type']
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        if update_detection(detection_id, updates):
            return jsonify({'success': True, 'message': 'Detección actualizada'})
        else:
            return jsonify({'success': False, 'error': 'Detección no encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/detections/<detection_id>', methods=['DELETE'])
def delete_detection_endpoint(detection_id):
    """Eliminar una detección"""
    try:
        if delete_detection(detection_id):
            return jsonify({'success': True, 'message': 'Detección eliminada'})
        else:
            return jsonify({'success': False, 'error': 'Detección no encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/detections', methods=['POST'])
def create_detection():
    """Crear una nueva detección manualmente"""
    try:
        data = request.get_json()
        
        detection = {
            'id': datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
            'timestamp': datetime.now().isoformat(),
            'type': data.get('type', 'unknown'),
            'image_path': data.get('image_path', ''),
            'face_location': data.get('face_location', []),
            'confidence': data.get('confidence'),
            'name': data.get('name'),
            'notes': data.get('notes', ''),
            'status': data.get('status', 'pending')
        }
        
        save_detection(detection)
        return jsonify({'success': True, 'detection': detection}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== ENDPOINTS PARA ESTADÍSTICAS KPI ==========

@app.route('/api/kpi', methods=['GET'])
def get_kpi():
    """Obtener estadísticas KPI"""
    try:
        stats = get_kpi_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== ENDPOINT PARA SERVIR IMÁGENES DE DESCONOCIDOS ==========

@app.route('/api/unknown_image/<filename>')
def get_unknown_image(filename):
    """Servir imágenes de caras (conocidas y desconocidas)"""
    try:
        # Buscar en la carpeta de unknown_faces (donde se guardan todas las detecciones)
        filepath = os.path.join(UNKNOWN_FACES_FOLDER, filename)
        if os.path.exists(filepath):
            return send_from_directory(UNKNOWN_FACES_FOLDER, filename)
        else:
            return jsonify({'error': 'Imagen no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detection_image/<path:filename>')
def get_detection_image(filename):
    """Servir imágenes de detecciones (ruta completa relativa)"""
    try:
        # filename puede ser una ruta relativa como "unknown_faces/unknown_xxx.jpg"
        # o solo el nombre del archivo
        if os.path.sep in filename:
            # Es una ruta completa relativa
            filepath = os.path.join('.', filename)
        else:
            # Solo el nombre del archivo, buscar en unknown_faces
            filepath = os.path.join(UNKNOWN_FACES_FOLDER, filename)
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            directory = os.path.dirname(filepath) or '.'
            filename_only = os.path.basename(filepath)
            return send_from_directory(directory, filename_only)
        else:
            return jsonify({'error': 'Imagen no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("INICIANDO SERVIDOR FLASK")
    print("=" * 60)
    
    # 1. Cargar caras de referencia (usando dlib/face_recognition)
    print("\n[1] Cargando caras de referencia...")
    load_reference_faces()
    print("[2] Caras de referencia cargadas")
    
    # 2. Inicializar Modelos de Detección (YOLO, SSD, etc.)
    # Se hace después para evitar conflictos de librerías en macOS
    print("\n[3] Inicializando modelos de detección...")
    init_models()
    
    print("\n[4] Iniciando servidor Flask en http://0.0.0.0:5005")
    print("=" * 60)
    print("")

    try:
        # threaded=True permite ver múltiples cámaras simultáneamente
        app.run(debug=False, host='0.0.0.0', port=5005, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\nCerrando aplicación...")
    finally:
        if camera is not None:
            camera.release()
            print("Cámara liberada al cerrar")
