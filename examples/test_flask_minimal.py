#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("=" * 60)
print("TEST MINIMAL DE FLASK")
print("=" * 60)

from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "Servidor Flask funcionando!"

print("\n✅ Flask app creada")
print("✅ Ruta '/' registrada")
print("\nIniciando servidor en puerto 5005...")
print("=" * 60)
print("")

try:
    app.run(debug=True, host='0.0.0.0', port=5005, threaded=True)
except KeyboardInterrupt:
    print("\nServidor detenido")



