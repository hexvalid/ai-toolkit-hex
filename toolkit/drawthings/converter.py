import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

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


def _emit_converter_log(log: Optional[Callable[[str], None]], message: str):
    if log is not None:
        log(message)


def _run_command(
    command: list[str],
    *,
    cwd: Optional[Path] = None,
    cancel_event: Optional[threading.Event] = None,
    description: Optional[str] = None,
) -> str:
    if cancel_event is not None and cancel_event.is_set():
        raise DrawThingsCancelledError(f"{description or 'Draw Things command'} cancelled.")

    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Command failed because `{command[0]}` is not installed or not on PATH: {' '.join(command)}"
        ) from exc
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


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _persistent_binary_dir() -> Path:
    configured = os.environ.get("AITK_DRAWTHINGS_BINARY_DIR")
    if configured:
        return Path(configured).expanduser()

    return _project_root() / ".aitk_bin" / "drawthings" / DRAW_THINGS_COMMUNITY_COMMIT[:12]


def _source_build_binary_path(source_dir: Optional[Path] = None) -> Path:
    resolved_source_dir = source_dir if source_dir is not None else _default_source_dir()
    return resolved_source_dir / ".build" / "release" / DRAW_THINGS_CONVERTER_PRODUCT


def get_drawthings_converter_binary_path() -> Path:
    return _persistent_binary_dir() / DRAW_THINGS_CONVERTER_PRODUCT


def _persist_converter_binary(source_binary_path: Path, log: Optional[Callable[[str], None]] = None) -> Path:
    persistent_binary_path = get_drawthings_converter_binary_path()
    persistent_binary_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_binary_path, persistent_binary_path)
    persistent_binary_path.chmod(persistent_binary_path.stat().st_mode | 0o111)
    _emit_converter_log(log, f" - Copied converter binary into project cache: {persistent_binary_path}")
    return persistent_binary_path


def _ensure_swift_toolchain_available(log: Optional[Callable[[str], None]] = None):
    swift_path = shutil.which("swift")
    if swift_path is None:
        raise RuntimeError(
            "Draw Things converter build requires the Swift toolchain, but `swift` was not found on PATH. "
            "Install Xcode Command Line Tools or Xcode, or restore the cached converter binary."
        )
    _emit_converter_log(log, f" - Found Swift toolchain at: {swift_path}")

    if sys.platform == "darwin":
        xcode_select_path = shutil.which("xcode-select")
        if xcode_select_path is None:
            raise RuntimeError(
                "Draw Things converter build requires `xcode-select`, but it was not found. "
                "Install Xcode Command Line Tools or Xcode, or restore the cached converter binary."
            )
        developer_dir = _run_command(
            [xcode_select_path, "-p"],
            description="Xcode toolchain check",
        ).strip()
        if developer_dir == "":
            raise RuntimeError(
                "Draw Things converter build could not resolve the active Xcode developer directory. "
                "Run `xcode-select --install` or `sudo xcode-select -s <Xcode.app/.../Developer>`, "
                "or restore the cached converter binary."
            )
        _emit_converter_log(log, f" - Active Xcode developer dir: {developer_dir}")


def _ensure_source_checkout(
    cancel_event: Optional[threading.Event] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Path:
    source_dir = _default_source_dir()
    package_file = source_dir / "Package.swift"
    pinned_checkout = "AITK_DRAWTHINGS_SOURCE_DIR" not in os.environ

    _emit_converter_log(log, f" - Draw Things source dir: {source_dir}")
    if pinned_checkout:
        _emit_converter_log(log, f" - Pinned Draw Things commit: {DRAW_THINGS_COMMUNITY_COMMIT}")
    else:
        _emit_converter_log(log, " - Using custom Draw Things source dir from AITK_DRAWTHINGS_SOURCE_DIR")

    if package_file.exists():
        _emit_converter_log(log, " - Existing Draw Things source checkout detected")
        git_dir = source_dir / ".git"
        if pinned_checkout and git_dir.exists():
            current_commit = _run_command(
                ["git", "rev-parse", "HEAD"],
                cwd=source_dir,
                cancel_event=cancel_event,
                description="Draw Things source check",
            ).strip()
            if current_commit != DRAW_THINGS_COMMUNITY_COMMIT:
                _emit_converter_log(
                    log,
                    f" - Source checkout is at {current_commit[:12]}; switching to pinned commit",
                )
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
            else:
                _emit_converter_log(log, " - Source checkout already matches pinned commit")
        return source_dir

    if source_dir.exists() and any(source_dir.iterdir()):
        raise RuntimeError(
            f"Draw Things source directory exists but is incomplete: {source_dir}"
        )

    source_dir.parent.mkdir(parents=True, exist_ok=True)
    _emit_converter_log(log, " - Draw Things source checkout is missing; cloning repository")
    _run_command(
        ["git", "clone", DRAW_THINGS_COMMUNITY_REPO_URL, str(source_dir)],
        cancel_event=cancel_event,
        description="Draw Things source clone",
    )
    _emit_converter_log(log, " - Draw Things source clone completed")
    _run_command(
        ["git", "checkout", DRAW_THINGS_COMMUNITY_COMMIT],
        cwd=source_dir,
        cancel_event=cancel_event,
        description="Draw Things source checkout",
    )
    _emit_converter_log(log, " - Checked out pinned Draw Things commit")
    return source_dir


def _patch_package_for_converter(source_dir: Path, log: Optional[Callable[[str], None]] = None):
    package_path = source_dir / "Package.swift"
    package_text = package_path.read_text(encoding="utf-8")
    updated_text = package_text
    package_changed = False

    if DRAW_THINGS_CONVERTER_PRODUCT not in updated_text:
        product_anchor = '    .executable(name: "draw-things-cli", targets: ["DrawThingsCLI"]),\n'
        if product_anchor not in updated_text:
            raise RuntimeError("Unable to patch Draw Things Package.swift: product anchor not found.")
        updated_text = updated_text.replace(
            product_anchor,
            product_anchor + _CONVERTER_PRODUCT_LINE,
            1,
        )
        package_changed = True

    if 'name: "AITKLoRAConverter"' not in updated_text:
        target_anchor = '    .target(\n      name: "ImageGenerator",\n'
        if target_anchor not in updated_text:
            raise RuntimeError("Unable to patch Draw Things Package.swift: target anchor not found.")
        updated_text = updated_text.replace(
            target_anchor,
            _CONVERTER_TARGET_BLOCK + target_anchor,
            1,
        )
        package_changed = True

    if updated_text != package_text:
        package_path.write_text(updated_text, encoding="utf-8")
        _emit_converter_log(log, " - Patched Draw Things Package.swift for aitk-lora-converter")
    elif not package_changed:
        _emit_converter_log(log, " - Draw Things Package.swift already contains aitk-lora-converter target")

    converter_source_dir = source_dir / "Apps" / "AITKLoRAConverter"
    converter_source_dir.mkdir(parents=True, exist_ok=True)
    converter_main_path = converter_source_dir / "main.swift"
    current_main = converter_main_path.read_text(encoding="utf-8") if converter_main_path.exists() else None
    if current_main != _CONVERTER_MAIN_SWIFT:
        converter_main_path.write_text(_CONVERTER_MAIN_SWIFT, encoding="utf-8")
        _emit_converter_log(log, " - Wrote Draw Things converter entrypoint source")
    else:
        _emit_converter_log(log, " - Draw Things converter entrypoint source is already up to date")


def ensure_drawthings_converter_binary(
    cancel_event: Optional[threading.Event] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Path:
    with _CONVERTER_LOCK:
        binary_path = get_drawthings_converter_binary_path()
        _emit_converter_log(log, f" - Draw Things converter binary path: {binary_path}")
        if binary_path.exists():
            _emit_converter_log(log, " - Converter binary already exists; skipping Swift build")
            return binary_path

        source_dir = _ensure_source_checkout(cancel_event=cancel_event, log=log)
        _patch_package_for_converter(source_dir, log=log)

        source_binary_path = _source_build_binary_path(source_dir)
        _emit_converter_log(log, f" - Swift build output path: {source_binary_path}")
        if source_binary_path.exists():
            _emit_converter_log(log, " - Converter binary already exists after source preparation; skipping Swift build")
            return _persist_converter_binary(source_binary_path, log=log)

        _ensure_swift_toolchain_available(log=log)
        _emit_converter_log(log, " - Running: swift build -c release --product aitk-lora-converter")
        build_started_at = time.monotonic()
        try:
            _run_command(
                ["swift", "build", "-c", "release", "--product", DRAW_THINGS_CONVERTER_PRODUCT],
                cwd=source_dir,
                cancel_event=cancel_event,
                description="Draw Things converter build",
            )
        except Exception as exc:
            _emit_converter_log(log, f" - Swift build failed: {exc}")
            raise RuntimeError(
                "Failed to build the Draw Things LoRA converter before training started. "
                "This job cannot continue without that binary. "
                "Install the required Swift/Xcode tooling or restore the cached converter binary. "
                f"Original error: {exc}"
            ) from exc
        if not source_binary_path.exists():
            raise RuntimeError("Draw Things LoRA converter build finished without producing a binary.")
        _emit_converter_log(
            log,
            f" - Swift build completed in {time.monotonic() - build_started_at:.1f}s",
        )
        return _persist_converter_binary(source_binary_path, log=log)


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
