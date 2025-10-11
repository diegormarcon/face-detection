#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import face_recognition
import cv2
import numpy as np
import base64
import io
import os
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from PIL import Image
import json
import threading
import time

# Importar soporte para HEIF
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
    print("Soporte HEIF habilitado")
except ImportError:
    HEIF_SUPPORT = False
    print("Soporte HEIF no disponible")

app = Flask(__name__)

# Configuración
UPLOAD_FOLDER = 'uploads'
REFERENCE_FOLDER = 'reference_faces'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Crear directorios si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REFERENCE_FOLDER, exist_ok=True)

# Variables globales para la cámara
camera = None
camera_lock = threading.Lock()
is_streaming = False

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

def init_camera():
    global camera
    try:
        # Liberar cámara anterior si existe
        if camera is not None:
            try:
                camera.release()
            except:
                pass
            camera = None

        # Intentar diferentes índices de cámara
        for camera_index in [0, 1, 2]:
            try:
                print(f"Intentando abrir cámara en índice {camera_index}")
                camera = cv2.VideoCapture(camera_index)

                if camera.isOpened():
                    # Configurar propiedades de la cámara
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    camera.set(cv2.CAP_PROP_FPS, 30)
                    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                    # Probar lectura de frame
                    ret, test_frame = camera.read()
                    if ret and test_frame is not None:
                        print(f"Cámara inicializada correctamente en índice {camera_index}")
                        return True
                    else:
                        print(f"No se pudo leer de la cámara en índice {camera_index}")
                        camera.release()
                        camera = None
                else:
                    print(f"No se pudo abrir cámara en índice {camera_index}")
                    if camera is not None:
                        camera.release()
                        camera = None
            except Exception as e:
                print(f"Error con cámara en índice {camera_index}: {e}")
                if camera is not None:
                    try:
                        camera.release()
                    except:
                        pass
                    camera = None

        print("No se pudo inicializar ninguna cámara")
        return False

    except Exception as e:
        print(f"Error general inicializando cámara: {e}")
        if camera is not None:
            try:
                camera.release()
            except:
                pass
            camera = None
        return False

def load_reference_faces():
    """Cargar caras de referencia desde archivos"""
    global reference_faces, reference_encodings
    reference_faces = {}
    reference_encodings = []

    if not os.path.exists(REFERENCE_FOLDER):
        return

    for filename in os.listdir(REFERENCE_FOLDER):
        if allowed_file(filename):
            filepath = os.path.join(REFERENCE_FOLDER, filename)
            try:
                image = face_recognition.load_image_file(filepath)
                face_locations = face_recognition.face_locations(image)
                face_encodings = face_recognition.face_encodings(image, face_locations)

                if len(face_encodings) > 0:
                    name = os.path.splitext(filename)[0]
                    reference_faces[name] = {
                        'encoding': face_encodings[0],
                        'image_path': filepath,
                        'face_location': face_locations[0]
                    }
                    reference_encodings.append(face_encodings[0])
                    print(f"Cara de referencia cargada: {name}")
            except Exception as e:
                print(f"Error cargando {filename}: {e}")

def generate_frames():
    global camera, is_streaming, reference_encodings, reference_faces

    while is_streaming:
        try:
            with camera_lock:
                # Verificar si la cámara está disponible
                if camera is None or not camera.isOpened():
                    print("Cámara no disponible, intentando reinicializar...")
                    if not init_camera():
                        print("No se pudo reinicializar la cámara, esperando...")
                        time.sleep(2)
                        continue

                # Leer frame de la cámara
                success, frame = camera.read()
                if not success or frame is None:
                    print("Error leyendo frame de la cámara, reintentando...")
                    time.sleep(0.5)
                    continue
        except Exception as e:
            print(f"Error en generate_frames: {e}")
            time.sleep(0.1)
            continue

        # Redimensionar frame para mejor rendimiento
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Detectar caras
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        # Dibujar rectángulos y etiquetas
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            if len(reference_encodings) > 0:
                matches = face_recognition.compare_faces(reference_encodings, face_encoding, tolerance=0.6)
                face_distances = face_recognition.face_distance(reference_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)

                if matches[best_match_index]:
                    name = list(reference_faces.keys())[best_match_index]
                    confidence = 1 - face_distances[best_match_index]
                    color = (0, 255, 0)
                    label = f"{name} ({confidence:.2f})"
                else:
                    color = (0, 0, 255)
                    label = "Desconocido"
            else:
                color = (255, 0, 0)
                label = "Cara Detectada"

            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            cv2.putText(frame, label, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

        info_text = f"Caras detectadas: {len(face_locations)} | Referencias: {len(reference_faces)}"
        cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('beautiful.html')

@app.route('/test_app.html')
def test_app():
    return send_from_directory('.', 'test_app.html')

@app.route('/video_feed')
def video_feed():
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

        # Detectar caras
        face_locations = face_recognition.face_locations(image)

        if len(face_locations) == 0:
            # Intentar con modelo HOG que es más permisivo
            face_locations = face_recognition.face_locations(image, model="hog")

            if len(face_locations) == 0:
                return jsonify({'success': False, 'error': 'No se detectaron caras en la imagen. Asegúrate de que la imagen contenga una cara visible y bien iluminada.'}), 400

        face_encodings = face_recognition.face_encodings(image, face_locations)

        if len(face_encodings) > 1:
            return jsonify({'success': False, 'error': 'Se detectaron múltiples caras. Usa una imagen con una sola cara'}), 400

        # Guardar imagen de referencia
        filename = f"{name}_{int(time.time())}.jpg"
        filepath = os.path.join(REFERENCE_FOLDER, filename)

        pil_image = Image.fromarray(image)
        pil_image.save(filepath, 'JPEG')

        # Guardar datos de la cara
        reference_faces[name] = {
            'encoding': face_encodings[0],
            'image_path': filepath,
            'face_location': face_locations[0]
        }
        reference_encodings.append(face_encodings[0])

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
    return jsonify({
        'success': True,
        'faces': list(reference_faces.keys()),
        'count': len(reference_faces)
    })

@app.route('/api/delete_reference/<name>', methods=['DELETE'])
def delete_reference(name):
    global reference_faces, reference_encodings
    try:
        if name in reference_faces:
            if os.path.exists(reference_faces[name]['image_path']):
                os.remove(reference_faces[name]['image_path'])

            del reference_faces[name]
            reference_encodings = [face['encoding'] for face in reference_faces.values()]

            return jsonify({'success': True, 'message': f'Cara "{name}" eliminada'})
        else:
            return jsonify({'success': False, 'error': 'Cara no encontrada'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    load_reference_faces()

    try:
        app.run(debug=True, host='0.0.0.0', port=5005, threaded=True)
    except KeyboardInterrupt:
        print("\nCerrando aplicación...")
    finally:
        if camera is not None:
            camera.release()
            print("Cámara liberada al cerrar")
