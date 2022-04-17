from dataclasses import dataclass
from typing import List
from functools import lru_cache

from rich.console import RenderableType
from rich.text import Text
from textual.events import Mount
from textual.reactive import Reactive
from textual.widgets import TreeControl, TreeClick, TreeNode, NodeID

from ...index import Index


@dataclass
class IndexEntry:
    path: str
    directory: bool


class IndexTree(TreeControl[IndexEntry]):

    has_focus: Reactive[bool] = Reactive(False)

    def __init__(self, index: Index) -> None:
        self.index = index
        super().__init__(label="Index", data=IndexEntry(path="", directory=True))

    has_focus: Reactive[bool] = Reactive(False)

    def on_focus(self) -> None:
        self.has_focus = True

    def on_blur(self) -> None:
        self.has_focus = False

    async def watch_hover_node(self, hover_node: NodeID) -> None:
        for node in self.nodes.values():
            node.tree.guide_style = (
                "bold not dim red" if node.id == hover_node else "black"
            )
        self.refresh(layout=True)

    def render_node(self, node: TreeNode[IndexEntry]) -> RenderableType:
        return self.render_tree_label(
            node,
            node.data.directory,
            node.expanded,
            node.is_cursor,
            node.id == self.hover_node,
        )

    @lru_cache(maxsize=1024 * 32)
    def render_tree_label(
        self,
        node: TreeNode[IndexEntry],
        directory: bool,
        expanded: bool,
        is_cursor: bool,
        is_hover: bool,
    ) -> RenderableType:
        meta = {
            "@click": f"click_label({node.id})",
            "tree_node": node.id,
            "cursor": node.is_cursor,
        }
        label = Text(node.label) if isinstance(node.label, str) else node.label
        if is_hover:
            label.stylize("underline")
        if directory:
            label.stylize("bold magenta")
            icon = "📂" if expanded else "📁"
        else:
            label.stylize("bright_green")
            icon = "📄"
            label.highlight_regex(r"\..*$", "green")

        if label.plain.startswith("."):
            label.stylize("dim")

        icon_label = Text(f"{icon} ", no_wrap=True, overflow="ellipsis") + label
        icon_label.apply_meta(meta)
        return icon_label

    async def on_mount(self, event: Mount) -> None:
        await self.load_directory(self.root)

    async def load_directory(self, node: TreeNode[IndexEntry]):
        path = node.data.path
        directory = sorted(self.index.contents(path).items())
        for name, details in directory:
            self.log(name, details)
            await node.add(name, IndexEntry(details.path, details.directory))
        node.loaded = True
        await node.expand()
        self.refresh(layout=True)

    async def handle_tree_click(self, message: TreeClick[IndexEntry]) -> None:
        dir_entry = message.node.data
        if not dir_entry.directory:
            pass  # await self.emit(FileClick(self, dir_entry.path))
        else:
            if not message.node.loaded:
                await self.load_directory(message.node)
                await message.node.expand()
            else:
                await message.node.toggle()
