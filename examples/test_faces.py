import face_recognition
import os

REFERENCE_FOLDER = "/Users/diego/Desktop/face_recognition-master/examples/reference_faces"
files = os.listdir(REFERENCE_FOLDER)
print(f"Testing {len(files)} files...")

for filename in files:
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        filepath = os.path.join(REFERENCE_FOLDER, filename)
        print(f"Testing {filename}...")
        try:
            image = face_recognition.load_image_file(filepath)
            face_locations = face_recognition.face_locations(image, model="hog")
            print(f"  Found {len(face_locations)} faces")
        except Exception as e:
            print(f"  Error: {e}")

print("Done!")
