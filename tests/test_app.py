from __future__ import annotations

import asyncio
import unittest

from sql_query_mcp.app import create_app


class AppTestCase(unittest.TestCase):
    def test_create_app_registers_import_table_file_tool(self) -> None:
        app = create_app()

        tools = asyncio.run(app.list_tools())

        self.assertIn("import_table_file", {tool.name for tool in tools})

    def test_create_app_registers_async_query_tools(self) -> None:
        app = create_app()

        tools = asyncio.run(app.list_tools())

        tool_names = {tool.name for tool in tools}
        self.assertIn("start_query", tool_names)
        self.assertIn("get_query", tool_names)
        self.assertIn("cancel_query", tool_names)

    def test_create_app_registers_export_query_file_tool(self) -> None:
        app = create_app()

        tools = asyncio.run(app.list_tools())

        self.assertIn("export_query_file", {tool.name for tool in tools})


if __name__ == "__main__":
    unittest.main()
