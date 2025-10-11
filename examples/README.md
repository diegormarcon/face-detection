# Sistema de Reconocimiento Facial

## 🚀 Aplicación con Interfaz Beautiful

Este es un sistema de reconocimiento facial completamente funcional con una interfaz moderna, elegante y fácil de usar.

## ✨ Características

- **🎥 Video en Tiempo Real**: Detección facial instantánea con la cámara
- **📁 Gestión de Referencias**: Subida y eliminación de caras conocidas
- **🎨 Interfaz Beautiful**: Diseño elegante, moderno y responsive
- **⚡ Rendimiento Optimizado**: Código eficiente y estable

## 🛠️ Instalación

### 1. Instalar Dependencias

```bash
pip install face_recognition opencv-python flask pillow numpy
```

### 2. Ejecutar la Aplicación

```bash
cd examples
python3 simple_face_recognition_app.py
```

**Nota**: La aplicación ahora usa la interfaz "beautiful" por defecto.

### 3. Acceder a la Aplicación

Abre tu navegador y ve a: `http://127.0.0.1:5005`

## 📱 Cómo Usar

### 🎥 Video en Tiempo Real

1. Haz clic en **"Iniciar Video"**
2. Permite el acceso a la cámara cuando se solicite
3. Verás la detección facial en tiempo real:
   - **Verde**: Cara conocida (con nombre y confianza)
   - **Rojo**: Cara desconocida
   - **Azul**: Cara detectada sin referencia

### 👤 Gestión de Referencias

#### Agregar una Nueva Referencia:

1. **Arrastra una imagen** al área de carga
2. **O haz clic** para seleccionar un archivo
3. **Ingresa el nombre** de la persona
4. **Haz clic en "Guardar Referencia"**

#### Eliminar una Referencia:

1. Haz clic en **"Eliminar"** en la tarjeta de la referencia
2. Confirma la eliminación

## 📋 Requisitos de Imágenes

- **Formato**: JPG, PNG, JPEG, GIF, BMP
- **Contenido**: Debe contener **una sola cara** visible
- **Calidad**: Cara bien iluminada y clara
- **Tamaño**: Recomendado mínimo 200x200 píxeles

## 🔧 Solución de Problemas

### ❌ "No se detectaron caras en la imagen"

**Causas posibles:**
- La imagen no contiene una cara visible
- La cara está muy oscura o mal iluminada
- La imagen tiene múltiples caras
- La imagen es muy pequeña o borrosa

**Soluciones:**
- Usa una imagen con una sola cara bien visible
- Asegúrate de que la cara esté bien iluminada
- Usa una imagen de buena calidad
- Recorta la imagen para mostrar solo la cara

### ❌ "Error de conexión"

**Soluciones:**
- Verifica que el servidor esté ejecutándose
- Asegúrate de que el puerto 5005 esté disponible
- Reinicia la aplicación si es necesario

### ❌ La cámara no funciona

**Soluciones:**
- Permite el acceso a la cámara en el navegador
- Verifica que no haya otras aplicaciones usando la cámara
- Reinicia el navegador si es necesario

## 📁 Estructura de Archivos

```
examples/
├── simple_face_recognition_app.py    # Aplicación principal
├── templates/
│   └── beautiful.html                # Interfaz web elegante
├── static/
│   ├── css/
│   │   └── beautiful.css             # Estilos de la interfaz
│   └── js/
│       └── beautiful.js              # JavaScript de la interfaz
├── reference_faces/                  # Caras de referencia guardadas
├── uploads/                          # Imágenes temporales
└── README.md                         # Este archivo
```

## 🎯 Funcionalidades Técnicas

- **Detección Facial**: Usa la librería `face_recognition`
- **Modelos**: CNN (por defecto) y HOG (fallback)
- **Base de Datos**: Almacenamiento local de referencias
- **API RESTful**: Endpoints bien definidos
- **Validación**: Verificación de archivos y caras

## 🚀 Características de la Interfaz Beautiful

- ✅ **Diseño elegante y moderno** con animaciones suaves
- ✅ **Interfaz intuitiva** con pestañas organizadas
- ✅ **Manejo de errores robusto** con mensajes claros
- ✅ **API más confiable** y bien estructurada
- ✅ **Detección facial mejorada** con fallback HOG
- ✅ **Validación de archivos mejorada**
- ✅ **Experiencia de usuario optimizada**

## 📞 Soporte

Si tienes problemas:

1. **Verifica los requisitos** de las imágenes
2. **Revisa la consola** del navegador para errores
3. **Reinicia la aplicación** si es necesario
4. **Asegúrate** de que todas las dependencias estén instaladas

¡Disfruta usando el sistema de reconocimiento facial! 🎉
