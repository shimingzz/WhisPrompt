"""Entry point. Default launches the GUI; --headless runs servers only."""
import argparse
import logging
import sys


def build_pipeline():
    from .config import Settings, ensure_dirs
    from .llm import OllamaClient
    from .server import Pipeline
    from .transcriber import Transcriber

    ensure_dirs()
    settings = Settings.load()
    return Pipeline(
        settings=settings,
        transcriber=Transcriber(settings.whisper_model),
        llm=OllamaClient(settings),
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="whisprompt")
    parser.add_argument("--headless", action="store_true", help="run servers without GUI")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    pipeline = build_pipeline()

    if args.headless:
        from .server import ServerManager

        manager = ServerManager(pipeline)
        manager.start()
        print(f"PWA:        {manager.app_url}")
        print(f"憑證安裝頁: {manager.helper_url}")
        print("預先載入 Whisper 模型中...")
        import threading
        threading.Thread(target=pipeline.backfill_titles, daemon=True).start()
        pipeline.transcriber.load()
        print(f"Whisper 已載入 ({pipeline.transcriber.device})。Ctrl+C 結束。")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop()
        return 0

    from .gui.main_window import run_gui

    return run_gui(pipeline)


if __name__ == "__main__":
    sys.exit(main())
