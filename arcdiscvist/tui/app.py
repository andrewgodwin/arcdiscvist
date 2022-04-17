import os
import sys
from rich.console import RenderableType

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App
from textual.widgets import Header, Footer, FileClick, ScrollView, DirectoryTree

from ..config import Config
from .widgets.index_tree import IndexTree


class ArcApp(App):
    async def on_load(self) -> None:
        await self.bind("q", "quit", "Quit")

        # Set up config
        self.config = Config()

    async def on_mount(self) -> None:
        self.index_tree = IndexTree(self.config.index)

        # Dock our widgets
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        # Note the directory is also in a scroll view
        await self.view.dock(ScrollView(self.index_tree), edge="top", name="main")
