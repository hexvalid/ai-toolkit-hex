import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from .exceptions import DrawThingsCancelledError

DRAW_THINGS_COMMUNITY_REPO_URL = "https://github.com/drawthingsai/draw-things-community"
DRAW_THINGS_COMMUNITY_COMMIT = "5391e641c2a53769189e1672993059d2d34a6fae"
DRAW_THINGS_CONVERTER_PRODUCT = "aitk-lora-converter"

_CONVERTER_LOCK = threading.Lock()

_CONVERTER_PRODUCT_LINE = '    .executable(name: "aitk-lora-converter", targets: ["AITKLoRAConverter"]),\n'
_CONVERTER_TARGET_BLOCK = """    .executableTarget(
      name: "AITKLoRAConverter",
      dependencies: [
        "Diffusion",
        "ModelOp",
        "ModelZoo",
        .product(name: "ArgumentParser", package: "swift-argument-parser"),
      ],
      path: "Apps/AITKLoRAConverter"
    ),

"""
_CONVERTER_MAIN_SWIFT = """import ArgumentParser
import Diffusion
import Foundation
import ModelOp
import ModelZoo

extension ModelVersion: ExpressibleByArgument {}

@main
struct AITKLoRAConverter: ParsableCommand {
  @Option(name: .shortAndLong, help: "Input LoRA safetensors/ckpt file.")
  var input: String

  @Option(name: .shortAndLong, help: "Output directory for converted Draw Things LoRA.")
  var outputDirectory: String

  @Option(name: .shortAndLong, help: "Display name for the LoRA.")
  var name: String

  @Option(help: "Force model version when known.")
  var version: ModelVersion?

  @Option(help: "Optional scale factor.")
  var scaleFactor: Double?

  mutating func run() throws {
    try FileManager.default.createDirectory(
      at: URL(fileURLWithPath: outputDirectory),
      withIntermediateDirectories: true
    )
    ModelZoo.externalUrls = [URL(fileURLWithPath: outputDirectory)]
    let fileName = Importer.cleanup(filename: name) + "_lora_f16.ckpt"
    let scale = scaleFactor ?? 1.0
    let result = try LoRAImporter.import(
      downloadedFile: input,
      name: name,
      filename: fileName,
      scaleFactor: scale,
      forceVersion: version
    ) { _ in
    }

    print("file=\\(fileName)")
    print("version=\\(result.0)")
    print("ti_embedding=\\(result.1)")
    print("text_embedding_length=\\(result.2)")
    print("is_loha=\\(result.3)")
  }
}
"""


def _run_command(
    command: list[str],
    *,
    cwd: Optional[Path] = None,
    cancel_event: Optional[threading.Event] = None,
    description: Optional[str] = None,
) -> str:
    if cancel_event is not None and cancel_event.is_set():
        raise DrawThingsCancelledError(f"{description or 'Draw Things command'} cancelled.")

    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = ""
    while True:
        try:
            stdout, _ = process.communicate(timeout=0.2)
            output = stdout or ""
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise DrawThingsCancelledError(f"{description or 'Draw Things command'} cancelled.")
            time.sleep(0.05)

    if process.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {process.returncode}: {' '.join(command)}\n{output.strip()}"
        )
    return output


def _default_source_dir() -> Path:
    configured = os.environ.get("AITK_DRAWTHINGS_SOURCE_DIR")
    if configured:
        return Path(configured).expanduser()

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ai-toolkit" / "draw-things-community"
    return Path.home() / ".cache" / "ai-toolkit" / "draw-things-community"


def _ensure_source_checkout(cancel_event: Optional[threading.Event] = None) -> Path:
    source_dir = _default_source_dir()
    package_file = source_dir / "Package.swift"
    pinned_checkout = "AITK_DRAWTHINGS_SOURCE_DIR" not in os.environ

    if package_file.exists():
        git_dir = source_dir / ".git"
        if pinned_checkout and git_dir.exists():
            current_commit = _run_command(
                ["git", "rev-parse", "HEAD"],
                cwd=source_dir,
                cancel_event=cancel_event,
                description="Draw Things source check",
            ).strip()
            if current_commit != DRAW_THINGS_COMMUNITY_COMMIT:
                _run_command(
                    ["git", "fetch", "--all", "--tags"],
                    cwd=source_dir,
                    cancel_event=cancel_event,
                    description="Draw Things source fetch",
                )
                _run_command(
                    ["git", "checkout", DRAW_THINGS_COMMUNITY_COMMIT],
                    cwd=source_dir,
                    cancel_event=cancel_event,
                    description="Draw Things source checkout",
                )
        return source_dir

    if source_dir.exists() and any(source_dir.iterdir()):
        raise RuntimeError(
            f"Draw Things source directory exists but is incomplete: {source_dir}"
        )

    source_dir.parent.mkdir(parents=True, exist_ok=True)
    _run_command(
        ["git", "clone", DRAW_THINGS_COMMUNITY_REPO_URL, str(source_dir)],
        cancel_event=cancel_event,
        description="Draw Things source clone",
    )
    _run_command(
        ["git", "checkout", DRAW_THINGS_COMMUNITY_COMMIT],
        cwd=source_dir,
        cancel_event=cancel_event,
        description="Draw Things source checkout",
    )
    return source_dir


def _patch_package_for_converter(source_dir: Path):
    package_path = source_dir / "Package.swift"
    package_text = package_path.read_text(encoding="utf-8")
    updated_text = package_text

    if DRAW_THINGS_CONVERTER_PRODUCT not in updated_text:
        product_anchor = '    .executable(name: "draw-things-cli", targets: ["DrawThingsCLI"]),\n'
        if product_anchor not in updated_text:
            raise RuntimeError("Unable to patch Draw Things Package.swift: product anchor not found.")
        updated_text = updated_text.replace(
            product_anchor,
            product_anchor + _CONVERTER_PRODUCT_LINE,
            1,
        )

    if 'name: "AITKLoRAConverter"' not in updated_text:
        target_anchor = '    .target(\n      name: "ImageGenerator",\n'
        if target_anchor not in updated_text:
            raise RuntimeError("Unable to patch Draw Things Package.swift: target anchor not found.")
        updated_text = updated_text.replace(
            target_anchor,
            _CONVERTER_TARGET_BLOCK + target_anchor,
            1,
        )

    if updated_text != package_text:
        package_path.write_text(updated_text, encoding="utf-8")

    converter_source_dir = source_dir / "Apps" / "AITKLoRAConverter"
    converter_source_dir.mkdir(parents=True, exist_ok=True)
    converter_main_path = converter_source_dir / "main.swift"
    current_main = converter_main_path.read_text(encoding="utf-8") if converter_main_path.exists() else None
    if current_main != _CONVERTER_MAIN_SWIFT:
        converter_main_path.write_text(_CONVERTER_MAIN_SWIFT, encoding="utf-8")


def ensure_drawthings_converter_binary(cancel_event: Optional[threading.Event] = None) -> Path:
    with _CONVERTER_LOCK:
        source_dir = _ensure_source_checkout(cancel_event=cancel_event)
        _patch_package_for_converter(source_dir)

        binary_path = source_dir / ".build" / "release" / DRAW_THINGS_CONVERTER_PRODUCT
        package_path = source_dir / "Package.swift"
        converter_main_path = source_dir / "Apps" / "AITKLoRAConverter" / "main.swift"
        if (
            binary_path.exists()
            and binary_path.stat().st_mtime >= package_path.stat().st_mtime
            and binary_path.stat().st_mtime >= converter_main_path.stat().st_mtime
        ):
            return binary_path

        _run_command(
            ["swift", "build", "-c", "release", "--product", DRAW_THINGS_CONVERTER_PRODUCT],
            cwd=source_dir,
            cancel_event=cancel_event,
            description="Draw Things converter build",
        )
        if not binary_path.exists():
            raise RuntimeError("Draw Things LoRA converter build finished without producing a binary.")
        return binary_path


def convert_lora_for_drawthings(
    *,
    input_path: str,
    output_dir: str,
    name: str,
    version: Optional[str] = None,
    scale_factor: Optional[float] = None,
    cancel_event: Optional[threading.Event] = None,
) -> str:
    binary_path = ensure_drawthings_converter_binary(cancel_event=cancel_event)
    command = [
        str(binary_path),
        "--input",
        input_path,
        "--output-directory",
        output_dir,
        "--name",
        name,
    ]
    if version is not None:
        command.extend(["--version", version])
    if scale_factor is not None:
        command.extend(["--scale-factor", str(scale_factor)])

    output = _run_command(
        command,
        cancel_event=cancel_event,
        description="Draw Things LoRA conversion",
    )
    metadata: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        metadata[key] = value

    file_name = metadata.get("file")
    if file_name is None or file_name.strip() == "":
        raise RuntimeError(f"Draw Things LoRA converter did not return an output file.\n{output.strip()}")
    return str(Path(output_dir) / file_name)
