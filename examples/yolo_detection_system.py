#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Detección en Tiempo Real con YOLOv8
Diseñado para videovigilancia profesional (estilo Hikvision/iVMS)
Optimizado para GEO CAM - Sistema de Infracciones

Autor: Sistema de Detección Inteligente
Versión: 1.0
"""

import cv2
import numpy as np
from ultralytics import YOLO
import torch
from datetime import datetime
import time
from collections import deque
import os
import sys

# Intentar importar cvzone (opcional)
try:
    from cvzone.FPS import FPS
    CVZONE_AVAILABLE = True
except ImportError:
    CVZONE_AVAILABLE = False
    print("⚠️  cvzone no disponible, usando implementación propia de FPS")

# Configuración del sistema
CONFIG = {
    'model_path': 'yolov8n.pt',  # Modelo YOLOv8n (nano - más rápido)
    'confidence_threshold': 0.5,  # Umbral de confianza mínimo
    'iou_threshold': 0.45,  # Umbral IoU para NMS
    'target_classes': ['person', 'car', 'motorcycle', 'bus', 'truck'],  # Clases a detectar
    'min_area_ratio': 0.01,  # Área mínima (1% del frame)
    'stabilization_frames': 5,  # Frames para estabilización
    'fps_history_size': 30,  # Historial para cálculo de FPS
}

# Colores profesionales estilo videovigilancia
COLORS = {
    'person': (0, 0, 255),  # Rojo BGR
    'car': (0, 165, 255),  # Naranja BGR
    'motorcycle': (255, 0, 255),  # Magenta BGR
    'bus': (0, 255, 255),  # Cyan BGR
    'truck': (0, 255, 255),  # Cyan BGR
    'background': (0, 0, 0),  # Negro para overlays
    'text': (255, 255, 255),  # Blanco para texto
    'info': (0, 255, 0),  # Verde para info
}

class DetectionStabilizer:
    """Estabilizador de detecciones para reducir falsos positivos"""
    
    def __init__(self, history_size=5):
        self.history_size = history_size
        self.detection_history = deque(maxlen=history_size)
    
    def stabilize(self, detections):
        """Estabilizar detecciones usando historial temporal"""
        if not detections:
            return []
        
        self.detection_history.append(detections)
        
        if len(self.detection_history) < 2:
            return detections
        
        # Agrupar detecciones por clase y posición
        class_groups = {}
        for frame_dets in self.detection_history:
            for det in frame_dets:
                class_name = det['class']
                if class_name not in class_groups:
                    class_groups[class_name] = []
                class_groups[class_name].append(det)
        
        # Promediar detecciones estables
        stabilized = []
        for class_name, dets in class_groups.items():
            if len(dets) >= 2:  # Aparece en al menos 2 frames
                # Agrupar por proximidad espacial
                groups = self._group_by_proximity(dets)
                for group in groups:
                    if len(group) >= 2:
                        avg_box = np.mean([d['box'] for d in group], axis=0)
                        avg_conf = np.mean([d['confidence'] for d in group])
                        if avg_conf >= CONFIG['confidence_threshold']:
                            stabilized.append({
                                'class': class_name,
                                'confidence': avg_conf,
                                'box': tuple(avg_box.astype(int))
                            })
        
        return stabilized if stabilized else detections
    
    def _group_by_proximity(self, detections, iou_threshold=0.3):
        """Agrupar detecciones por proximidad usando IoU"""
        groups = []
        for det in detections:
            matched = False
            for group in groups:
                avg_box = np.mean([g['box'] for g in group], axis=0)
                if self._calculate_iou(det['box'], tuple(avg_box)) > iou_threshold:
                    group.append(det)
                    matched = True
                    break
            if not matched:
                groups.append([det])
        return groups
    
    @staticmethod
    def _calculate_iou(box1, box2):
        """Calcular Intersection over Union"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
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


class FPSMonitor:
    """Monitor de FPS para optimización (con cvzone si está disponible)"""
    
    def __init__(self, history_size=30):
        self.history_size = history_size
        self.fps_history = deque(maxlen=history_size)
        self.last_time = time.time()
        
        # Usar cvzone si está disponible
        if CVZONE_AVAILABLE:
            try:
                self.cvzone_fps = FPS()
            except:
                self.cvzone_fps = None
        else:
            self.cvzone_fps = None
    
    def update(self):
        """Actualizar cálculo de FPS"""
        if self.cvzone_fps is not None:
            self.cvzone_fps.update()
            return self.cvzone_fps.fps()
        else:
            current_time = time.time()
            fps = 1.0 / (current_time - self.last_time) if current_time != self.last_time else 0
            self.fps_history.append(fps)
            self.last_time = current_time
            return fps
    
    def get_average_fps(self):
        """Obtener FPS promedio"""
        if self.cvzone_fps is not None:
            return self.cvzone_fps.fps()
        return np.mean(self.fps_history) if self.fps_history else 0


class YOLODetectionSystem:
    """Sistema principal de detección YOLOv8"""
    
    def __init__(self, source=0, model_path=None):
        """
        Inicializar sistema de detección
        
        Args:
            source: Fuente de video (0 para webcam, ruta de archivo, o URL RTSP)
            model_path: Ruta al modelo YOLO (None para descargar automáticamente)
        """
        self.source = source
        self.model_path = model_path or CONFIG['model_path']
        self.model = None
        self.stabilizer = DetectionStabilizer(CONFIG['stabilization_frames'])
        self.fps_monitor = FPSMonitor(CONFIG['fps_history_size'])
        self.detection_count = {'person': 0, 'car': 0, 'motorcycle': 0, 'bus': 0, 'truck': 0}
        
        self._load_model()
        self._init_video_source()
    
    def _load_model(self):
        """Cargar modelo YOLOv8 (descarga automática si no existe)"""
        try:
            # Verificar si el archivo existe localmente
            if os.path.exists(self.model_path):
                print(f"📥 Cargando modelo YOLOv8 desde: {self.model_path}")
                self.model = YOLO(self.model_path)
            else:
                print(f"📥 Modelo no encontrado localmente, descargando {self.model_path}...")
                # YOLO descarga automáticamente si no existe
                self.model = YOLO(self.model_path)
                print(f"✅ Modelo {self.model_path} descargado y cargado")
            
            print(f"✅ Modelo YOLOv8 cargado exitosamente")
            
            # Verificar dispositivo
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f"🖥️  Dispositivo: {device}")
            
            # Información del modelo
            if hasattr(self.model, 'names'):
                print(f"📊 Clases disponibles: {len(self.model.names)}")
            
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            print("📥 Intentando descargar modelo YOLOv8n por defecto...")
            try:
                self.model = YOLO('yolov8n.pt')  # Descarga automática
                print("✅ Modelo YOLOv8n descargado y cargado")
            except Exception as e2:
                print(f"❌ Error crítico: {e2}")
                raise
    
    def _init_video_source(self):
        """Inicializar fuente de video"""
        try:
            if isinstance(self.source, int) or (isinstance(self.source, str) and self.source.isdigit()):
                self.cap = cv2.VideoCapture(int(self.source))
                print(f"📹 Cámara {self.source} inicializada")
            elif isinstance(self.source, str):
                if self.source.startswith('rtsp://') or self.source.startswith('http://'):
                    self.cap = cv2.VideoCapture(self.source)
                    print(f"🌐 Stream RTSP/HTTP inicializado: {self.source}")
                else:
                    self.cap = cv2.VideoCapture(self.source)
                    print(f"📁 Archivo de video inicializado: {self.source}")
            else:
                raise ValueError("Fuente de video no válida")
            
            if not self.cap.isOpened():
                raise Exception("No se pudo abrir la fuente de video")
                
        except Exception as e:
            print(f"❌ Error inicializando fuente de video: {e}")
            raise
    
    def _filter_detections(self, detections, frame_shape):
        """Filtrar detecciones por tamaño y confianza"""
        h, w = frame_shape[:2]
        min_area = (w * h) * CONFIG['min_area_ratio']
        filtered = []
        
        for det in detections:
            x1, y1, x2, y2 = det['box']
            area = (x2 - x1) * (y2 - y1)
            
            # Filtrar por área mínima
            if area < min_area:
                continue
            
            # Filtrar por confianza según clase (umbrales más altos para reducir falsos positivos)
            if det['class'] == 'person':
                if det['confidence'] < 0.55:  # Umbral más alto para personas
                    continue
            elif det['class'] in ['car', 'motorcycle']:
                if det['confidence'] < 0.5:  # Umbral medio para vehículos
                    continue
            else:
                if det['confidence'] < CONFIG['confidence_threshold']:
                    continue
            
            # Filtrar por clases objetivo
            if det['class'] not in CONFIG['target_classes']:
                continue
            
            filtered.append(det)
        
        return filtered
    
    def _process_detections(self, results, frame_shape):
        """Procesar resultados de YOLO"""
        detections = []
        
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    # Obtener coordenadas
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    
                    # Obtener nombre de clase
                    class_name = result.names[class_id] if hasattr(result, 'names') else f"class_{class_id}"
                    
                    # Validar coordenadas
                    h, w = frame_shape[:2]
                    x1 = max(0, min(int(x1), w))
                    y1 = max(0, min(int(y1), h))
                    x2 = max(0, min(int(x2), w))
                    y2 = max(0, min(int(y2), h))
                    
                    if x2 > x1 and y2 > y1:
                        detections.append({
                            'class': class_name,
                            'confidence': confidence,
                            'box': (x1, y1, x2, y2)
                        })
        
        # Filtrar detecciones
        filtered = self._filter_detections(detections, frame_shape)
        
        # Estabilizar
        stabilized = self.stabilizer.stabilize(filtered)
        
        return stabilized
    
    def _draw_detection(self, frame, det):
        """Dibujar una detección en el frame (estilo profesional videovigilancia)"""
        x1, y1, x2, y2 = det['box']
        class_name = det['class']
        confidence = det['confidence']
        
        # Obtener color según clase
        color = COLORS.get(class_name, COLORS['text'])
        
        # Dibujar overlay semi-transparente (coloreado visible)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        
        # Dibujar bounding box con grosor variable según confianza
        thickness = 3 if confidence > 0.7 else 2
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        
        # Preparar etiqueta con porcentaje
        label = f"{class_name.upper()} {confidence:.0%}"
        label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        
        # Fondo para etiqueta (arriba del bounding box)
        label_y = max(y1, label_size[1] + 10)
        cv2.rectangle(frame,
                     (x1, label_y - label_size[1] - 5),
                     (x1 + label_size[0] + 10, label_y + baseline + 5),
                     color, cv2.FILLED)
        
        # Texto de etiqueta
        cv2.putText(frame, label, (x1 + 5, label_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLORS['text'], 2)
        
        # Indicador de confianza en esquina (opcional)
        if confidence < 0.6:
            # Marcar detecciones de baja confianza
            cv2.circle(frame, (x2 - 10, y1 + 10), 5, (0, 255, 255), -1)
    
    def _draw_hud(self, frame, detections):
        """Dibujar HUD (Head-Up Display) estilo videovigilancia"""
        h, w = frame.shape[:2]
        
        # Panel superior izquierdo
        panel_y = 10
        panel_x = 10
        
        # Fondo semi-transparente para panel
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x - 5, panel_y - 5), (panel_x + 300, panel_y + 150),
                     COLORS['background'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # FPS
        fps = self.fps_monitor.get_average_fps()
        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(frame, fps_text, (panel_x, panel_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS['info'], 2)
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (panel_x, panel_y + 55),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS['text'], 1)
        
        # Contador de detecciones
        y_offset = 85
        for class_name in CONFIG['target_classes']:
            count = sum(1 for d in detections if d['class'] == class_name)
            if count > 0:
                color = COLORS.get(class_name, COLORS['text'])
                text = f"{class_name.upper()}: {count}"
                cv2.putText(frame, text, (panel_x, panel_y + y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                y_offset += 30
        
        # Panel inferior derecho - Información del sistema
        info_y = h - 80
        info_x = w - 250
        
        overlay = frame.copy()
        cv2.rectangle(overlay, (info_x - 5, info_y - 5), (info_x + 240, info_y + 70),
                     COLORS['background'], -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        cv2.putText(frame, "YOLOv8 Detection System", (info_x, info_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS['info'], 2)
        cv2.putText(frame, "GEO CAM Ready", (info_x, info_y + 55),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS['text'], 1)
    
    def run(self):
        """Ejecutar sistema de detección"""
        print("\n" + "="*60)
        print("🚀 Sistema de Detección YOLOv8 Iniciado")
        print("="*60)
        print(f"📹 Fuente: {self.source}")
        print(f"🎯 Clases objetivo: {', '.join(CONFIG['target_classes'])}")
        print(f"⚙️  Confianza mínima: {CONFIG['confidence_threshold']}")
        print("="*60 + "\n")
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("⚠️  No se pudo leer frame, reintentando...")
                    time.sleep(0.1)
                    continue
                
                # Actualizar FPS
                self.fps_monitor.update()
                
                # Ejecutar detección
                results = self.model(frame, conf=CONFIG['confidence_threshold'],
                                   iou=CONFIG['iou_threshold'], verbose=False)
                
                # Procesar detecciones
                detections = self._process_detections(results, frame.shape)
                
                # Dibujar detecciones
                for det in detections:
                    self._draw_detection(frame, det)
                
                # Dibujar HUD
                self._draw_hud(frame, detections)
                
                # Mostrar frame
                cv2.imshow('YOLOv8 Detection System - GEO CAM', frame)
                
                # Control de salida
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n🛑 Deteniendo sistema...")
                    break
                elif key == ord('s'):
                    # Guardar captura
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"detection_{timestamp}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"📸 Captura guardada: {filename}")
        
        except KeyboardInterrupt:
            print("\n🛑 Interrupción del usuario")
        except Exception as e:
            print(f"\n❌ Error en ejecución: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpiar recursos"""
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()
        print("✅ Recursos liberados")


def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sistema de Detección YOLOv8 para GEO CAM')
    parser.add_argument('--source', type=str, default='0',
                       help='Fuente de video (0 para webcam, ruta de archivo, o URL RTSP)')
    parser.add_argument('--model', type=str, default=None,
                       help='Ruta al modelo YOLO (None para descargar automáticamente)')
    parser.add_argument('--conf', type=float, default=0.5,
                       help='Umbral de confianza (default: 0.5)')
    
    args = parser.parse_args()
    
    # Actualizar configuración
    CONFIG['confidence_threshold'] = args.conf
    
    # Convertir source a int si es un número
    try:
        source = int(args.source)
    except ValueError:
        source = args.source
    
    # Crear y ejecutar sistema
    system = YOLODetectionSystem(source=source, model_path=args.model)
    system.run()


if __name__ == '__main__':
    main()

