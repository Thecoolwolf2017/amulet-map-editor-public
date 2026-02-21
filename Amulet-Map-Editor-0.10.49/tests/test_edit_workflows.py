import inspect
import tempfile
import unittest
from pathlib import Path


def _require_module(name: str):
    try:
        module = __import__(name)
    except Exception as exc:
        return None, exc
    return module, None


def _get_latest_version(translation_manager, platform: str):
    try:
        versions = translation_manager.version_numbers(platform)
    except Exception:
        versions = []
    if versions:
        return max(versions)
    # Fallback to a commonly supported version tuple.
    return (1, 16, 0)


def _call_create_and_open(wrapper, platform: str, version):
    signature = inspect.signature(wrapper.create_and_open)
    kwargs = {}
    if "platform" in signature.parameters:
        kwargs["platform"] = platform
    if "version" in signature.parameters:
        kwargs["version"] = version
    if "bounds" in signature.parameters or "selection" in signature.parameters:
        try:
            from amulet.api.selection import SelectionGroup, SelectionBox

            bounds = SelectionGroup([SelectionBox((0, 0, 0), (16, 16, 16))])
            if "bounds" in signature.parameters:
                kwargs["bounds"] = bounds
            if "selection" in signature.parameters:
                kwargs["selection"] = bounds
        except Exception:
            pass
    if "overwrite" in signature.parameters:
        kwargs["overwrite"] = True
    return wrapper.create_and_open(**kwargs)


def _get_world_api():
    amulet, err = _require_module("amulet")
    if amulet is None:
        raise unittest.SkipTest(f"amulet not available: {err}")

    PyMCTranslate, err = _require_module("PyMCTranslate")
    if PyMCTranslate is None:
        raise unittest.SkipTest(f"PyMCTranslate not available: {err}")

    try:
        from amulet.level.formats.anvil_world import AnvilFormat
    except Exception as exc:
        raise unittest.SkipTest(f"AnvilFormat not available: {exc}")

    try:
        from amulet.api.level import World
    except Exception as exc:
        raise unittest.SkipTest(f"World API not available: {exc}")

    return amulet, PyMCTranslate, AnvilFormat, World


def _create_java_world(path: Path):
    amulet, PyMCTranslate, AnvilFormat, World = _get_world_api()
    translation_manager = PyMCTranslate.new_translation_manager()
    version = _get_latest_version(translation_manager, "java")

    wrapper = AnvilFormat(str(path))
    _call_create_and_open(wrapper, "java", version)
    load_level = getattr(amulet, "load_level", None)
    if load_level is not None:
        save = getattr(wrapper, "save", None)
        if save is not None:
            save()
        close = getattr(wrapper, "close", None)
        if close is not None:
            close()
        world = load_level(str(path))
    else:
        world = World(str(path), wrapper)
    return world, version


def _ensure_chunk(world, dimension, cx, cz):
    get_chunk = getattr(world, "get_chunk")
    signature = inspect.signature(get_chunk)
    if "create" in signature.parameters:
        return get_chunk(cx, cz, dimension, create=True)
    try:
        return get_chunk(cx, cz, dimension)
    except Exception:
        create_chunk = getattr(world, "create_chunk", None)
        if create_chunk is None:
            raise
        create_chunk(cx, cz, dimension)
        return get_chunk(cx, cz, dimension)


def _set_block(world, x, y, z, dimension, block):
    set_block = getattr(world, "set_block", None)
    if set_block is not None:
        try:
            return set_block(x, y, z, dimension, block)
        except TypeError:
            pass
    # Fallback to chunk manipulation
    cx, cz = x // 16, z // 16
    chunk = _ensure_chunk(world, dimension, cx, cz)
    internal_id = world.block_palette.get_add_block(block)
    chunk.blocks[x % 16, y, z % 16] = internal_id
    chunk.changed = True
    return None


def _get_block(world, x, y, z, dimension):
    get_block = getattr(world, "get_block", None)
    if get_block is not None:
        return get_block(x, y, z, dimension)
    cx, cz = x // 16, z // 16
    chunk = _ensure_chunk(world, dimension, cx, cz)
    internal_id = int(chunk.blocks[x % 16, y, z % 16])
    return world.block_palette[internal_id]


class SelectionLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wx, err = _require_module("wx")
        if wx is None:
            raise unittest.SkipTest(f"wx not available: {err}")
        cls.wx = wx
        if wx.App.Get() is None:
            cls.app = wx.App(False)

    def test_selection_manager_roundtrip(self):
        try:
            from amulet.api.selection import SelectionGroup, SelectionBox
            from amulet_map_editor.programs.edit.api.selection import SelectionManager
        except Exception as exc:
            raise unittest.SkipTest(f"Amulet APIs unavailable: {exc}")

        wx = self.wx

        class DummyCanvas(wx.Frame):
            def __init__(self):
                super().__init__(None)
                self.undo_calls = 0

            def create_undo_point(self, world=True, non_world=True):
                self.undo_calls += 1

        canvas = DummyCanvas()
        manager = SelectionManager(canvas)
        manager.set_selection_corners((((1, 2, 3), (4, 5, 6)),))
        self.assertEqual(len(manager.selection_group.selection_boxes), 1)
        box = manager.selection_group.selection_boxes[0]
        self.assertEqual(box.min, (1, 2, 3))
        self.assertEqual(box.max, (4, 5, 6))

        new_group = SelectionGroup([SelectionBox((7, 8, 9), (10, 11, 12))])
        manager.set_selection_group(new_group)
        self.assertEqual(
            tuple(manager.selection_corners),
            (((7, 8, 9), (10, 11, 12)),),
        )


class EditWorkflowTests(unittest.TestCase):
    def test_delete_and_undo_redo(self):
        try:
            from amulet.api.block import Block, UniversalAirBlock
            from amulet.api.selection import SelectionGroup, SelectionBox
            from amulet_map_editor.programs.edit.plugins.operations.stock_plugins.internal_operations.delete import (
                delete,
            )
        except Exception as exc:
            raise unittest.SkipTest(f"Amulet APIs unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            world, _version = _create_java_world(Path(tmp_dir))
            try:
                dimension = next(iter(world.dimensions))
            except Exception:
                dimension = "minecraft:overworld"

            target = (1, 2, 3)
            _set_block(world, *target, dimension, Block("minecraft", "stone"))

            selection = SelectionGroup(
                [SelectionBox(target, (target[0] + 1, target[1] + 1, target[2] + 1))]
            )

            world.create_undo_point()
            for _ in delete(world, dimension, selection):
                pass
            world.create_undo_point()

            self.assertEqual(_get_block(world, *target, dimension), UniversalAirBlock)

            world.undo()
            self.assertEqual(
                _get_block(world, *target, dimension), Block("minecraft", "stone")
            )

            world.redo()
            self.assertEqual(_get_block(world, *target, dimension), UniversalAirBlock)

            close = getattr(world, "close", None)
            if close is not None:
                close()


class ConversionWorkflowTests(unittest.TestCase):
    def test_round_trip_conversion_java(self):
        try:
            from amulet.api.block import Block, UniversalAirBlock
        except Exception as exc:
            raise unittest.SkipTest(f"Amulet APIs unavailable: {exc}")

        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src_world, version = _create_java_world(Path(src_dir))
            dst_wrapper = None
            dst_world = None
            try:
                try:
                    dimension = next(iter(src_world.dimensions))
                except Exception:
                    dimension = "minecraft:overworld"

                target = (2, 3, 4)
                _set_block(src_world, *target, dimension, Block("minecraft", "stone"))

                amulet, PyMCTranslate, AnvilFormat, World = _get_world_api()
                dst_wrapper = AnvilFormat(str(dst_dir))
                _call_create_and_open(dst_wrapper, "java", version)

                save = getattr(src_world, "save", None)
                if save is None:
                    raise unittest.SkipTest("World.save not available")
                try:
                    save(dst_wrapper)
                except TypeError:
                    save(dst_wrapper, None)

                close = getattr(dst_wrapper, "close", None)
                if close is not None:
                    close()
                    dst_wrapper = None

                load_level = getattr(amulet, "load_level", None)
                if load_level is not None:
                    dst_world = load_level(str(dst_dir))
                else:
                    dst_world = World(str(dst_dir), dst_wrapper)
                stone = _get_block(dst_world, *target, dimension)
                self.assertEqual(getattr(stone, "base_name", None), "stone")
                self.assertIn(
                    getattr(stone, "namespace", ""),
                    {"minecraft", "universal_minecraft"},
                )
                self.assertEqual(
                    _get_block(dst_world, 0, 0, 0, dimension), UniversalAirBlock
                )
            finally:
                if dst_wrapper is not None:
                    close = getattr(dst_wrapper, "close", None)
                    if close is not None:
                        close()
                if dst_world is not None:
                    close = getattr(dst_world, "close", None)
                    if close is not None:
                        close()
                close = getattr(src_world, "close", None)
                if close is not None:
                    close()


if __name__ == "__main__":
    unittest.main()
