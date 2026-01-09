#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import traceback

print("=" * 60)
print("DIAGNÓSTICO DEL SERVIDOR")
print("=" * 60)

# Test 1: Importaciones básicas
print("\n[1] Verificando importaciones básicas...")
try:
    import flask
    print("✅ Flask importado correctamente")
except Exception as e:
    print(f"❌ Error importando Flask: {e}")
    sys.exit(1)

# Test 2: Importar el módulo principal
print("\n[2] Importando módulo principal...")
try:
    import simple_face_recognition_app
    print("✅ Módulo principal importado correctamente")
except Exception as e:
    print(f"❌ Error importando módulo principal: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 3: Verificar app Flask
print("\n[3] Verificando aplicación Flask...")
try:
    app = simple_face_recognition_app.app
    print(f"✅ Aplicación Flask creada: {app}")
    print(f"   Rutas registradas: {len(app.url_map._rules)}")
except Exception as e:
    print(f"❌ Error con aplicación Flask: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 4: Verificar archivos necesarios
print("\n[4] Verificando archivos necesarios...")
import os
files_to_check = [
    'templates/beautiful.html',
    'static/css/beautiful.css',
    'static/js/beautiful.js',
    'static/js/detections.js'
]

for file in files_to_check:
    if os.path.exists(file):
        print(f"✅ {file} existe")
    else:
        print(f"⚠️ {file} NO existe")

# Test 5: Intentar iniciar servidor
print("\n[5] Intentando iniciar servidor...")
print("   (Esto debería mostrar el mensaje de Flask)")
try:
    # Solo importar, no ejecutar
    print("✅ Módulo cargado correctamente")
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO COMPLETADO")
    print("=" * 60)
    print("\nPara iniciar el servidor, ejecuta:")
    print("   python3 simple_face_recognition_app.py")
    print("\nO desde el directorio examples:")
    print("   cd examples && python3 simple_face_recognition_app.py")
except Exception as e:
    print(f"❌ Error: {e}")
    traceback.print_exc()
    sys.exit(1)



