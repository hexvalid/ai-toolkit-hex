import hashlib
import ipaddress
import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import flatbuffers
import grpc
import numpy as np
from PIL import Image

try:
    import fpzip
except ImportError:  # pragma: no cover - optional at import time
    fpzip = None

from toolkit.drawthings.generated.config_generated import GenerationConfigurationT, LoRAT
from toolkit.drawthings.generated import imageService_pb2, imageService_pb2_grpc


DRAW_THINGS_SAMPLERS = [
    "DPM++ 2M Karras",
    "Euler A",
    "DDIM",
    "PLMS",
    "DPM++ SDE Karras",
    "UniPC",
    "LCM",
    "Euler A Substep",
    "DPM++ SDE Substep",
    "TCD",
    "Euler A Trailing",
    "DPM++ SDE Trailing",
    "DPM++ 2M AYS",
    "Euler A AYS",
    "DPM++ SDE AYS",
    "DPM++ 2M Trailing",
    "DDIM Trailing",
    "UniPC Trailing",
    "UniPC AYS",
]

DRAW_THINGS_SEED_MODES = [
    "Legacy",
    "TorchCpuCompatible",
    "ScaleAlike",
    "NvidiaGpuCompatible",
]

DRAW_THINGS_LORA_MODES = [
    "All",
    "Base",
    "Refiner",
]

ARCH_TO_DRAW_THINGS_VERSION = {
    "flux": "flux1",
    "flux_kontext": "flux1",
    "flux2_klein_9b": "flux2_9b",
    "hidream": "hidream_i1",
    "hidream_e1": "hidream_i1",
    "sdxl": "sdxl_base_v0.9",
    "sd15": "v1",
    "wan21:1b": "wan_v2.1_1.3b",
    "wan21:14b": "wan_v2.1_14b",
    "wan21_i2v:14b": "wan_v2.1_14b",
    "wan21_i2v:14b480p": "wan_v2.1_14b",
    "wan22_14b:t2v": "wan_v2.2_14b",
    "wan22_14b_i2v": "wan_v2.2_14b",
    "wan22_5b": "wan_v2.2_5b",
}

DRAW_THINGS_ROOT_CA_CERT = b"""-----BEGIN CERTIFICATE-----
MIIFHTCCAwWgAwIBAgIUWxJuoygy7Hsb9bcSfggNGLGZJW4wDQYJKoZIhvcNAQEL
BQAwHjEcMBoGA1UEAwwTRHJhdyBUaGluZ3MgUm9vdCBDQTAeFw0yNDEwMTUxNzI3
NTJaFw0zNDEwMTMxNzI3NTJaMB4xHDAaBgNVBAMME0RyYXcgVGhpbmdzIFJvb3Qg
Q0EwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQDe/RKAuabH2pEadZj6
JRTOaEIMYXsAI7ZIG+LSAEkyK/QZAMdLq+wBq6uJDIEvTXMyyhNgkI3oUnS2PJqi
y9lzGAh1s2y6MDG17BFboyriW0y6BKd42amX/g9A40ZC1cBs2NI9e0zjy/vhHLw1
EHK1XDLsIYAZvqQLJR3zRslHTHN6BysNWNmO/s1myLHQzbjyg4+/JHqma5Xatz0W
I5Wi6zxu/G1IdWeO6tlWWBSArDbhru+rb2U9p9/jKGW7fOom7sH9oBpj7q+xcrr5
h2Aoam4xRqxc3SG7TRc1inEki86/FoWCARSqGo2t7q/brkwwGbeZsuwKhIuhWGzW
CJKp0NvD11HyCqsJsLMTx9PXzEsCDFsios+zI6zu1aIVomO5h8d59oxMGEvNozIc
gSHJI3pCiHmJt0o9xoRi0UGiB6PP3k4ZzxTV30wt0oMOzS8dgMdl1u0zpAc2aEGG
4cdWQaDP2UgZlNQyzGbGUC2Q2ln1ghTlEBAs23/yDZyEbtWj+Qo1Isk80CXISs8/
H4cdM9Xw/Rt5fGxSaNzHJZJ9gK8YFI0z7IDiQp9nWkMqyDhGjhT4ZR847Nz52gcK
zuqmSK6B7ksumilchQ8hq79VAAvZqQoyVIvLvkbb6pXZbH0qTK5yk0YQVJ49JU1L
XnB4Iu8IuDxTLmtW2WoCjUZaqQIDAQABo1MwUTAdBgNVHQ4EFgQUhmFk2qHWAU6/
3u6FyCnk2vaV0fswHwYDVR0jBBgwFoAUhmFk2qHWAU6/3u6FyCnk2vaV0fswDwYD
VR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAgEAdvryE1xbhpyDjtP+I95Z
tgmlkmIWTPoHL5WO20SWtWjryHTs0XGXkohqSFKBqYTOVTyRCTtUTF4nWoNfBhlz
aOExf64UgvYHO4NxcPNjUH2Yx/AKFWBeHx50jfjz/zTSqhAHv8rlYDt6rlLs1aFm
rNj3DObqmTfDoI8qkdLK8bekjhul6PusmezhW+qa/DMvDRy3moUugpXwzvyG5GRW
C3+nNbBdCdblUyiEgFu5htH6hSSu2IX5t/ryoKNjAAfUxMKcNFdYCnzWiHKOlrmp
wYL4YhVQZZYmis8ZIFOQ+BKVQHJcqE5bdrbNbCpurMNODEuDDB/VkbGHEVFVgB0n
x+ZtaGnfTeJJ6h7IIl+Gnpx0u9k+2pu78cEQ+6ZYKaGUoOKccxgipsSXWL75qHl9
7/scB3imqRq0Q7/jKP6mvcB3/5irQwVmczsFwELLP0LJdsCZMcQQQsSCGuskzcAJ
iiiGzRVTfYFUu2hJ5JIgewg+NEzMCwzR5yyWacBcrrDxQTymTNW9NWahHxvdZJHd
zRd4Y3HNLPikGg37mCYIPWtUxJCU7/lZleNSqlMBhDdbIZcAqaHOQlYJQSZaTMwK
kWF1y/C6TdCKWyXhAEV8zp/0q4b6vC1ynn/GfopROPXceLbGA+BLG9JEQ1AiGae3
ejQ40oILyZjEclMPGLYjqoQ=
-----END CERTIFICATE-----
"""

def infer_drawthings_model_version(model_arch: Optional[str]) -> Optional[str]:
    if model_arch is None:
        return None
    return ARCH_TO_DRAW_THINGS_VERSION.get(model_arch)


def _decode_response_tensor_bytes(response_image: bytes) -> np.ndarray:
    int_buffer = np.frombuffer(response_image, dtype=np.uint32, count=17)
    height, width, channels = int_buffer[6:9]
    length = width * height * channels * 2
    is_compressed = int_buffer[0] == 1012247

    if is_compressed:
        if fpzip is None:
            raise RuntimeError(
                "Draw Things returned a compressed image tensor but `fpzip` is not installed."
            )
        uncompressed = fpzip.decompress(response_image[68:], order="C")
        buffer = uncompressed.astype(np.float16).tobytes()
    else:
        buffer = response_image[68:]

    return np.frombuffer(buffer, dtype=np.float16, count=length // 2)


def convert_response_image(response_image: bytes) -> Image.Image:
    int_buffer = np.frombuffer(response_image, dtype=np.uint32, count=17)
    height, width, channels = int_buffer[6:9]

    data = _decode_response_tensor_bytes(response_image)
    if data.size == 0:
        raise RuntimeError("Draw Things returned an empty image tensor.")
    if np.isnan(data[0]):
        raise RuntimeError("Draw Things returned an invalid image tensor (NaN detected).")

    data = np.clip((data + 1) * 127, 0, 255).astype(np.uint8)
    mode = "RGBA" if channels == 4 else "RGB"
    return Image.frombytes(mode, (width, height), bytes(data))


@dataclass
class DrawThingsConfig:
    server: str
    port: int
    use_tls: bool = False
    shared_secret: Optional[str] = None
    model: Optional[str] = None
    seed_mode: str = "ScaleAlike"
    clip_skip: int = 1
    lora_mode: str = "All"


@dataclass
class DrawThingsGenerationRequest:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed: int
    sampler: str
    model_file: str
    lora_file: Optional[str] = None
    lora_weight: float = 1.0
    seed_mode: str = "ScaleAlike"
    clip_skip: int = 1
    lora_mode: str = "All"
    num_frames: int = 1
    fps: int = 1
    model_version: Optional[str] = None
    model_name: Optional[str] = None
    model_prefix: str = ""


class DrawThingsClient:
    def __init__(self, config: DrawThingsConfig):
        self.config = config
        self._catalog: Optional[dict[str, Any]] = None
        self._resolved_use_tls: Optional[bool] = None

    def _base_channel_options(self) -> list[tuple[str, Any]]:
        return [
            ("grpc.max_send_message_length", -1),
            ("grpc.max_receive_message_length", -1),
        ]

    def _should_override_tls_hostname(self) -> bool:
        server = str(self.config.server or "").strip()
        if server == "":
            return False
        if server.lower() == "localhost":
            return True
        try:
            ipaddress.ip_address(server)
            return True
        except ValueError:
            return False

    def _channel(self, use_tls: bool):
        options = self._base_channel_options()
        if use_tls:
            if self._should_override_tls_hostname():
                options.extend([
                    ("grpc.ssl_target_name_override", "localhost"),
                    ("grpc.default_authority", "localhost"),
                ])
            credentials = grpc.ssl_channel_credentials(root_certificates=DRAW_THINGS_ROOT_CA_CERT)
            return grpc.secure_channel(f"{self.config.server}:{self.config.port}", credentials, options=options)
        return grpc.insecure_channel(f"{self.config.server}:{self.config.port}", options=options)

    def _stub(self, channel):
        return imageService_pb2_grpc.ImageGenerationServiceStub(channel)

    def _with_secret(self, payload):
        if self.config.shared_secret:
            payload.sharedSecret = self.config.shared_secret
        return payload

    @staticmethod
    def _decode_override_field(raw_value: bytes) -> list[dict[str, Any]]:
        if raw_value is None or len(raw_value) == 0:
            return []
        try:
            decoded = raw_value.decode("utf-8")
            return json.loads(decoded)
        except Exception as exc:
            raise RuntimeError("Failed to decode Draw Things metadata override payload.") from exc

    def _transport_attempts(self) -> list[bool]:
        if self._resolved_use_tls is not None:
            return [self._resolved_use_tls]
        attempts = [bool(self.config.use_tls)]
        if not self.config.use_tls:
            attempts.append(True)
        else:
            attempts.append(False)
        return attempts

    @staticmethod
    def _grpc_error_details(exc: grpc.RpcError) -> str:
        details = exc.details()
        if isinstance(details, str) and details.strip() != "":
            return details
        return str(exc)

    @classmethod
    def _is_transport_mismatch_error(cls, exc: grpc.RpcError) -> bool:
        code = exc.code()
        details = cls._grpc_error_details(exc).lower()
        if code not in {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.UNKNOWN, grpc.StatusCode.INTERNAL}:
            return False
        mismatch_markers = [
            "socket closed",
            "failed to connect to all addresses",
            "tls",
            "ssl",
            "handshake",
            "peer name",
            "certificate verify failed",
            "wrong version number",
        ]
        return any(marker in details for marker in mismatch_markers)

    def _run_rpc(self, operation_name: str, callback):
        errors: list[tuple[bool, grpc.RpcError]] = []
        attempts = self._transport_attempts()
        for index, use_tls in enumerate(attempts):
            channel = self._channel(use_tls)
            try:
                result = callback(self._stub(channel))
                self._resolved_use_tls = use_tls
                return result
            except grpc.RpcError as exc:
                errors.append((use_tls, exc))
                has_more_attempts = index < len(attempts) - 1
                if has_more_attempts and self._resolved_use_tls is None and self._is_transport_mismatch_error(exc):
                    continue
                raise RuntimeError(
                    f"{operation_name} failed against Draw Things server at "
                    f"{self.config.server}:{self.config.port}: {self._grpc_error_details(exc)}"
                ) from exc
            finally:
                channel.close()

        if len(errors) > 0:
            use_tls, exc = errors[-1]
            transport_label = "TLS" if use_tls else "plaintext"
            raise RuntimeError(
                f"{operation_name} failed against Draw Things server at "
                f"{self.config.server}:{self.config.port} over {transport_label}: {self._grpc_error_details(exc)}"
            ) from exc

    @property
    def resolved_use_tls(self) -> Optional[bool]:
        return self._resolved_use_tls

    def get_catalog(self) -> dict[str, Any]:
        if self._catalog is not None:
            return self._catalog

        def request_catalog(stub):
            request = imageService_pb2.EchoRequest(name="ai-toolkit")
            request = self._with_secret(request)
            response = stub.Echo(request)

            if getattr(response, "sharedSecretMissing", False) and not self.config.shared_secret:
                raise RuntimeError(
                    "Draw Things server requires a shared secret. Fill `Sample > Draw Things > Shared Secret`."
                )

            override = response.override if response.HasField("override") else imageService_pb2.MetadataOverride()
            self._catalog = {
                "files": list(response.files),
                "models": self._decode_override_field(override.models),
                "loras": self._decode_override_field(override.loras),
                "controlNets": self._decode_override_field(override.controlNets),
                "textualInversions": self._decode_override_field(override.textualInversions),
                "upscalers": self._decode_override_field(override.upscalers),
            }
            return self._catalog

        return self._run_rpc("Draw Things catalog request", request_catalog)

    def _build_model_info(self, request: DrawThingsGenerationRequest) -> dict[str, Any]:
        catalog = self.get_catalog()
        model_info = next(
            (model for model in catalog["models"] if model.get("file") == request.model_file),
            None,
        )
        if model_info is not None:
            return model_info

        if request.model_version is None:
            raise RuntimeError(
                "Selected Draw Things model was not found in the server catalog, and its version could not be inferred."
            )

        return {
            "file": request.model_file,
            "name": request.model_name or os.path.basename(request.model_file),
            "version": request.model_version,
            "prefix": request.model_prefix or "",
        }

    def upload_file(self, local_path: str, remote_filename: str) -> None:
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Draw Things upload source does not exist: {local_path}")

        remote_filename = os.path.basename(remote_filename)
        file_size = os.path.getsize(local_path)
        sha256 = hashlib.sha256()
        with open(local_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha256.update(chunk)
        digest = sha256.digest()

        def request_iterator():
            init_request = imageService_pb2.FileUploadRequest(
                initRequest=imageService_pb2.InitUploadRequest(
                    filename=remote_filename,
                    sha256=digest,
                    totalSize=file_size,
                )
            )
            yield self._with_secret(init_request)

            offset = 0
            with open(local_path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    payload = imageService_pb2.FileUploadRequest(
                        chunk=imageService_pb2.FileChunk(
                            filename=remote_filename,
                            content=chunk,
                            offset=offset,
                        )
                    )
                    yield self._with_secret(payload)
                    offset += len(chunk)

        def do_upload(stub):
            responses = stub.UploadFile(request_iterator())
            saw_response = False
            for response in responses:
                saw_response = True
                if not response.chunkUploadSuccess:
                    raise RuntimeError(
                        f"Draw Things upload failed for {remote_filename}: {response.message or 'unknown error'}"
                    )
            if not saw_response:
                raise RuntimeError(f"Draw Things upload returned no response for {remote_filename}.")

        self._run_rpc(f"Uploading {remote_filename}", do_upload)

    def generate(self, request: DrawThingsGenerationRequest) -> list[Image.Image]:
        if request.sampler not in DRAW_THINGS_SAMPLERS:
            raise ValueError(f"Unsupported Draw Things sampler: {request.sampler}")
        if request.seed_mode not in DRAW_THINGS_SEED_MODES:
            raise ValueError(f"Unsupported Draw Things seed mode: {request.seed_mode}")
        if request.lora_file is not None and request.lora_mode not in DRAW_THINGS_LORA_MODES:
            raise ValueError(f"Unsupported Draw Things LoRA mode: {request.lora_mode}")

        model_info = self._build_model_info(request)
        model_version = model_info.get("version", request.model_version)
        if model_version is None:
            raise RuntimeError("Unable to determine Draw Things model version for sampling.")

        width = max(64, int(round(request.width / 64.0) * 64))
        height = max(64, int(round(request.height / 64.0) * 64))

        config = GenerationConfigurationT()
        config.startWidth = width // 64
        config.startHeight = height // 64
        config.seed = int(request.seed % 4294967295)
        config.steps = int(request.steps)
        config.guidanceScale = float(request.guidance_scale)
        config.model = request.model_file
        config.sampler = DRAW_THINGS_SAMPLERS.index(request.sampler)
        config.batchCount = 1
        config.batchSize = 1
        config.seedMode = DRAW_THINGS_SEED_MODES.index(request.seed_mode)
        config.clipSkip = max(1, int(request.clip_skip))
        if request.lora_file is not None:
            config.loras = [
                LoRAT(
                    file=os.path.basename(request.lora_file),
                    weight=float(request.lora_weight),
                    mode=DRAW_THINGS_LORA_MODES.index(request.lora_mode),
                )
            ]

        if request.num_frames > 1:
            config.numFrames = int(request.num_frames)
            config.fpsId = max(1, int(request.fps))

        if str(model_version).startswith("sdxl"):
            config.originalImageHeight = height
            config.targetImageHeight = height
            config.negativeOriginalImageHeight = height // 2
            config.originalImageWidth = width
            config.targetImageWidth = width
            config.negativeOriginalImageWidth = width // 2

        builder = flatbuffers.Builder(0)
        builder.Finish(config.Pack(builder))
        config_fbs = bytes(builder.Output())

        override_kwargs = {
            "models": json.dumps([model_info]).encode("utf-8"),
        }
        if request.lora_file is not None:
            lora_info = {
                "file": os.path.basename(request.lora_file),
                "name": os.path.basename(request.lora_file),
                "version": model_version,
                "prefix": "",
                "mode": request.lora_mode,
            }
            override_kwargs["loras"] = json.dumps([lora_info]).encode("utf-8")

        override = imageService_pb2.MetadataOverride(**override_kwargs)

        def do_generate(stub):
            generation_request = imageService_pb2.ImageGenerationRequest(
                prompt=request.prompt,
                negativePrompt=request.negative_prompt,
                configuration=config_fbs,
                override=override,
                user="ai-toolkit",
                device=imageService_pb2.LAPTOP,
            )
            generation_request = self._with_secret(generation_request)

            response_stream = stub.GenerateImage(generation_request)
            response_images: list[bytes] = []
            for response in response_stream:
                if len(response.generatedImages) > 0:
                    response_images.extend(response.generatedImages)

            if len(response_images) == 0:
                raise RuntimeError("Draw Things returned no generated images.")

            return [convert_response_image(response_image) for response_image in response_images]

        return self._run_rpc("Draw Things image generation", do_generate)
