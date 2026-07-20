from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import shutil
import socket
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
UI_SOURCE = ROOT / "src" / "future_assistant" / "ui"
TOOLS_DIR = Path(__file__).resolve().parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _prepare_capture_ui(destination: Path) -> None:
    shutil.copytree(UI_SOURCE, destination)
    shutil.copy2(TOOLS_DIR / "judge_demo_state.js", destination / "judge_demo_state.js")
    shutil.copy2(TOOLS_DIR / "judge_demo_bridge.js", destination / "judge_demo_bridge.js")
    shutil.copy2(TOOLS_DIR / "judge_demo_driver.js", destination / "judge_demo_driver.js")

    index_path = destination / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="today.css" />',
        "\n".join(
            (
                '<link rel="stylesheet" href="today.css" />',
                '<link rel="stylesheet" href="verified_v2.css" />',
                '<link rel="stylesheet" href="memory_v2.css" />',
            )
        ),
    )
    html = html.replace(
        '<script src="app.js"></script>',
        "\n".join(
            (
                '<script src="judge_demo_state.js"></script>',
                '<script src="judge_demo_bridge.js"></script>',
                '<script src="app.js"></script>',
            )
        ),
    )
    html = html.replace(
        '<script src="today.js"></script>',
        "\n".join(
            (
                '<script src="today.js"></script>',
                '<script src="verified_v2.js"></script>',
                '<script src="memory_v2.js"></script>',
                '<script src="judge_demo_driver.js"></script>',
            )
        ),
    )
    index_path.write_text(html, encoding="utf-8")


@contextlib.contextmanager
def _serve(directory: Path) -> Iterator[str]:
    port = _free_port()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _convert_to_mp4(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        check=True,
    )


def render(output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="rayluno-judge-video-") as temp:
        temp_path = Path(temp)
        capture_ui = temp_path / "ui"
        video_dir = temp_path / "video"
        _prepare_capture_ui(capture_ui)
        video_dir.mkdir()

        with _serve(capture_ui) as url, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                locale="en-GB",
                record_video_dir=str(video_dir),
                record_video_size={"width": 1600, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            page.wait_for_function(
                "window.__RAYLUNO_DEMO_DONE__ === true || Boolean(window.__RAYLUNO_DEMO_ERROR__)",
                timeout=120_000,
            )
            error = page.evaluate("window.__RAYLUNO_DEMO_ERROR__ || null")
            if error:
                raise RuntimeError(f"Judge demo driver failed: {error}")
            page.wait_for_timeout(1_000)
            video = page.video
            context.close()
            browser.close()
            if video is None:
                raise RuntimeError("Playwright did not produce a recording.")
            recorded_path = Path(video.path())

        _convert_to_mp4(recorded_path, output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Rayluno's silent judge-demo capture.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/rayluno-judge-demo-raw.mp4"),
    )
    args = parser.parse_args()
    render(args.output.resolve())
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
