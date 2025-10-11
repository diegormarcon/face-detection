# 🔧 Guía de Solución de Problemas

## ❌ Problema: No veo el stream de video

### Posibles Causas y Soluciones:

#### 1. **Permisos de Cámara**
- **Problema**: El navegador no tiene permisos para acceder a la cámara
- **Solución**:
  - Haz clic en el ícono de cámara en la barra de direcciones
  - Selecciona "Permitir" para el acceso a la cámara
  - Recarga la página

#### 2. **Cámara en Uso**
- **Problema**: Otra aplicación está usando la cámara
- **Solución**:
  - Cierra otras aplicaciones que puedan usar la cámara (Zoom, Teams, etc.)
  - Reinicia el navegador
  - Reinicia la aplicación

#### 3. **Problema de Conexión**
- **Problema**: Error de conexión con el servidor
- **Solución**:
  - Verifica que el servidor esté corriendo en el puerto 5005
  - Prueba acceder a: `http://127.0.0.1:5005/test_app.html`
  - Reinicia el servidor si es necesario

#### 4. **Navegador No Compatible**
- **Problema**: El navegador no soporta video streaming
- **Solución**:
  - Usa Chrome, Firefox, Safari o Edge actualizado
  - Habilita JavaScript en el navegador

---

## ❌ Problema: No puedo guardar las imágenes

### Posibles Causas y Soluciones:

#### 1. **Imagen Sin Cara Detectada**
- **Problema**: La imagen no contiene una cara visible
- **Solución**:
  - Usa una imagen con una cara clara y bien iluminada
  - Asegúrate de que la cara esté completa en la imagen
  - Evita imágenes muy oscuras o borrosas

#### 2. **Múltiples Caras en la Imagen**
- **Problema**: La imagen contiene más de una cara
- **Solución**:
  - Recorta la imagen para mostrar solo una cara
  - Usa una imagen con una sola persona

#### 3. **Formato de Archivo No Soportado**
- **Problema**: El archivo no es una imagen válida
- **Solución**:
  - Usa formatos: JPG, PNG, JPEG, GIF, BMP
  - Verifica que el archivo no esté corrupto

#### 4. **Error de Conexión**
- **Problema**: Error al enviar la imagen al servidor
- **Solución**:
  - Verifica tu conexión a internet
  - Reinicia la aplicación
  - Prueba con una imagen más pequeña

---

## 🧪 Página de Pruebas

Para diagnosticar problemas, usa la página de pruebas:

**URL**: `http://127.0.0.1:5005`

Esta página te permite probar:
- ✅ Conexión con el servidor
- ✅ Video stream
- ✅ Subida de imágenes
- ✅ Carga de referencias

---

## 🔍 Verificación Paso a Paso

### 1. **Verificar Servidor**
```bash
curl -I http://127.0.0.1:5005
```
Debería devolver: `HTTP/1.1 200 OK`

### 2. **Verificar Video Stream**
```bash
curl -I http://127.0.0.1:5005/video_feed
```
Debería devolver: `Content-Type: multipart/x-mixed-replace; boundary=frame`

### 3. **Verificar API de Referencias**
```bash
curl http://127.0.0.1:5005/api/reference_faces
```
Debería devolver un JSON con las referencias

---

## 🚀 Soluciones Rápidas

### **Reiniciar Todo**
1. Detén el servidor (Ctrl+C)
2. Reinicia: `python3 simple_face_recognition_app.py`
3. Abre: `http://127.0.0.1:5005`

### **Limpiar Cache del Navegador**
1. Presiona Ctrl+Shift+R (o Cmd+Shift+R en Mac)
2. O abre una ventana de incógnito

### **Verificar Dependencias**
```bash
pip install face_recognition opencv-python flask pillow numpy
```

---

## 📞 Información de Debug

Si el problema persiste, verifica:

1. **Logs del Servidor**: Revisa la consola donde corre el servidor
2. **Consola del Navegador**: Presiona F12 y revisa la pestaña "Console"
3. **Página de Pruebas**: Usa `/test_app.html` para diagnosticar

---

## ✅ Estado Normal

Cuando todo funciona correctamente deberías ver:

- **Video Stream**: Imagen en tiempo real de la cámara
- **Detección**: Rectángulos verdes/rojos alrededor de las caras
- **Subida**: Mensaje "Cara de referencia guardada correctamente"
- **Referencias**: Lista de caras conocidas en la interfaz

---

## 🎯 Consejos Adicionales

- **Iluminación**: Usa buena iluminación para mejor detección
- **Posición**: Mantén la cara centrada y a una distancia adecuada
- **Calidad**: Usa imágenes de al menos 200x200 píxeles
- **Navegador**: Chrome suele funcionar mejor para video streaming
