$ErrorActionPreference = 'Stop'
$racketRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $racketRoot
$racketPython = Join-Path $racketRoot '.venv/Scripts/python.exe'
& $racketPython -m pip install 'torch==2.11.0' 'torchvision==0.26.0' --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed.' }
& $racketPython -m pip uninstall -y onnxruntime onnxruntime-gpu
& $racketPython -m pip install 'onnxruntime-gpu==1.23.2' 'lap>=0.5.12'
if ($LASTEXITCODE -ne 0) { throw 'ONNX Runtime GPU installation failed.' }
& $racketPython -c "import torch,onnxruntime as ort; ort.preload_dlls(); print(torch.cuda.get_device_name(0)); print(ort.get_available_providers()); assert torch.cuda.is_available(); assert 'CUDAExecutionProvider' in ort.get_available_providers()"
