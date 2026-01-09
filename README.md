# 🚀 Sistema de Detección Intuitiva AI (Estilo TRON ARES)

Este repositorio contiene un sistema avanzado de videovigilancia e identificación biométrica que combina **Face Recognition (Dlib)** con **YOLOv8-seg (Segmentación de Instancias)**, envuelto en una interfaz HUD futurista inspirada en la película *TRON: ARES*.

---

## ✨ Características Principales

*   **🎬 Interfaz TRON ARES HUD**: Diseño visual de alta tecnología con efectos de resplandor (glow), tipografía técnica y colores Cyan/Ámbar.
*   **👤 Reconocimiento Facial Pro**: Identificación de personas en tiempo real con soporte para múltiples encodings por sujeto.
*   **📑 Biografías Dinámicas**: Muestra información específica (puesto, empresa, localización) al detectar personas registradas (ej: Diego, German).
*   **🔍 Segmentación de Objetos (YOLOv8)**: Detecta y segmenta más de 80 clases de objetos (personas, vehículos, mochilas, etc.) simultáneamente.
*   **📹 Soporte Multi-Cámara**: Sistema preparado para manejar múltiples fuentes RTSP (Cámaras Hikvision/Dahua) y cámaras locales por AVFoundation.
*   **🍎 Optimizado para macOS**: Configuraciones específicas para evitar bloqueos por bibliotecas OpenMP y gestión inteligente de memoria RAM.

---

## 🛠 Instalación (Desde Cero)

Para que el proyecto funcione en un equipo nuevo tras el clonado, sigue estos pasos:

### 1. Requisitos del Sistema
Debes tener instalado **Python 3.9+** y herramientas de compilación para la librería `dlib`:

```bash
# En macOS (con Homebrew)
brew install cmake pkg-config
```

### 2. Clonar y Configurar Entorno
```bash
git clone https://github.com/diegormarcon/face-detection.git
cd face-detection
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ⚙️ Configuración

### Caras de Referencia
Sube fotos de las personas que quieres reconocer a la carpeta:
`examples/reference_faces/`
*El nombre del archivo será el nombre que muestre el sistema (ej: `Diego_M.jpg`).*

### Cámaras
Puedes configurar tus cámaras en `examples/simple_face_recognition_app.py`, modificando la lista `PREDEFINED_CAMERAS`:
```python
PREDEFINED_CAMERAS = [
    {'id': 'hikvision_1', 'name': 'Main Cam', 'url': 'rtsp://user:pass@ip:554/stream', 'type': 'rtsp'},
    {'id': 'local_0', 'name': 'MacBook Cam', 'url': 0, 'type': 'local'}
]
```

---

## 🚀 Ejecución

Para iniciar el servidor principal:

```bash
cd examples
../.venv/bin/python simple_face_recognition_app.py
```

El sistema estará disponible en: **[http://localhost:5005](http://localhost:5005)**

---

## 🧠 Notas Técnicas

*   **Procesamiento**: El sistema utiliza **CPU** para YOLOv8 para garantizar estabilidad absoluta en macOS.
*   **Memoria**: Implementa `gc.collect()` automático cada 150 frames para evitar fugas de memoria en sesiones largas.
*   **Locks de Seguridad**: Utiliza `face_lock` y `yolo_lock` para manejar de forma segura la concurrencia de dlib y torch en hilos de Flask.
*   **Zoom-on-Person**: Si una persona está lejos, el sistema extrae automáticamente un recorte de alta resolución de la cabeza para intentar reconocerla.

---
**Desarrollado por Diego RM - Geo Software ltd**

known_image = face_recognition.load_image_file("biden.jpg")
unknown_image = face_recognition.load_image_file("unknown.jpg")

biden_encoding = face_recognition.face_encodings(known_image)[0]
unknown_encoding = face_recognition.face_encodings(unknown_image)[0]

results = face_recognition.compare_faces([biden_encoding], unknown_encoding)
```

## 🤖 Modelos Utilizados

Este proyecto utiliza varios modelos pre-entrenados de dlib que se descargan automáticamente a través del paquete `face_recognition_models`. Los modelos incluyen:

### 1. **Detector de Caras HOG (Histogram of Oriented Gradients)**
   - **Modelo**: `dlib.get_frontal_face_detector()`
   - **Uso**: Detección rápida de caras en imágenes
   - **Ventajas**: Rápido, funciona en CPU
   - **Desventajas**: Menos preciso que CNN

### 2. **Detector de Caras CNN (Convolutional Neural Network)**
   - **Modelo**: `mmod_human_face_detector.dat`
   - **Uso**: Detección precisa de caras usando deep learning
   - **Ventajas**: Muy preciso, funciona mejor con diferentes ángulos
   - **Desventajas**: Requiere GPU para mejor rendimiento

### 3. **Predictor de Puntos Faciales de 68 Puntos**
   - **Modelo**: `shape_predictor_68_face_landmarks.dat`
   - **Uso**: Detecta 68 puntos clave en el rostro (ojos, nariz, boca, contorno)
   - **Aplicaciones**: Análisis facial detallado, maquillaje digital, animación facial

### 4. **Predictor de Puntos Faciales de 5 Puntos**
   - **Modelo**: `shape_predictor_5_face_landmarks.dat`
   - **Uso**: Detecta 5 puntos clave (ojos, nariz)
   - **Ventajas**: Más rápido que el modelo de 68 puntos
   - **Aplicaciones**: Alineación facial rápida

### 5. **Modelo de Reconocimiento Facial ResNet**
   - **Modelo**: `dlib_face_recognition_resnet_model_v1.dat`
   - **Arquitectura**: ResNet-34 basado en deep learning
   - **Uso**: Genera encodings de 128 dimensiones para comparación de caras
   - **Precisión**: 99.38% en el benchmark LFW
   - **Aplicaciones**: Identificación y verificación de identidad

### Ubicación de los Modelos

Los modelos se instalan automáticamente con `face_recognition_models` y se encuentran en:
```
{site-packages}/face_recognition_models/models/
├── shape_predictor_68_face_landmarks.dat
├── shape_predictor_5_face_landmarks.dat
├── mmod_human_face_detector.dat
└── dlib_face_recognition_resnet_model_v1.dat
```

## 📁 Estructura del Proyecto

```
face_recognition-master/
│
├── face_recognition/              # Módulo principal
│   ├── __init__.py               # Exporta funciones principales
│   ├── api.py                    # API principal con lógica de reconocimiento
│   ├── face_detection_cli.py     # CLI para detección de caras
│   └── face_recognition_cli.py   # CLI para reconocimiento de caras
│
├── examples/                     # Ejemplos y aplicaciones
│   ├── find_faces_in_picture.py           # Detección básica de caras
│   ├── find_faces_in_picture_cnn.py      # Detección con CNN
│   ├── recognize_faces_in_pictures.py    # Reconocimiento facial
│   ├── find_facial_features_in_picture.py # Características faciales
│   ├── facerec_from_webcam.py            # Reconocimiento en tiempo real
│   ├── simple_face_recognition_app.py    # Aplicación web Flask
│   ├── face_recognition_knn.py           # Clasificación KNN
│   ├── face_recognition_svm.py           # Clasificación SVM
│   ├── reference_faces/                  # Caras de referencia
│   ├── knn_examples/                     # Ejemplos KNN
│   │   ├── train/                        # Imágenes de entrenamiento
│   │   └── test/                         # Imágenes de prueba
│   └── static/                           # Archivos estáticos web
│       ├── css/
│       └── js/
│
├── tests/                        # Tests unitarios
│   ├── test_face_recognition.py
│   └── test_images/
│
├── docs/                         # Documentación
│   ├── conf.py
│   ├── usage.rst
│   └── ...
│
├── docker/                       # Configuración Docker
│   ├── cpu/
│   ├── gpu/
│   └── README.md
│
├── requirements.txt              # Dependencias principales
├── requirements_dev.txt         # Dependencias de desarrollo
├── setup.py                      # Configuración del paquete
├── Dockerfile                    # Dockerfile principal
└── docker-compose.yml            # Configuración Docker Compose
```

### Componentes Principales

#### `face_recognition/api.py`
- Contiene toda la lógica de reconocimiento facial
- Carga y utiliza los modelos de dlib
- Funciones principales:
  - `load_image_file()`: Carga imágenes
  - `face_locations()`: Detecta ubicaciones de caras
  - `face_landmarks()`: Detecta características faciales
  - `face_encodings()`: Genera encodings para comparación
  - `compare_faces()`: Compara caras
  - `face_distance()`: Calcula distancia entre caras

#### `face_recognition/face_recognition_cli.py`
- Herramienta de línea de comandos para reconocimiento
- Uso: `face_recognition [carpeta_conocidos] [carpeta_desconocidos]`

#### `face_recognition/face_detection_cli.py`
- Herramienta de línea de comandos para detección
- Uso: `face_detection [carpeta_imagenes]`

## 🚀 Instalación

### Requisitos

- Python 3.3+ (Python 2.7 también soportado pero no recomendado)
- macOS o Linux (Windows no oficialmente soportado, pero puede funcionar)
- cmake (para compilar dlib desde fuente)

### Instalación en macOS

#### Opción 1: Instalación con dlib-bin (Recomendado)

```bash
# Instalar dependencias básicas
pip3 install --user numpy Pillow scipy Click

# Instalar dlib-bin (versión precompilada, evita problemas de compilación)
pip3 install --user dlib-bin

# Instalar face_recognition_models
pip3 install --user face_recognition_models

# Instalar el proyecto
cd face_recognition-master
python3 setup.py install --user
```

#### Opción 2: Instalación con Homebrew

```bash
# Instalar cmake
brew install cmake

# Instalar dlib desde fuente
pip3 install dlib

# Instalar face_recognition
pip3 install face_recognition
```

### Instalación en Linux (Ubuntu/Debian)

```bash
# Instalar dependencias del sistema
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    python3-dev

# Instalar dependencias Python
pip3 install numpy Pillow scipy Click

# Instalar dlib
pip3 install dlib

# Instalar face_recognition
pip3 install face_recognition
```

### Instalación usando Docker

```bash
# Construir y ejecutar con Docker Compose
docker-compose up --build

# O construir manualmente
docker build -t face_recognition .
docker run -v $(pwd)/examples:/face_recognition/examples face_recognition
```

### Verificación de Instalación

```python
import face_recognition
import dlib

print(f"face_recognition version: {face_recognition.__version__}")
print(f"dlib version: {dlib.__version__}")
```

## 💻 Uso

### Uso Básico en Python

```python
import face_recognition

# Cargar imagen
image = face_recognition.load_image_file("person.jpg")

# Detectar caras
face_locations = face_recognition.face_locations(image)
print(f"Encontré {len(face_locations)} cara(s)")

# Detectar características faciales
face_landmarks = face_recognition.face_landmarks(image)

# Generar encoding para reconocimiento
face_encodings = face_recognition.face_encodings(image)
```

### Uso desde Línea de Comandos

#### Detectar caras

```bash
face_detection ./folder_with_pictures/
```

Salida:
```
examples/image1.jpg,65,215,169,112
examples/image2.jpg,62,394,211,244
```

#### Reconocer caras

```bash
face_recognition ./pictures_of_people_i_know/ ./unknown_pictures/
```

Salida:
```
/unknown_pictures/unknown.jpg,Barack Obama
/unknown_pictures/unknown2.jpg,unknown_person
```

### Aplicación Web

El proyecto incluye una aplicación web Flask completa:

```bash
cd examples
python3 simple_face_recognition_app.py
```

Luego abre tu navegador en: `http://localhost:5005`

## 📚 Ejemplos

El proyecto incluye más de 20 ejemplos en la carpeta `examples/`:

### Detección de Caras
- `find_faces_in_picture.py` - Detección básica con HOG
- `find_faces_in_picture_cnn.py` - Detección con CNN (más precisa)
- `find_faces_in_batches.py` - Procesamiento por lotes

### Reconocimiento Facial
- `recognize_faces_in_pictures.py` - Reconocimiento básico
- `identify_and_draw_boxes_on_faces.py` - Dibuja cajas alrededor de caras reconocidas
- `face_distance.py` - Calcula distancia entre caras

### Características Faciales
- `find_facial_features_in_picture.py` - Detecta puntos faciales
- `digital_makeup.py` - Aplica maquillaje digital
- `blink_detection.py` - Detecta parpadeos

### Tiempo Real
- `facerec_from_webcam.py` - Reconocimiento desde webcam
- `facerec_from_webcam_faster.py` - Versión optimizada
- `facerec_from_webcam_multiprocessing.py` - Versión multiproceso
- `blur_faces_on_webcam.py` - Desenfoque de caras en tiempo real

### Videos
- `facerec_from_video_file.py` - Procesamiento de archivos de video

### Clasificación Avanzada
- `face_recognition_knn.py` - Clasificación K-Nearest Neighbors
- `face_recognition_svm.py` - Clasificación Support Vector Machine

### Aplicaciones Web
- `simple_face_recognition_app.py` - Aplicación web completa con Flask

### Ejecutar un Ejemplo

```bash
cd examples
python3 find_faces_in_picture.py
python3 recognize_faces_in_pictures.py
python3 simple_face_recognition_app.py
```

## 📦 Dependencias

### Dependencias Principales

| Paquete | Versión Mínima | Descripción |
|---------|---------------|-------------|
| `face_recognition_models` | >=0.3.0 | Modelos pre-entrenados |
| `dlib` | >=19.7 | Biblioteca de machine learning |
| `numpy` | - | Computación numérica |
| `Pillow` | - | Procesamiento de imágenes |
| `scipy` | >=0.17.0 | Computación científica |
| `Click` | >=6.0 | Interfaz de línea de comandos |

### Dependencias Opcionales

| Paquete | Uso |
|---------|-----|
| `opencv-python` | Para ejemplos de webcam y video |
| `flask` | Para aplicación web |
| `scikit-learn` | Para clasificación KNN/SVM |

### Verificar Dependencias Instaladas

```bash
pip3 list | grep -E "(face|dlib|numpy|Pillow|scipy|Click|opencv|flask)"
```

## 🎯 Casos de Uso

- **Seguridad**: Control de acceso mediante reconocimiento facial
- **Organización de Fotos**: Clasificación automática de fotos por persona
- **Asistencia**: Identificación de personas en eventos
- **Investigación**: Análisis de expresiones faciales
- **Entretenimiento**: Filtros y efectos faciales

## 🔧 Solución de Problemas

### Error: "No module named 'dlib'"

**Solución**: Instala dlib usando `dlib-bin` (precompilado):
```bash
pip3 install --user dlib-bin
```

### Error: "CMake must be installed to build dlib"

**Solución**: Instala cmake:
```bash
# macOS
brew install cmake

# Linux
sudo apt-get install cmake

# O usando pip (menos recomendado)
pip3 install cmake
```

### Error: "No module named 'face_recognition'"

**Solución**: Instala el proyecto:
```bash
cd face_recognition-master
python3 setup.py install --user
```

## 📖 Documentación Adicional

- [Documentación oficial](http://face-recognition.readthedocs.io/)
- [Ejemplos completos](https://github.com/ageitgey/face_recognition/tree/master/examples)
- [Guía de instalación de dlib](https://gist.github.com/ageitgey/629d75c1baac34dfa5ca2a1928a7aeaf)

## 📄 Licencia

MIT License - Ver archivo [LICENSE](LICENSE) para más detalles.

## 🙏 Agradecimientos

- [Davis King](https://github.com/davisking) por crear dlib y los modelos entrenados
- Todos los contribuidores de la comunidad open source

## 🔗 Enlaces Útiles

- [Repositorio GitHub](https://github.com/ageitgey/face_recognition)
- [PyPI Package](https://pypi.python.org/pypi/face_recognition)
- [Documentación](http://face-recognition.readthedocs.io/)

---

**Versión del Proyecto**: 1.4.0  
**Última Actualización**: 2024
