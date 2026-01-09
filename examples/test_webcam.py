#!/usr/bin/env python3
"""
Test simple de webcam local
"""

import cv2
import sys

print("🎥 Probando webcam local (índice 0)...")
print()

try:
    # Intentar con AVFoundation primero (macOS)
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    
    if not cap.isOpened():
        print("⚠️ AVFoundation falló, intentando backend por defecto...")
        cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ No se pudo abrir la webcam")
        print("   Posibles causas:")
        print("   - La webcam está siendo usada por otra app")
        print("   - No hay permisos de cámara")
        print("   - La cámara no está disponible")
        sys.exit(1)
    
    print(f"✅ Webcam abierta exitosamente")
    print(f"   Backend: {cap.getBackendName()}")
    print(f"   Resolución: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"   FPS: {cap.get(cv2.CAP_PROP_FPS)}")
    print()
    
    # Capturar algunos frames de prueba
    print("📸 Capturando 5 frames de prueba...")
    for i in range(5):
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"   Frame {i+1}: {w}x{h} pixels ✅")
        else:
            print(f"   Frame {i+1}: Error leyendo ❌")
            break
    
    cap.release()
    print()
    print("✅ Test completado - La webcam funciona correctamente")
    
except Exception as e:
    print(f"❌ Error durante el test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
