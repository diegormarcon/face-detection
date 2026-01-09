#!/bin/bash
cd "$(dirname "$0")"
echo "Iniciando servidor Flask..."
echo "Directorio: $(pwd)"
echo "Python: $(which python3)"
echo ""
python3 simple_face_recognition_app.py



