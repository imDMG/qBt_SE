import json
from pathlib import Path
from tkinter import *
from tkinter import ttk, messagebox


class EngineSettingsGUI:
    def __init__(self, engine_name: str):
        self.config = dict()
        self.cfg_file = Path(engine_name + ".json")
        if self.cfg_file.exists():
            self.config = json.loads(self.cfg_file.read_text())

        self.window = Tk()
        self.window.title(engine_name + " Settings")

        mainframe = ttk.Frame(self.window, padding="10")
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        self.username = StringVar(value=self.config.get('username', ''))
        self.password = StringVar(value=self.config.get('password', ''))
        self.proxy_http = StringVar(
            value=self.config.get('proxies').get('http', '')
        )
        self.proxy_https = StringVar(
            value=self.config.get('proxies').get('https', '')
        )

        self.date = BooleanVar(value=self.config.get('torrentDate', True))
        self.magnet = BooleanVar(value=self.config.get('magnet', False))
        self.proxy = BooleanVar(value=self.config.get('proxy', False))

        ttk.Label(mainframe, text="Username:").grid(column=0, row=0, sticky=W)
        ttk.Label(mainframe, text="Password:").grid(column=0, row=1, sticky=W,
                                                    rowspan=2)

        ttk.Entry(mainframe, width=25, textvariable=self.username).grid(
            column=1, row=0, sticky=(W, E), padx=(0, 5)
        )
        ttk.Entry(mainframe, width=25, textvariable=self.password).grid(
            column=1, row=1, rowspan=2, sticky=(W, E), padx=(0, 5)
        )

        ttk.Checkbutton(
            mainframe, text="Date before torrent", variable=self.date,
            onvalue=True
        ).grid(column=2, row=0, sticky=W)
        ttk.Checkbutton(
            mainframe, text="Use magnet link", variable=self.magnet,
            onvalue=True
        ).grid(column=2, row=1, sticky=W)
        ttk.Checkbutton(
            mainframe, text="Proxy", variable=self.proxy, onvalue=True,
            command=self.proxy_action
        ).grid(column=2, row=2, sticky=W)

        ttk.Label(mainframe, text="HTTP:").grid(column=0, row=3, sticky=W)
        ttk.Label(mainframe, text="HTTPS:").grid(column=0, row=4, sticky=W)

        proxy_state = NORMAL if self.proxy.get() else DISABLED
        self.http_entry = ttk.Entry(
            mainframe, textvariable=self.proxy_http, state=proxy_state
        )
        self.http_entry.grid(column=1, row=3, sticky=(W, E),
                             padx=(0, 5), pady=(0, 5))
        self.https_entry = ttk.Entry(
            mainframe, textvariable=self.proxy_https, state=proxy_state
        )
        self.https_entry.grid(column=1, row=4, sticky=(W, E), padx=(0, 5))

        ttk.Button(
            mainframe, text="Save", command=self.close
        ).grid(column=2, row=3, rowspan=2)

        self.window.mainloop()

    def proxy_action(self):
        state = ("!" if self.proxy.get() else "") + DISABLED
        self.http_entry.state([state])
        self.https_entry.state([state])

    def close(self):
        if not (self.username.get() or self.password.get()):
            messagebox.showinfo('Error', "Some fields is empty!")
            return None

        if self.proxy.get() and not (self.http_entry.get()
                                     or self.https_entry.get()):
            messagebox.showinfo('Error', "Some fields is empty!")
            return None

        self.config['username'] = self.username.get()
        self.config['password'] = self.password.get()
        self.config['proxy'] = self.proxy.get()
        if self.config['proxy']:
            self.config['proxies'] = {
                'http': self.http_entry.get(),
                'https': self.https_entry.get()
            }
        self.config['torrentDate'] = self.date.get()
        self.config['magnet'] = self.magnet.get()
        self.cfg_file.write_text(
            json.dumps(self.config, indent=4, sort_keys=False)
        )
        self.window.destroy()


if __name__ == '__main__':
    settings = EngineSettingsGUI("kinozal")
    print(settings.config)
