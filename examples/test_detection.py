#!/usr/bin/env python3
"""
Script de testing para verificar detección de personas y rostros a distancia
"""

import cv2
import face_recognition
import numpy as np
import time
import os
from datetime import datetime

# Configuración
REFERENCE_FOLDER = 'reference_faces'
TEST_OUTPUT_FOLDER = 'test_results'
os.makedirs(TEST_OUTPUT_FOLDER, exist_ok=True)

def load_reference_faces():
    """Cargar caras de referencia"""
    reference_faces = {}
    reference_encodings = []
    
    if not os.path.exists(REFERENCE_FOLDER):
        print("❌ No hay carpeta de referencias")
        return reference_faces, reference_encodings
    
    files = os.listdir(REFERENCE_FOLDER)
    print(f"📁 Cargando {len(files)} archivos de referencia...")
    
    for filename in files:
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            filepath = os.path.join(REFERENCE_FOLDER, filename)
            try:
                image = face_recognition.load_image_file(filepath)
                face_locations = face_recognition.face_locations(image, model="hog")
                
                if len(face_locations) > 0:
                    face_encodings = face_recognition.face_encodings(image, face_locations, num_jitters=2)
                    name = os.path.splitext(filename)[0]
                    
                    if name not in reference_faces:
                        reference_faces[name] = {'encodings': []}
                    
                    for encoding in face_encodings:
                        reference_faces[name]['encodings'].append(encoding)
                        reference_encodings.append(encoding)
                    
                    print(f"✅ {name}: {len(face_encodings)} encoding(s)")
            except Exception as e:
                print(f"❌ Error cargando {filename}: {e}")
    
    print(f"\n📊 Total: {len(reference_faces)} personas, {len(reference_encodings)} encodings\n")
    return reference_faces, reference_encodings

def test_detection(camera_source=0, duration=30):
    """Test de detección en tiempo real"""
    print("=" * 60)
    print("🧪 TEST DE DETECCIÓN DE PERSONAS Y ROSTROS")
    print("=" * 60)
    print(f"📹 Fuente: {camera_source}")
    print(f"⏱️  Duración: {duration} segundos")
    print(f"🎯 Objetivo: Detectar a 7 metros de distancia")
    print("=" * 60)
    print()
    
    # Cargar referencias
    reference_faces, reference_encodings = load_reference_faces()
    
    # Inicializar cámara
    print("📹 Inicializando cámara...")
    cap = cv2.VideoCapture(camera_source)
    
    if not cap.isOpened():
        print("❌ Error: No se pudo abrir la cámara")
        return
    
    # Configurar resolución más alta para mejor detección a distancia
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"✅ Cámara configurada: {width}x{height} @ {fps:.1f} FPS")
    print()
    
    # Estadísticas
    stats = {
        'total_frames': 0,
        'faces_detected': 0,
        'persons_detected': 0,
        'known_faces': 0,
        'unknown_faces': 0,
        'detection_times': [],
        'face_sizes': []
    }
    
    start_time = time.time()
    frame_count = 0
    
    print("🎬 Iniciando test... (Presiona 'q' para salir)\n")
    
    try:
        while time.time() - start_time < duration:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Error leyendo frame")
                continue
            
            stats['total_frames'] += 1
            frame_count += 1
            
            # Procesar cada frame para mejor detección
            frame_start = time.time()
            
            # Redimensionar para procesamiento (mantener alta resolución para distancia)
            scale_factor = 0.5  # 50% para mejor detección a distancia
            small_frame = cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Detectar caras
            face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
            
            if len(face_locations) > 0:
                stats['faces_detected'] += len(face_locations)
                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations, num_jitters=1)
                
                # Escalar coordenadas de vuelta
                scale_back = int(1 / scale_factor)
                
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    top *= scale_back
                    right *= scale_back
                    bottom *= scale_back
                    left *= scale_back
                    
                    # Calcular tamaño de la cara
                    face_width = right - left
                    face_height = bottom - top
                    face_size = max(face_width, face_height)
                    stats['face_sizes'].append(face_size)
                    
                    # Reconocimiento si hay referencias
                    name = "Desconocido"
                    color = (0, 0, 255)  # Rojo
                    confidence = 0.0
                    
                    if len(reference_encodings) > 0:
                        face_distances = face_recognition.face_distance(reference_encodings, face_encoding)
                        best_match_index = np.argmin(face_distances)
                        best_distance = face_distances[best_match_index]
                        
                        # Tolerance más permisivo para distancias largas
                        tolerance = 0.65
                        matches = face_recognition.compare_faces(reference_encodings, face_encoding, tolerance=tolerance)
                        
                        if best_distance < tolerance or True in matches:
                            # Encontrar persona
                            current_index = 0
                            for person_name, person_data in reference_faces.items():
                                num_encodings = len(person_data['encodings'])
                                if best_match_index < current_index + num_encodings:
                                    name = person_name.split('_')[0] if '_' in person_name else person_name
                                    color = (0, 255, 0)  # Verde
                                    confidence = 1 - best_distance
                                    stats['known_faces'] += 1
                                    break
                                current_index += num_encodings
                        else:
                            stats['unknown_faces'] += 1
                    else:
                        stats['unknown_faces'] += 1
                    
                    # Dibujar en frame
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    label = f"{name} ({confidence:.2f})" if confidence > 0 else name
                    cv2.putText(frame, label, (left, top - 10), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Detectar personas con YOLO (si está disponible)
            try:
                from ultralytics import YOLO
                yolo_model = YOLO('yolov8n.pt')
                results = yolo_model(frame, conf=0.3, verbose=False)
                
                person_count = 0
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        if int(box.cls) == 0:  # class 0 = person
                            person_count += 1
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                            cv2.putText(frame, "Persona", (int(x1), int(y1) - 10),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                if person_count > 0:
                    stats['persons_detected'] += person_count
            except:
                pass
            
            detection_time = time.time() - frame_start
            stats['detection_times'].append(detection_time)
            
            # Mostrar estadísticas en frame
            elapsed = time.time() - start_time
            fps_actual = frame_count / elapsed if elapsed > 0 else 0
            
            info_text = [
                f"Frames: {stats['total_frames']}",
                f"FPS: {fps_actual:.1f}",
                f"Caras: {stats['faces_detected']}",
                f"Personas: {stats['persons_detected']}",
                f"Conocidas: {stats['known_faces']}",
                f"Desconocidas: {stats['unknown_faces']}",
                f"Tiempo: {elapsed:.1f}s"
            ]
            
            y_offset = 30
            for i, text in enumerate(info_text):
                cv2.putText(frame, text, (10, y_offset + i * 25),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(frame, text, (10, y_offset + i * 25),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            
            # Mostrar frame
            cv2.imshow('Test Deteccion', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # Mostrar progreso cada segundo
            if int(elapsed) != int(elapsed - detection_time):
                avg_time = np.mean(stats['detection_times'][-30:]) if stats['detection_times'] else 0
                avg_face_size = np.mean(stats['face_sizes'][-10:]) if stats['face_sizes'] else 0
                print(f"⏱️  {int(elapsed)}s | FPS: {fps_actual:.1f} | "
                      f"Caras: {stats['faces_detected']} | Personas: {stats['persons_detected']} | "
                      f"Tamaño promedio cara: {avg_face_size:.0f}px")
    
    except KeyboardInterrupt:
        print("\n⚠️ Test interrumpido por usuario")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
        
        # Mostrar resultados finales
        print("\n" + "=" * 60)
        print("📊 RESULTADOS DEL TEST")
        print("=" * 60)
        print(f"Total de frames procesados: {stats['total_frames']}")
        print(f"FPS promedio: {stats['total_frames'] / duration:.2f}")
        print(f"Caras detectadas: {stats['faces_detected']}")
        print(f"Personas detectadas: {stats['persons_detected']}")
        print(f"Caras conocidas: {stats['known_faces']}")
        print(f"Caras desconocidas: {stats['unknown_faces']}")
        if stats['detection_times']:
            print(f"Tiempo promedio por frame: {np.mean(stats['detection_times']):.3f}s")
        if stats['face_sizes']:
            print(f"Tamaño promedio de cara: {np.mean(stats['face_sizes']):.0f}px")
            print(f"Tamaño mínimo detectado: {np.min(stats['face_sizes']):.0f}px")
            print(f"Tamaño máximo detectado: {np.max(stats['face_sizes']):.0f}px")
        print("=" * 60)

if __name__ == '__main__':
    import sys
    camera_source = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    test_detection(camera_source, duration)


