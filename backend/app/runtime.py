"""Explicit device selection with no silent fallback when CUDA is requested."""
from functools import lru_cache
import os


@lru_cache(maxsize=1)
def runtime_status():
    import torch
    import onnxruntime as ort
    return {'cuda_available': torch.cuda.is_available(), 'torch_cuda': torch.version.cuda,
            'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            'onnx_providers': ort.get_available_providers()}


def select_device(requested='cuda', pose='yolo-small'):
    import torch
    import onnxruntime as ort
    if requested not in ('cuda', 'cpu', 'auto'):
        raise ValueError('Choose CUDA, CPU, or auto mode.')
    if requested == 'auto':
        requested = 'cuda' if torch.cuda.is_available() else 'cpu'
    if requested == 'cpu':
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        return 'cpu'
    if not torch.cuda.is_available():
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        return 'cpu'
    # Rescue crops vary in shape. Avoid expensive convolution autotuning for
    # each new view before the first useful player result can be returned.
    torch.backends.cudnn.benchmark = False
    if pose in ('rtmpose', 'rtmo'):
        if hasattr(ort, 'preload_dlls'):
            ort.preload_dlls()
        if 'CUDAExecutionProvider' not in ort.get_available_providers():
            raise RuntimeError('The ONNX pose backend has no CUDAExecutionProvider. Install onnxruntime-gpu or explicitly select CPU mode.')
    return 0
