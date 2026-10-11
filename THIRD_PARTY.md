# Reference models and dependencies

This project was developed using interface and algorithm observations from:

- Good-Tennis: https://github.com/yo-WASSUP/Good-Tennis — project README identifies Apache License 2.0 for code; model assets retain their upstream licenses.
- Good-Badminton: https://github.com/yo-WASSUP/Good-Badminton — project README identifies Apache License 2.0 for code and shuttle weights; ONNX assets retain OpenMMLab attribution.
- RTMPose, RTMO and YOLOX: OpenMMLab model ecosystem. Preserve upstream notices when distributing model assets.
- Ultralytics: consult the license terms for the installed library and YOLO model artifacts before distributing this prototype commercially.
- RTMLib, OpenCV, PyTorch, ONNX Runtime, React, FastAPI, Celery and other packages retain their own licenses.

No reference project code or UI was copied into the implementation. Downloaded binary model assets are unchanged and are listed with source URLs and checksums in `weights/manifest.json`.
