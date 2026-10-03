"""An in-memory file system simulator built from a tree of Python objects.

Run with ``python filesystem_simulator.py`` and enter ``help`` to see commands.
All directories and files exist only in this simulator; your real disk is not
changed.
"""

from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass, field


class FileSystemError(Exception):
    """An error caused by an invalid simulated file-system operation."""


@dataclass
class Node:
    name: str
    parent: Directory | None = field(default=None, repr=False)


@dataclass
class File(Node):
    content: str = ""


@dataclass
class Directory(Node):
    children: dict[str, Node] = field(default_factory=dict)


class FileSystem:
    """A hierarchical file system whose directories form a tree."""

    def __init__(self) -> None:
        self.root = Directory(name="/")
        self.cwd = self.root

    @staticmethod
    def _parts(path: str) -> list[str]:
        return [part for part in path.split("/") if part]

    def resolve(self, path: str) -> Node:
        """Resolve an absolute or current-directory-relative path."""
        if not path or path == ".":
            return self.cwd

        node: Node = self.root if path.startswith("/") else self.cwd
        for part in self._parts(path):
            if part == ".":
                continue
            if part == "..":
                if isinstance(node, Directory) and node.parent is not None:
                    node = node.parent
                continue
            if not isinstance(node, Directory):
                raise FileSystemError(f"'{node.name}' is not a directory")
            child = node.children.get(part)
            if child is None:
                raise FileSystemError(f"path not found: {path}")
            node = child
        return node

    def _resolve_parent(self, path: str) -> tuple[Directory, str]:
        parts = self._parts(path)
        if not parts or parts[-1] in {".", ".."}:
            raise FileSystemError("a file or directory name is required")
        name = parts[-1]
        parent_path = "/".join(parts[:-1])
        if path.startswith("/"):
            parent_path = "/" + parent_path
        parent = self.resolve(parent_path or ("/" if path.startswith("/") else "."))
        if not isinstance(parent, Directory):
            raise FileSystemError("parent path is not a directory")
        return parent, name

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name or name in {".", ".."} or "/" in name:
            raise FileSystemError(f"invalid name: {name!r}")

    def pwd(self) -> str:
        if self.cwd is self.root:
            return "/"
        names: list[str] = []
        node: Directory | None = self.cwd
        while node is not None and node is not self.root:
            names.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(names))

    def path_of(self, node: Node) -> str:
        """Return a node's absolute path."""
        if node is self.root:
            return "/"
        names: list[str] = []
        current: Node | None = node
        while current is not None and current is not self.root:
            names.append(current.name)
            current = current.parent
        return "/" + "/".join(reversed(names))

    def ls(self, path: str = ".") -> list[str]:
        node = self.resolve(path)
        if isinstance(node, File):
            return [node.name]
        return [
            child.name + ("/" if isinstance(child, Directory) else "")
            for child in sorted(node.children.values(), key=lambda item: item.name.lower())
        ]

    def cd(self, path: str = "/") -> None:
        node = self.resolve(path)
        if not isinstance(node, Directory):
            raise FileSystemError(f"not a directory: {path}")
        self.cwd = node

    def mkdir(self, path: str, parents: bool = False) -> None:
        if not parents:
            parent, name = self._resolve_parent(path)
            self._validate_name(name)
            if name in parent.children:
                raise FileSystemError(f"already exists: {path}")
            parent.children[name] = Directory(name=name, parent=parent)
            return

        node = self.root if path.startswith("/") else self.cwd
        for part in self._parts(path):
            if part == ".":
                continue
            if part == "..":
                if node.parent is not None:
                    node = node.parent
                continue
            if not isinstance(node, Directory):
                raise FileSystemError(f"'{node.name}' is not a directory")
            child = node.children.get(part)
            if child is None:
                child = Directory(name=part, parent=node)
                node.children[part] = child
            elif not isinstance(child, Directory):
                raise FileSystemError(f"a file already exists at: {part}")
            node = child

    def touch(self, path: str) -> None:
        parent, name = self._resolve_parent(path)
        self._validate_name(name)
        existing = parent.children.get(name)
        if existing is None:
            parent.children[name] = File(name=name, parent=parent)
        elif isinstance(existing, Directory):
            raise FileSystemError(f"a directory already exists at: {path}")

    def write(self, path: str, text: str, append: bool = False) -> None:
        parent, name = self._resolve_parent(path)
        self._validate_name(name)
        node = parent.children.get(name)
        if node is None:
            node = File(name=name, parent=parent)
            parent.children[name] = node
        if isinstance(node, Directory):
            raise FileSystemError(f"is a directory: {path}")
        node.content = node.content + text if append else text

    def cat(self, path: str) -> str:
        node = self.resolve(path)
        if isinstance(node, Directory):
            raise FileSystemError(f"is a directory: {path}")
        return node.content

    def rm(self, path: str, recursive: bool = False) -> None:
        node = self.resolve(path)
        if node is self.root:
            raise FileSystemError("the root directory cannot be removed")
        if isinstance(node, Directory) and node.children and not recursive:
            raise FileSystemError(f"directory is not empty: {path} (use rm -r)")
        if isinstance(node, Directory) and self._is_inside(self.cwd, node):
            raise FileSystemError("cannot remove the current directory or one of its parents")
        assert node.parent is not None
        del node.parent.children[node.name]

    @staticmethod
    def _is_inside(node: Directory, ancestor: Directory) -> bool:
        current: Directory | None = node
        while current is not None:
            if current is ancestor:
                return True
            current = current.parent
        return False

    def tree(self, path: str = ".") -> str:
        start = self.resolve(path)
        lines = [start.name + ("/" if isinstance(start, Directory) else "")]

        def visit(directory: Directory, prefix: str) -> None:
            children = sorted(directory.children.values(), key=lambda item: item.name.lower())
            for index, child in enumerate(children):
                last = index == len(children) - 1
                branch = "└── " if last else "├── "
                label = child.name + ("/" if isinstance(child, Directory) else "")
                lines.append(prefix + branch + label)
                if isinstance(child, Directory):
                    visit(child, prefix + ("    " if last else "│   "))

        if isinstance(start, Directory):
            visit(start, "")
        return "\n".join(lines)


HELP = """Commands:
  help                       Show this help
  pwd                        Show the current directory
  ls [path]                  List a directory (or show a file name)
  tree [path]                Display a directory tree
  cd [path]                  Change directory (default: /)
  mkdir [-p] path            Create a directory; -p also creates parents
  touch path                 Create an empty file
  write path text            Create or replace a file's contents
  append path text           Add text to a file
  cat path                   Show a file's contents
  rm [-r] path               Remove a file or an empty directory; -r is recursive
  exit                       Quit the simulator

Paths may be absolute (starting with /) or relative to the current directory.
Quote names or text containing spaces, for example: write notes.txt "hello there"
"""


def run() -> None:
    fs = FileSystem()
    print("Python Tree File System Simulator")
    print("Type 'help' for commands. This simulator does not change your real files.")

    while True:
        try:
            raw = input(f"{fs.pwd()} $ ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        try:
            args = shlex.split(raw)
        except ValueError as error:
            print(f"Error: {error}")
            continue
        if not args:
            continue

        command, *rest = args
        try:
            if command == "help":
                print(HELP)
            elif command == "pwd":
                print(fs.pwd())
            elif command == "ls":
                if len(rest) > 1:
                    raise FileSystemError("usage: ls [path]")
                print("  ".join(fs.ls(rest[0] if rest else ".")))
            elif command == "tree":
                if len(rest) > 1:
                    raise FileSystemError("usage: tree [path]")
                print(fs.tree(rest[0] if rest else "."))
            elif command == "cd":
                if len(rest) > 1:
                    raise FileSystemError("usage: cd [path]")
                fs.cd(rest[0] if rest else "/")
            elif command == "mkdir":
                parents = bool(rest and rest[0] == "-p")
                path_args = rest[1:] if parents else rest
                if len(path_args) != 1:
                    raise FileSystemError("usage: mkdir [-p] path")
                fs.mkdir(path_args[0], parents=parents)
            elif command == "touch":
                if len(rest) != 1:
                    raise FileSystemError("usage: touch path")
                fs.touch(rest[0])
            elif command in {"write", "append"}:
                if len(rest) < 2:
                    raise FileSystemError(f"usage: {command} path text")
                fs.write(rest[0], " ".join(rest[1:]), append=command == "append")
            elif command == "cat":
                if len(rest) != 1:
                    raise FileSystemError("usage: cat path")
                print(fs.cat(rest[0]))
            elif command == "rm":
                recursive = bool(rest and rest[0] == "-r")
                path_args = rest[1:] if recursive else rest
                if len(path_args) != 1:
                    raise FileSystemError("usage: rm [-r] path")
                fs.rm(path_args[0], recursive=recursive)
            elif command in {"exit", "quit"}:
                print("Goodbye!")
                break
            else:
                print(f"Unknown command: {command}. Type 'help' for commands.")
        except FileSystemError as error:
            print(f"Error: {error}")


def run_gui() -> None:
    """Launch a graphical interface for the in-memory file system."""
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk

    fs = FileSystem()
    window = tk.Tk()
    window.title("Python Tree File System Simulator")
    window.geometry("900x580")
    window.minsize(680, 420)

    style = ttk.Style(window)
    if "vista" in style.theme_names():
        style.theme_use("vista")

    toolbar = ttk.Frame(window, padding=(12, 10, 12, 6))
    toolbar.pack(fill="x")
    ttk.Label(toolbar, text="Path").pack(side="left", padx=(0, 8))
    path_var = tk.StringVar(value="/")
    path_entry = ttk.Entry(toolbar, textvariable=path_var)
    path_entry.pack(side="left", fill="x", expand=True)

    body = ttk.Panedwindow(window, orient="horizontal")
    body.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    tree_frame = ttk.Frame(body, padding=(0, 4, 8, 0))
    editor_frame = ttk.Frame(body, padding=(8, 4, 0, 0))
    body.add(tree_frame, weight=1)
    body.add(editor_frame, weight=3)

    ttk.Label(tree_frame, text="Folders and files").pack(anchor="w", pady=(0, 6))
    tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
    tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=tree_scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    tree_scroll.pack(side="right", fill="y")

    ttk.Label(editor_frame, text="File contents").pack(anchor="w", pady=(0, 6))
    editor_wrap = ttk.Frame(editor_frame)
    editor_wrap.pack(fill="both", expand=True)
    editor = tk.Text(editor_wrap, wrap="word", undo=True, font=("Consolas", 10), padx=10, pady=8)
    editor_scroll = ttk.Scrollbar(editor_wrap, orient="vertical", command=editor.yview)
    editor.configure(yscrollcommand=editor_scroll.set)
    editor.pack(side="left", fill="both", expand=True)
    editor_scroll.pack(side="right", fill="y")

    status_var = tk.StringVar(value="All changes are stored in memory for this session.")
    ttk.Label(window, textvariable=status_var, anchor="w", padding=(12, 4)).pack(fill="x")

    selected: Node = fs.root
    current_directory: Directory = fs.root
    node_iids: dict[int, str] = {}
    iid_nodes: dict[str, Node] = {}
    next_iid = 0
    loading_editor = False

    def set_editor_enabled(enabled: bool) -> None:
        editor.configure(state="normal" if enabled else "disabled")
        save_button.configure(state="normal" if enabled else "disabled")

    def show_node(node: Node) -> None:
        nonlocal selected, current_directory, loading_editor
        selected = node
        current_directory = node if isinstance(node, Directory) else (node.parent or fs.root)
        path_var.set(fs.path_of(node))
        loading_editor = True
        editor.configure(state="normal")
        editor.delete("1.0", "end")
        if isinstance(node, File):
            editor.insert("1.0", node.content)
            set_editor_enabled(True)
            status_var.set(f"File: {fs.path_of(node)}")
        else:
            set_editor_enabled(False)
            status_var.set(f"Folder: {fs.path_of(node)}")
        loading_editor = False

    def refresh(select_node: Node | None = None) -> None:
        nonlocal next_iid
        tree.delete(*tree.get_children())
        node_iids.clear()
        iid_nodes.clear()
        next_iid = 0

        def add_node(node: Node, parent_iid: str = "") -> str:
            nonlocal next_iid
            next_iid += 1
            iid = f"node-{next_iid}"
            label = node.name + ("/" if isinstance(node, Directory) and node is not fs.root else "")
            tree.insert(parent_iid, "end", iid=iid, text=label, open=node is fs.root)
            node_iids[id(node)] = iid
            iid_nodes[iid] = node
            if isinstance(node, Directory):
                for child in sorted(node.children.values(), key=lambda item: (isinstance(item, File), item.name.lower())):
                    add_node(child, iid)
            return iid

        root_iid = add_node(fs.root)
        target = select_node or selected
        target_iid = node_iids.get(id(target), root_iid)
        tree.selection_set(target_iid)
        tree.focus(target_iid)
        tree.see(target_iid)
        show_node(target)

    def save_file() -> None:
        if not isinstance(selected, File):
            return
        selected.content = editor.get("1.0", "end-1c")
        status_var.set(f"Saved: {fs.path_of(selected)}")

    def on_tree_select(_event: object = None) -> None:
        chosen = tree.selection()
        if chosen and chosen[0] in iid_nodes:
            show_node(iid_nodes[chosen[0]])

    def go_to_path(_event: object = None) -> None:
        try:
            target = fs.resolve(path_var.get().strip() or "/")
            refresh(target)
        except FileSystemError as error:
            messagebox.showerror("Path not found", str(error), parent=window)
            path_var.set(fs.path_of(selected))

    def create_folder() -> None:
        name = simpledialog.askstring("New folder", "Folder name:", parent=window)
        if name is None:
            return
        try:
            path = fs.path_of(current_directory).rstrip("/") + "/" + name
            fs.mkdir(path or "/" + name)
            created = fs.resolve(path or "/" + name)
            refresh(created)
        except FileSystemError as error:
            messagebox.showerror("Could not create folder", str(error), parent=window)

    def create_file() -> None:
        name = simpledialog.askstring("New file", "File name:", parent=window)
        if name is None:
            return
        try:
            path = fs.path_of(current_directory).rstrip("/") + "/" + name
            fs.touch(path or "/" + name)
            created = fs.resolve(path or "/" + name)
            refresh(created)
            editor.focus_set()
        except FileSystemError as error:
            messagebox.showerror("Could not create file", str(error), parent=window)

    def delete_selected() -> None:
        if selected is fs.root:
            messagebox.showinfo("Delete", "The root folder cannot be deleted.", parent=window)
            return
        target = selected
        target_path = fs.path_of(target)
        recursive = isinstance(target, Directory) and bool(target.children)
        prompt = f"Delete '{target_path}'?"
        if recursive:
            prompt += "\n\nThis also deletes everything inside the folder."
        if not messagebox.askyesno("Confirm delete", prompt, parent=window):
            return
        try:
            fs.rm(target_path, recursive=recursive)
            parent = target.parent or fs.root
            refresh(parent)
        except FileSystemError as error:
            messagebox.showerror("Could not delete", str(error), parent=window)

    tree.bind("<<TreeviewSelect>>", on_tree_select)
    path_entry.bind("<Return>", go_to_path)

    ttk.Button(toolbar, text="Go", command=go_to_path).pack(side="left", padx=(8, 0))
    actions = ttk.Frame(tree_frame)
    actions.pack(side="bottom", fill="x", pady=(8, 0))
    ttk.Button(actions, text="New Folder", command=create_folder).pack(fill="x", pady=2)
    ttk.Button(actions, text="New File", command=create_file).pack(fill="x", pady=2)
    ttk.Button(actions, text="Delete", command=delete_selected).pack(fill="x", pady=2)

    editor_actions = ttk.Frame(editor_frame)
    editor_actions.pack(fill="x", pady=(8, 0))
    save_button = ttk.Button(editor_actions, text="Save File", command=save_file)
    save_button.pack(side="right")

    refresh(fs.root)
    window.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv[1:]:
        run()
    else:
        run_gui()
