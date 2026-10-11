import tkinter as tk
import random
import subprocess
import sys

# ============ 全局配置 ============
THEME = {
    "bar_bg": "#0078D7",        # 蓝条背景
    "bar_fg": "#FFFFFF",        # 蓝条文字
    "bar_hover": "#106EBE",     # 悬停色
    "list_bg": "#FFFFFF",       # 列表背景
    "list_fg": "#000000",       # 列表文字
    "list_hover": "#E5F1FB",    # 列表悬停
    "group_fg": "#0078D7",      # 分组标题色
    "font_bar": ("微软雅黑", 11, "bold"),
    "font_item": ("微软雅黑", 10),
    "font_group": ("微软雅黑", 9, "bold"),
}

_root = None
_windows = {}          # class_name -> window
_init_handlers = {}    # class_name -> init callback


# ============ 基础设施 ============
def get_root():
    global _root
    if _root is None:
        _root = tk.Tk()
        _root.withdraw()
    return _root


def register_init_handler(class_name, handler):
    """注册子窗口初始化回调"""
    _init_handlers[class_name] = handler


# ============ 核心：创建蓝条窗口 ============
class BlueBar:
    def __init__(self, class_name="", width=280, height=48, topmost=True,
                 list_height=200, bg=None, fg=None):
        self.class_name = class_name
        self.bg = bg or THEME["bar_bg"]
        self.fg = fg or THEME["bar_fg"]
        self.topmost = topmost
        self.list_height = list_height
        self.items = []             # 列表项
        self.list_win = None
        self.list_open = False
        self.drag = {"x": 0, "y": 0, "moving": False}

        root = get_root()
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{width}x{height}")
        self.win.configure(bg=self.bg)
        if topmost:
            self.win.attributes('-topmost', True)

        if class_name:
            _windows[class_name] = self

        self.title_label = None
        self._bind_events()

    # ---------- 事件绑定 ----------
    def _bind_events(self):
        w = self.win
        w.bind("<Button-1>", self._on_press)
        w.bind("<B1-Motion>", self._on_drag)
        w.bind("<ButtonRelease-1>", self._on_release)
        w.bind("<Escape>", self._on_escape)
        w.bind("<Destroy>", self._on_destroy)
        w.bind("<Enter>", lambda e: self._set_bar_bg(THEME["bar_hover"]))
        w.bind("<Leave>", lambda e: self._set_bar_bg(self.bg))

    def _set_bar_bg(self, color):
        self.win.configure(bg=color)
        if self.title_label:
            self.title_label.configure(bg=color)

    def _on_press(self, e):
        self.drag["x"] = e.x_root
        self.drag["y"] = e.y_root
        self.drag["moving"] = False

    def _on_drag(self, e):
        dx = e.x_root - self.drag["x"]
        dy = e.y_root - self.drag["y"]
        if abs(dx) > 4 or abs(dy) > 4:
            self.drag["moving"] = True
        if self.drag["moving"]:
            new_x = self.win.winfo_x() + dx
            new_y = self.win.winfo_y() + dy
            self.win.geometry(f"+{new_x}+{new_y}")
            self.drag["x"] = e.x_root
            self.drag["y"] = e.y_root
            self._sync_list_pos()

    def _on_release(self, e):
        if not self.drag["moving"]:
            self.toggle_list()
        self.drag["moving"] = False
        self._sync_list_pos()

    def _on_escape(self, e):
        for w in list(_windows.values()):
            try:
                w.destroy()
            except Exception:
                pass
        _root.quit()

    def _on_destroy(self, e):
        if self.list_win and self.list_win.winfo_exists():
            self.list_win.destroy()
        if self.class_name and _windows.get(self.class_name) is self:
            del _windows[self.class_name]

    # ---------- 标题 ----------
    def set_title(self, text, fg=None, font=None):
        if self.title_label:
            self.title_label.destroy()
        self.title_label = tk.Label(
            self.win, text=text,
            fg=fg or self.fg, bg=self.win.cget("bg"),
            font=font or THEME["font_bar"]
        )
        self.title_label.place(relx=0.5, rely=0.5, anchor='center')
        self.title_label.bind("<Button-1>", self._on_press)
        self.title_label.bind("<B1-Motion>", self._on_drag)
        self.title_label.bind("<ButtonRelease-1>", self._on_release)
        return self.title_label

    # ---------- 列表窗口 ----------
    def _sync_list_pos(self):
        if self.list_win and self.list_win.winfo_exists():
            self.win.update_idletasks()
            x = self.win.winfo_rootx()
            y = self.win.winfo_rooty() + self.win.winfo_height()
            w = self.win.winfo_width()
            h = self.list_win.winfo_height()
            self.list_win.geometry(f"{w}x{h}+{x}+{y}")

    def toggle_list(self):
        if self.list_win and self.list_win.winfo_exists():
            self.list_win.destroy()
            self.list_win = None
            self.list_open = False
        else:
            self._build_list()

    def _build_list(self):
        if self.list_win and self.list_win.winfo_exists():
            self.list_win.destroy()

        self.win.update_idletasks()
        x = self.win.winfo_rootx()
        y = self.win.winfo_rooty() + self.win.winfo_height()
        w = self.win.winfo_width()

        lw = tk.Toplevel(self.win)
        lw.overrideredirect(True)
        lw.geometry(f"{w}x{self.list_height}+{x}+{y}")
        lw.configure(bg=THEME["list_bg"])
        if self.topmost:
            lw.attributes('-topmost', True)

        # 边框感
        border = tk.Frame(lw, bg="#D0D0D0", bd=0)
        border.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        canvas = tk.Canvas(border, bg=THEME["list_bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(border, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=THEME["list_bg"])

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        if not self.items:
            tk.Label(frame, text="（空）", bg=THEME["list_bg"],
                     fg="gray", font=THEME["font_item"]).pack(pady=12)
        else:
            for item in self.items:
                self._render_item(frame, item)

        self.list_win = lw
        self.list_open = True

    def _render_item(self, parent, item):
        if item.startswith("---"):
            # 分组
            text = item[3:].strip()
            tk.Label(parent, text=text, bg=THEME["list_bg"], fg=THEME["group_fg"],
                     font=THEME["font_group"], anchor="w", padx=10, pady=4).pack(fill=tk.X)

        elif item.startswith("###"):
            # 打开子窗口
            parts = item[3:].split("|", 1)
            if len(parts) != 2:
                return
            target, text = parts[0].strip(), parts[1].strip()
            self._make_clickable(parent, text,
                                 lambda: self._toggle_child(target, text))

        elif item.startswith("$$$"):
            # 执行命令
            parts = item[3:].split("|", 1)
            if len(parts) != 2:
                return
            command, text = parts[0].strip(), parts[1].strip()
            self._make_clickable(parent, text, lambda: self._run(command))

        else:
            tk.Label(parent, text=item, bg=THEME["list_bg"], fg=THEME["list_fg"],
                     font=THEME["font_item"], anchor="w", padx=10, pady=3).pack(fill=tk.X)

    def _make_clickable(self, parent, text, callback):
        lbl = tk.Label(parent, text=text, bg=THEME["list_bg"], fg=THEME["list_fg"],
                       font=THEME["font_item"], anchor="w", padx=10, pady=3,
                       cursor="hand2")
        lbl.pack(fill=tk.X)
        lbl.bind("<Button-1>", lambda e: callback())
        lbl.bind("<Enter>", lambda e: lbl.configure(bg=THEME["list_hover"]))
        lbl.bind("<Leave>", lambda e: lbl.configure(bg=THEME["list_bg"]))

    def _toggle_child(self, target, text):
        if target in _windows:
            _windows[target].destroy()
        else:
            child = BlueBar(class_name=target, width=200, height=44)
            child.win.geometry(f"+{random.randint(80, 500)}+{random.randint(80, 400)}")
            child.set_title(text)
            if target in _init_handlers:
                _init_handlers[target](child)

    def _run(self, command):
        try:
            subprocess.Popen(command, shell=True)
        except Exception as e:
            print(f"命令执行失败: {command} -> {e}")

    # ---------- 公共 API ----------
    def add_item(self, text):
        self.items.append(text)
        self._refresh()

    def add_group(self, text):
        self.items.append(f"--- {text}")
        self._refresh()

    def add_child(self, target_class, text):
        self.items.append(f"###{target_class}|{text}")
        self._refresh()

    def add_command(self, name, command):
        self.items.append(f"$$${command}|{name}")
        self._refresh()

    def _refresh(self):
        if self.list_open and self.list_win:
            self.list_win.destroy()
            self.list_win = None
            self.list_open = False
            self.toggle_list()

    def destroy(self):
        self.win.destroy()


# ============ 兼容旧 API 的包装 ============
def create_blue_bar(class_name="", width=200, height=50, topmost=True,
                    list_height=150, bg=None, fg=None):
    bar = BlueBar(class_name=class_name, width=width, height=height,
                  topmost=topmost, list_height=list_height, bg=bg, fg=fg)
    return bar.win


def winz(text, class_name, color="white", font=("Arial", 14)):
    bar = _windows.get(class_name)
    if bar is None:
        print(f"警告：未找到类名为 '{class_name}' 的窗口")
        return
    return bar.set_title(text, fg=color, font=font)


def add_item(class_name, text):
    bar = _windows.get(class_name)
    if bar is None:
        print(f"警告：未找到类名为 '{class_name}' 的窗口")
        return
    bar.add_item(text)


def fenge(class_name, text):
    bar = _windows.get(class_name)
    if bar is None:
        print(f"警告：未找到类名为 '{class_name}' 的窗口")
        return
    bar.add_group(text)


def gongnen(class_name, target_class, text):
    bar = _windows.get(class_name)
    if bar is None:
        print(f"警告：未找到类名为 '{class_name}' 的窗口")
        return
    bar.add_child(target_class, text)


def cmd(class_name, name, command):
    bar = _windows.get(class_name)
    if bar is None:
        print(f"警告：未找到类名为 '{class_name}' 的窗口")
        return
    bar.add_command(name, command)


# ============ 示例 ============
if __name__ == "__main__":
    def init_sub(bar):
        bar.add_group("子菜单")
        bar.add_child("sub2", "打开二级菜单")
        bar.add_item("普通文字")
        bar.add_command("记事本", "notepad")
        bar.add_command("计算器", "calc")

    def init_sub2(bar):
        bar.add_group("二级菜单")
        bar.add_item("这是最里面一层")
        bar.add_command("任务管理器", "taskmgr")

    def init_about(bar):
        bar.add_item("OpenUI v2.0")
        bar.add_item("一个悬浮蓝条菜单框架")

    register_init_handler("sub", init_sub)
    register_init_handler("sub2", init_sub2)
    register_init_handler("about", init_about)

    main = BlueBar(class_name="main", width=320, height=52, list_height=260)
    main.win.geometry("+200+150")
    main.set_title("OpenUI")

    main.add_group("常用功能")
    main.add_child("calc", "打开计算器")
    main.add_child("note", "打开记事本")

    main.add_group("系统命令")
    main.add_command("启动计算器", "calc")
    main.add_command("启动记事本", "notepad")

    main.add_group("其他")
    main.add_child("about", "关于")
    main.add_child("sub", "打开子蓝条")

    tk.mainloop()