#!/usr/bin/env python3


def _on_error(e):
    """Code to handle errors"""
    try:
        import traceback
        import sys
        import os

    except ImportError as e:
        # Something has gone seriously wrong
        print(e)
        print("Failed to import requirements. Check that you extracted correctly.")
        input("Press ENTER to continue.")
    else:
        err = "\n".join(
            [traceback.format_exc()]
            + ["Failed to import requirements. Check that you extracted correctly."]
            * isinstance(e, ImportError)
            + [str(e)]
        )
        print(err)
        try:
            with open("crash.log", "w") as f:
                f.write(err)
        except OSError:
            pass
        input("Press ENTER to continue.")
        sys.exit(1)


try:
    import sys

    if sys.version_info[:2] < (3, 10):
        raise Exception("Must be using Python 3.10+")
    import logging
    import os
    import traceback
    import glob
    import time
    import shutil

    def _configure_windows_dll_search_paths() -> None:
        if sys.platform != "win32":
            return

        candidate_dirs: list[str] = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate_dirs.extend(
                [
                    meipass,
                    os.path.join(meipass, "leveldb"),
                    os.path.join(meipass, "wx"),
                ]
            )

        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            internal_dir = os.path.join(exe_dir, "_internal")
            candidate_dirs.extend(
                [
                    internal_dir,
                    os.path.join(internal_dir, "leveldb"),
                    os.path.join(internal_dir, "wx"),
                ]
            )

        seen_dirs = set()
        for path in candidate_dirs:
            if not path:
                continue
            norm_path = os.path.normcase(os.path.normpath(path))
            if norm_path in seen_dirs or not os.path.isdir(path):
                continue
            seen_dirs.add(norm_path)
            try:
                os.add_dll_directory(path)
            except (AttributeError, OSError):
                pass

    _configure_windows_dll_search_paths()
    # Import leveldb before wx to avoid a native crash when opening Bedrock worlds.
    import leveldb
    import wx
    from amulet_map_editor.api.bedrock_open_safety import prepare_bedrock_world_for_open
    import platformdirs
    from typing import NoReturn
    from types import TracebackType
    import threading
    import faulthandler

    if sys.platform == "linux" and wx.VERSION >= (4, 1, 1):
        # bug 247
        os.environ["PYOPENGL_PLATFORM"] = "egl"
except Exception as e_:
    _on_error(e_)


def _init_log():
    logs_path = os.environ["LOG_DIR"]
    # set up handlers
    os.makedirs(logs_path, exist_ok=True)
    # remove all log files older than a week
    for path in glob.glob(os.path.join(glob.escape(logs_path), "*.log")):
        if (
            os.path.isfile(path)
            and os.path.getmtime(path) < time.time() - 3600 * 24 * 7
        ):
            os.remove(path)

    debug = "--amulet-debug" in sys.argv

    log_file = open(
        os.path.join(logs_path, f"amulet_{os.getpid()}.log"),
        "w",
        encoding="utf-8",
    )

    file_handler = logging.StreamHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            "%(levelname)s - %(name)s - %(message)s"
            if debug
            else "%(levelname)s - %(message)s"
        )
    )

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=[file_handler, console_handler],
        force=True,
    )

    log = logging.getLogger(__name__)

    def error_handler(
        exc_type: type[BaseException],
        exc_value: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_value is None:
            return
        log.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = error_handler

    def thread_error_handler(args: threading.ExceptHookArgs) -> None:
        error_handler(args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = thread_error_handler

    # When running via pythonw the stderr is None so log directly to the log file
    faulthandler.enable(log_file)


def _preflight() -> None:
    # Basic preflight checks for write access and disk space.
    def _check_writable(path: str) -> None:
        os.makedirs(path, exist_ok=True)
        test_path = os.path.join(path, f".write_test_{os.getpid()}")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_path)

    # Ensure required dirs are writable
    for key in ("DATA_DIR", "CONFIG_DIR", "CACHE_DIR", "LOG_DIR"):
        value = os.environ.get(key)
        if not value:
            raise Exception(f"Missing required environment variable {key}.")
        _check_writable(value)

    # Check free space in DATA_DIR volume
    try:
        usage = shutil.disk_usage(os.environ["DATA_DIR"])
        if usage.free < 512 * 1024 * 1024:
            raise Exception("Insufficient free disk space (need at least 512MB).")
    except Exception:
        # If disk usage fails, proceed without blocking startup
        pass


def _run_world_probe(path: str) -> int:
    import traceback
    import amulet

    try:
        prepare_bedrock_world_for_open(path)
    except Exception:
        pass

    world = None
    try:
        world = amulet.load_level(path)
        return 0
    except BaseException:
        traceback.print_exc()
        return 1
    finally:
        if world is not None:
            close = getattr(world, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    pass


def main() -> NoReturn:
    try:
        if "--amulet-world-probe" in sys.argv:
            index = sys.argv.index("--amulet-world-probe")
            if index + 1 >= len(sys.argv):
                raise Exception("Missing world path for --amulet-world-probe")
            sys.exit(_run_world_probe(sys.argv[index + 1]))

        # Initialise default paths.
        data_dir = platformdirs.user_data_dir("AmuletMapEditor", "AmuletTeam")
        os.environ.setdefault("DATA_DIR", data_dir)
        config_dir = platformdirs.user_config_dir("AmuletMapEditor", "AmuletTeam")
        if config_dir == data_dir:
            config_dir = os.path.join(data_dir, "Config")
        os.environ.setdefault("CONFIG_DIR", config_dir)
        os.environ.setdefault(
            "CACHE_DIR", platformdirs.user_cache_dir("AmuletMapEditor", "AmuletTeam")
        )
        os.environ.setdefault(
            "LOG_DIR", platformdirs.user_log_dir("AmuletMapEditor", "AmuletTeam")
        )

        _preflight()
        _init_log()
        log = logging.getLogger(__name__)
        log.debug("Importing numpy")
        import numpy

        log.debug("Importing amulet_nbt")
        import amulet_nbt

        _configure_windows_dll_search_paths()
        log.debug("Importing leveldb")
        import leveldb

        log.debug("Importing PyMCTranslate and amulet")
        import PyMCTranslate
        import amulet

        log.debug("Importing minecraft_model_reader")
        import minecraft_model_reader

        log.debug("Importing amulet_map_editor")
        from amulet_map_editor.api.framework import AmuletApp

        log.debug("Finished importing")

    except Exception as e:
        _on_error(e)
    else:
        try:
            app = AmuletApp(0)
            app.MainLoop()
        except Exception as e:
            log.critical(
                f"Amulet Crashed. Sorry about that. Please report it to a developer if you think this is an issue. \n{traceback.format_exc()}"
            )
            input("Press ENTER to continue.")

    sys.exit(0)


if __name__ == "__main__":
    main()
