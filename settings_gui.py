import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any


class EngineSettingsGUI:
    def __init__(self, engine_name: str):
        self.config: dict[str, Any] = {}
        self.cfg_file = Path(engine_name + ".json")
        if self.cfg_file.exists():
            self.config = json.loads(self.cfg_file.read_text())

        self.window = tk.Tk()
        self.window.title(f"{engine_name.capitalize()} Settings")

        mainframe = ttk.Frame(self.window, padding="10")
        mainframe.grid(column=0, row=0, sticky=tk.N)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        self.username = tk.StringVar(value=self.config.get("username", ""))
        self.password = tk.StringVar(value=self.config.get("password", ""))
        self.proxy_http = tk.StringVar(
            value=self.config.get("proxies", {}).get("http", "")
        )
        self.proxy_https = tk.StringVar(
            value=self.config.get("proxies", {}).get("https", "")
        )

        self.date = tk.BooleanVar(value=self.config.get("torrentDate", True))
        self.magnet = tk.BooleanVar(value=self.config.get("magnet", False))
        self.proxy = tk.BooleanVar(value=self.config.get("proxy", False))

        ttk.Label(mainframe, text="Username:").grid(
            column=0, row=0, sticky=tk.W
        )
        ttk.Entry(
            mainframe, width=25, textvariable=self.username
        ).grid(column=1, row=0, sticky=tk.EW, padx=(0, 5))

        ttk.Label(mainframe, text="Password:").grid(
            column=0, row=1, sticky=tk.W
        )
        ttk.Entry(
            mainframe, width=25, textvariable=self.password, show="*"
        ).grid(column=1, row=1, sticky=tk.EW, padx=(0, 5))

        ttk.Checkbutton(
            mainframe, text="Date before torrent", variable=self.date
        ).grid(column=2, row=0, sticky=tk.W)
        ttk.Checkbutton(
            mainframe, text="Use magnet link", variable=self.magnet
        ).grid(column=2, row=1, sticky=tk.W)
        ttk.Checkbutton(
            mainframe,
            text="Proxy",
            variable=self.proxy,
            command=self._toggle_proxy_fields,
        ).grid(column=2, row=2, sticky=tk.W)

        ttk.Label(mainframe, text="HTTP:").grid(column=0, row=3, sticky=tk.W)
        self.http_entry = ttk.Entry(mainframe, textvariable=self.proxy_http)
        self.http_entry.grid(
            column=1, row=3, sticky=tk.EW, padx=(0, 5), pady=(0, 5)
        )

        ttk.Label(mainframe, text="HTTPS:").grid(column=0, row=4, sticky=tk.W)
        self.https_entry = ttk.Entry(mainframe, textvariable=self.proxy_https)
        self.https_entry.grid(column=1, row=4, sticky=tk.EW, padx=(0, 5))

        ttk.Button(mainframe, text="Save", command=self.close).grid(
            column=2, row=3, rowspan=2
        )

        self._toggle_proxy_fields()
        self.window.mainloop()

    def _toggle_proxy_fields(self) -> None:
        state = tk.NORMAL if self.proxy.get() else tk.DISABLED
        self.http_entry.config(state=state)
        self.https_entry.config(state=state)

    def close(self) -> None:
        if (self.username.get() or self.password.get()) and not (
            self.username.get() and self.password.get()
        ):
            messagebox.showerror(
                "Error", "Both username and password must be filled"
            )
            return

        if self.username.get() and self.password.get():
            self.config["username"] = self.username.get()
            self.config["password"] = self.password.get()
        else:
            self.config.pop("username", None)
            self.config.pop("password", None)

        if self.proxy.get():
            if not self.http_entry.get() and not self.https_entry.get():
                messagebox.showerror(
                    "Error", "Fill at least HTTP or HTTPS proxy URL"
                )
                return
            self.config["proxies"] = {
                "http": self.http_entry.get(),
                "https": self.https_entry.get(),
            }
        else:
            self.config.pop("proxies", None)

        self.config["proxy"] = self.proxy.get()
        self.config["torrentDate"] = self.date.get()
        self.config["magnet"] = self.magnet.get()
        self.cfg_file.write_text(json.dumps(self.config, indent=4))

        self.window.destroy()


if __name__ == "__main__":
    settings = EngineSettingsGUI("engines/kinozal")
    print(settings.config)
