#!/usr/bin/env python3
"""
Test de conexión RTSP
Verifica si la cámara Hikvision responde correctamente
"""

import cv2
import sys

# URL de la cámara RTSP
RTSP_URL = "rtsp://admin:IXGQBU@192.168.1.218:554/Streaming/Channels/0101"

print("🔄 Probando conexión a cámara RTSP...")
print(f"   URL: {RTSP_URL}")
print()

try:
    # Intentar conectar con diferentes backends
    cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
    
    if not cap.isOpened():
        print("❌ No se pudo abrir la cámara RTSP")
        print("   Posibles causas:")
        print("   - La cámara no está accesible en la red")
        print("   - Credenciales incorrectas")
        print("   - Puerto bloqueado por firewall")
        sys.exit(1)
    
    print("✅ Conexión establecida")
    print(f"   Backend: {cap.getBackendName()}")
    
    # Intentar leer un frame
    print("\n🎥 Intentando capturar frame...")
    ret, frame = cap.read()
    
    if ret:
        height, width = frame.shape[:2]
        print(f"✅ Frame capturado exitosamente")
        print(f"   Resolución: {width}x{height}")
        print(f"   FPS configurados: {cap.get(cv2.CAP_PROP_FPS)}")
    else:
        print("❌ No se pudo capturar frame")
        print("   La conexión se estableció pero no hay datos")
    
    cap.release()
    print("\n✅ Test completado - La cámara RTSP está funcionando")
    
except Exception as e:
    print(f"\n❌ Error durante el test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
