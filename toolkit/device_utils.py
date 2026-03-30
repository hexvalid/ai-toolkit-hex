import contextlib
import gc
import warnings
from typing import Optional, Union

import torch


def is_mps_available() -> bool:
    try:
        return hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except AttributeError:
        return False


def is_cuda_available() -> bool:
    return torch.cuda.is_available()


def normalize_device_string(device_str: str) -> str:
    normalized = device_str.lower().strip()

    if normalized == "gpu":
        if is_cuda_available():
            return "cuda"
        if is_mps_available():
            return "mps"
        return "cpu"

    if normalized in {"cuda", "cuda:0"}:
        return "cuda" if is_cuda_available() else "cpu"

    if normalized.startswith("cuda:"):
        return normalized if is_cuda_available() else "cpu"

    if normalized in {"mps", "metal", "apple", "apple_silicon", "silicon"}:
        return "mps" if is_mps_available() else "cpu"

    if normalized == "cpu":
        return "cpu"

    return normalized


def get_optimal_device(device: Optional[Union[str, torch.device]] = None) -> torch.device:
    if device is not None:
        if isinstance(device, str):
            device = torch.device(normalize_device_string(device))

        if device.type == "cuda" and not is_cuda_available():
            warnings.warn("CUDA requested but not available. Falling back to CPU.", UserWarning)
            return torch.device("cpu")

        if device.type == "mps" and not is_mps_available():
            warnings.warn("MPS requested but not available. Falling back to CPU.", UserWarning)
            return torch.device("cpu")

        return device

    if is_cuda_available():
        return torch.device("cuda")
    if is_mps_available():
        return torch.device("mps")
    return torch.device("cpu")


def _as_torch_device(device: Optional[Union[str, torch.device]] = None) -> torch.device:
    return get_optimal_device(device)


def get_device() -> torch.device:
    return get_optimal_device()


def empty_cache(device: Optional[Union[str, torch.device]] = None):
    """
    Empties the cache for the selected device.
    """
    target_device = _as_torch_device(device)
    gc.collect()

    if target_device.type == "cuda" and is_cuda_available():
        torch.cuda.empty_cache()
    elif target_device.type == "mps" and is_mps_available() and hasattr(torch.mps, "empty_cache"):
        torch.mps.empty_cache()


def clear_cache():
    empty_cache()


def manual_seed(seed: int, device: Optional[Union[str, torch.device]] = None):
    """
    Sets global seed and device-specific seed when supported.
    """
    target_device = _as_torch_device(device)

    torch.manual_seed(seed)
    if target_device.type == "cuda" and is_cuda_available():
        torch.cuda.manual_seed(seed)
    elif target_device.type == "mps" and is_mps_available() and hasattr(torch.mps, "manual_seed"):
        torch.mps.manual_seed(seed)


def get_device_name(device: Optional[Union[str, torch.device]] = None) -> str:
    return _as_torch_device(device).type


def get_dataloader_kwargs(device: Optional[Union[str, torch.device]] = None) -> dict:
    target_device = _as_torch_device(device)

    if target_device.type == "mps":
        return {
            "num_workers": 0,
            "persistent_workers": False,
            "pin_memory": False,
        }

    if target_device.type == "cuda":
        return {
            "num_workers": 4,
            "prefetch_factor": 2,
            "persistent_workers": True,
            "pin_memory": True,
        }

    return {
        "num_workers": 2,
        "prefetch_factor": 2,
        "persistent_workers": True,
    }


def autocast(device: Optional[Union[str, torch.device]] = None):
    target_device = _as_torch_device(device)

    if target_device.type in {"cuda", "mps", "cpu"}:
        return torch.autocast(device_type=target_device.type)

    return contextlib.nullcontext()
