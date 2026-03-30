from .chroma import ChromaModel, ChromaRadianceModel
from .hidream import HidreamModel, HidreamE1Model
from .f_light import FLiteModel
from .omnigen2 import OmniGen2Model
from .flux_kontext import FluxKontextModel
from .wan22 import Wan225bModel, Wan2214bModel, Wan2214bI2VModel
from .qwen_image import QwenImageModel, QwenImageEditModel, QwenImageEditPlusModel
from .flux2 import Flux2Model, Flux2Klein4BModel, Flux2Klein9BModel
from .z_image import ZImageModel
from .zeta_chroma import ZetaChromaModel

try:
    from .ltx2 import LTX2Model, LTX23Model
    _ltx2_import_error = None
except ImportError as import_error:
    _ltx2_import_error = import_error

    class LTX2Model:
        arch = "ltx2"

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "LTX2 support is unavailable because the installed diffusers package "
                f"is missing required symbols: {_ltx2_import_error}"
            ) from _ltx2_import_error

    class LTX23Model:
        arch = "ltx2.3"

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "LTX2.3 support is unavailable because the installed diffusers package "
                f"is missing required symbols: {_ltx2_import_error}"
            ) from _ltx2_import_error

    print(f"Skipping LTX2 model imports: {_ltx2_import_error}")

AI_TOOLKIT_MODELS = [
    # put a list of models here
    ChromaModel,
    ChromaRadianceModel,
    HidreamModel,
    HidreamE1Model,
    FLiteModel,
    OmniGen2Model,
    FluxKontextModel,
    Wan225bModel,
    Wan2214bI2VModel,
    Wan2214bModel,
    QwenImageModel,
    QwenImageEditModel,
    QwenImageEditPlusModel,
    Flux2Model,
    ZImageModel,
    LTX2Model,
    LTX23Model,
    Flux2Klein4BModel,
    Flux2Klein9BModel,
    ZetaChromaModel,
]
