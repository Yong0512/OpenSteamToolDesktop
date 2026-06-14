"""
LuaGameManager 单元测试
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game_manager import LuaGameManager, GameInfo


class TestGameInfo(unittest.TestCase):
    """GameInfo 数据类测试"""

    def test_default_values(self):
        gi = GameInfo(app_id="730")
        self.assertEqual(gi.app_id, "730")
        self.assertEqual(gi.name, "")
        self.assertFalse(gi.has_token)
        self.assertFalse(gi.has_manifest)
        self.assertFalse(gi.has_appticket)
        self.assertEqual(gi.lua_path, "")

    def test_custom_values(self):
        gi = GameInfo(
            app_id="730", name="CS2",
            has_token=True, has_manifest=True, has_appticket=True,
            lua_path="/path/to/730.lua",
        )
        self.assertEqual(gi.app_id, "730")
        self.assertEqual(gi.name, "CS2")
        self.assertTrue(gi.has_token)
        self.assertTrue(gi.has_manifest)
        self.assertTrue(gi.has_appticket)
        self.assertEqual(gi.lua_path, "/path/to/730.lua")


class TestLuaGameManager(unittest.TestCase):
    """LuaGameManager 功能测试"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.lua_dir = self._tmpdir.name
        self.gm = LuaGameManager(self.lua_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_initial_empty(self):
        games = self.gm.get_games()
        self.assertEqual(len(games), 0)

    def test_set_lua_dir(self):
        new_dir = os.path.join(self._tmpdir.name, "subdir")
        self.gm.set_lua_dir(new_dir)
        self.assertEqual(self.gm.get_lua_dir(), new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_add_game_creates_file(self):
        ok = self.gm.add_game("730", "CS2")
        self.assertTrue(ok)

        lua_file = os.path.join(self.lua_dir, "730.lua")
        self.assertTrue(os.path.exists(lua_file))

        with open(lua_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("addappid(730)", content)
        self.assertIn("CS2", content)

    def test_add_game_no_name(self):
        self.gm.add_game("440")
        lua_file = os.path.join(self.lua_dir, "440.lua")
        self.assertTrue(os.path.exists(lua_file))

    def test_add_game_with_token(self):
        self.gm.add_game("730", "CS2", token="abc123")
        lua_file = os.path.join(self.lua_dir, "730.lua")
        with open(lua_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('addtoken(730, "abc123")', content)

    def test_add_game_with_depot_data(self):
        """manifest_id 被解析为 depot，生成 addappid 注册"""
        self.gm.add_game("730", "CS2", manifest_id="565660")
        lua_file = os.path.join(self.lua_dir, "730.lua")
        with open(lua_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("addappid(730)", content)

    def test_has_game(self):
        self.assertFalse(self.gm.has_game("730"))
        self.gm.add_game("730", "CS2")
        self.assertTrue(self.gm.has_game("730"))
        self.assertFalse(self.gm.has_game("999"))

    def test_remove_game(self):
        self.gm.add_game("730", "CS2")
        self.assertTrue(self.gm.has_game("730"))

        ok = self.gm.remove_game("730")
        self.assertTrue(ok)
        self.assertFalse(self.gm.has_game("730"))
        self.assertFalse(os.path.exists(os.path.join(self.lua_dir, "730.lua")))

    def test_remove_nonexistent(self):
        ok = self.gm.remove_game("999")
        self.assertTrue(ok)  # idempotent

    def test_get_games(self):
        self.gm.add_game("730", "Counter-Strike 2")
        self.gm.add_game("440", "Team Fortress 2")
        self.gm.add_game("570", "Dota 2")

        games = self.gm.get_games()
        self.assertEqual(len(games), 3)
        app_ids = {g.app_id for g in games}
        self.assertEqual(app_ids, {"730", "440", "570"})

    def test_search_games_by_name(self):
        self.gm.add_game("730", "Counter-Strike 2")
        self.gm.add_game("440", "Team Fortress 2")
        self.gm.add_game("570", "Dota 2")

        results = self.gm.search_games("counter")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].app_id, "730")

    def test_search_games_by_appid(self):
        self.gm.add_game("730", "CS2")
        results = self.gm.search_games("730")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].app_id, "730")

    def test_search_no_match(self):
        self.gm.add_game("730", "CS2")
        results = self.gm.search_games("xyz123")
        self.assertEqual(len(results), 0)

    def test_parse_game_name_from_comment(self):
        lua_file = os.path.join(self.lua_dir, "730.lua")
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write("-- Counter-Strike 2\naddappid(730)\n")

        games = self.gm.get_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].name, "Counter-Strike 2")

    def test_parse_has_token(self):
        lua_file = os.path.join(self.lua_dir, "730.lua")
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write("-- CS2\naddappid(730)\naddtoken(730, \"abc\")\n")

        games = self.gm.get_games()
        self.assertEqual(len(games), 1)
        self.assertTrue(games[0].has_token)

    def test_parse_has_manifest(self):
        lua_file = os.path.join(self.lua_dir, "730.lua")
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write("-- CS2\naddappid(730)\nsetManifestid(480, \"xxx\")\n")

        games = self.gm.get_games()
        self.assertEqual(len(games), 1)
        self.assertTrue(games[0].has_manifest)

    def test_skip_non_digit_files(self):
        # 非数字文件名的 .lua 不应被解析
        lua_file = os.path.join(self.lua_dir, "not_an_appid.lua")
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write("addappid(123)\n")

        games = self.gm.get_games()
        self.assertEqual(len(games), 0)

    def test_refresh_updates_cache(self):
        self.gm.add_game("730", "Old Name")
        games = self.gm.get_games()
        self.assertEqual(games[0].name, "Old Name")

        # 直接修改文件
        lua_file = os.path.join(self.lua_dir, "730.lua")
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write("-- New Name\naddappid(730)\n")

        self.gm.refresh()
        games = self.gm.get_games()
        self.assertEqual(games[0].name, "New Name")

    def test_empty_lua_dir_no_error(self):
        gm = LuaGameManager("")
        games = gm.get_games()
        self.assertEqual(len(games), 0)
        self.assertFalse(gm.has_game("730"))
        self.assertFalse(gm.add_game("730", "CS2"))

    def test_nonexistent_dir_no_error(self):
        gm = LuaGameManager("/nonexistent/path/12345")
        games = gm.get_games()
        self.assertEqual(len(games), 0)


class TestLuaGameManagerCaseInsensitive(unittest.TestCase):
    """大小写不敏感的 Lua 解析测试"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.gm = LuaGameManager(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_case_insensitive_addtoken(self):
        lua_file = os.path.join(self._tmpdir.name, "730.lua")
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write("AddToken(730, \"x\")\naddappid(730)\n")

        games = self.gm.get_games()
        self.assertEqual(len(games), 1)
        self.assertTrue(games[0].has_token)

    def test_case_insensitive_setmanifestid(self):
        lua_file = os.path.join(self._tmpdir.name, "730.lua")
        with open(lua_file, "w", encoding="utf-8") as f:
            f.write("SetManifestID(480, \"x\")\naddappid(730)\n")

        games = self.gm.get_games()
        self.assertEqual(len(games), 1)
        self.assertTrue(games[0].has_manifest)


if __name__ == "__main__":
    unittest.main()
