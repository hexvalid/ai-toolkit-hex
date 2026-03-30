import gc
import torch
from toolkit.basic import flush
from typing import Optional
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from toolkit.models.base_model import BaseModel


class FakeTextEncoder(torch.nn.Module):
    def __init__(self, device, dtype):
        super().__init__()
        # register a dummy parameter to avoid errors in some cases
        self.dummy_param = torch.nn.Parameter(torch.zeros(1))
        self._device = device
        self._dtype = dtype

    def forward(self, *args, **kwargs):
        raise NotImplementedError(
            "This is a fake text encoder and should not be used for inference."
        )
        return None

    @property
    def device(self):
        return self._device
    
    @property
    def dtype(self):
        return self._dtype
    
    def to(self, *args, **kwargs):
        return self


def _model_uses_mps(model: "BaseModel") -> bool:
    return isinstance(getattr(model, "device_torch", None), torch.device) and model.device_torch.type == "mps"


def _replace_text_encoder(
    model: "BaseModel",
    encoder: Optional[torch.nn.Module],
    pipe_attr_name: Optional[str] = None,
) -> FakeTextEncoder:
    fake = FakeTextEncoder(device=model.device_torch, dtype=model.torch_dtype)
    if encoder is not None:
        if _model_uses_mps(model):
            encoder.to("meta")
        else:
            encoder.to("cpu")

    if pipe_attr_name is not None and hasattr(model.pipeline, pipe_attr_name):
        setattr(model.pipeline, pipe_attr_name, fake)

    return fake


def unload_text_encoder(model: "BaseModel"):
    # unload the text encoder in a way that will work with all models and will not throw errors
    # we need to make it appear as a text encoder module without actually having one so all
    # to functions and what not will work.

    if model.text_encoder is not None:
        if isinstance(model.text_encoder, list):
            text_encoder_list = []
            pipe = model.pipeline

            # the pipeline stores text encoders like text_encoder, text_encoder_2, text_encoder_3, etc.
            if hasattr(pipe, "text_encoder"):
                te = _replace_text_encoder(model, pipe.text_encoder, "text_encoder")
                text_encoder_list.append(te)

            i = 2
            while hasattr(pipe, f"text_encoder_{i}"):
                encoder = getattr(pipe, f"text_encoder_{i}")
                te = _replace_text_encoder(model, encoder, f"text_encoder_{i}")
                text_encoder_list.append(te)
                i += 1
            model.text_encoder = text_encoder_list
        else:
            # only has a single text encoder
            pipe_attr_name = "text_encoder" if hasattr(model.pipeline, "text_encoder") else None
            model.text_encoder = _replace_text_encoder(model, model.text_encoder, pipe_attr_name)

    if _model_uses_mps(model) and hasattr(torch.mps, "empty_cache"):
        gc.collect()
        torch.mps.empty_cache()

    flush()
