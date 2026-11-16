"""RTW3 Mod Manager (beta): turns the Rule the Waves 3 mods in Mods/Library on and off and starts the game with them.

Modified from Sprocket Mod Manager 1.4.0 by Hans21223 (https://github.com/Hans21223/Sprocket-Mod-Loader), LGPL-3.0:
see LICENSE. Changed 2026-11-16 for Rule the Waves 3: the window keeps the original's layout, dark theme, error
handling and bundled Python; Sprocket's loader setup, DLL injection, mod import, Decals & Paint and .NET mod report
are removed, every mod action goes through Mods/Manager/mod_loader.py, and updates.py (2026-11-17) offers this
mod's own GitHub releases.

  Mod Manager.exe               the window (the bundled Python opens this file)
  python modman.pyw --selftest  self-check: the window builds, hidden, from the installed mods, then closes
"""
import ctypes, json, subprocess, sys, tempfile, traceback
from pathlib import Path

HOME = Path(__file__).resolve().parent
GAME = HOME.parent.parent           # this folder is <game>/Mods/ModManager
LOADER = GAME / "Mods" / "Manager" / "mod_loader.py"


def loader(*args):
    """mod_loader.py's JSON answer to one command; what it refuses comes back as the error."""
    run = subprocess.run([sys.executable, str(LOADER), *args], cwd=GAME, capture_output=True, text=True,
                         errors="replace", creationflags=subprocess.CREATE_NO_WINDOW, timeout=600)
    try:
        answer = json.loads(run.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        raise RuntimeError((run.stderr or run.stdout).strip() or "The mod loader stopped without an answer.")
    if not answer.get("ok"):
        raise RuntimeError(answer.get("message") or "The mod loader refused.")
    return answer


def guarded(fn, then=None):
    """Tk callback that shows errors in a dialog instead of dying silently, then runs `then`."""
    def run(*_):
        from tkinter import messagebox
        try:
            fn()
        except Exception as e:
            messagebox.showerror("Mod Manager", str(e))
        if then:
            then()
    return run


def dark(win):
    """Dark colours for every Tk/ttk widget made after this call, plus a dark Windows title bar."""
    from tkinter import ttk
    bg, field, fg, sel, line = "#1e1f22", "#2b2d30", "#dfe1e5", "#2f65ca", "#43454a"
    for pattern, value in [("*Background", bg), ("*Foreground", fg), ("*Entry.Background", field),
                           ("*Listbox.Background", field), ("*selectBackground", sel), ("*selectForeground", "white"),
                           ("*insertBackground", fg), ("*activeBackground", line), ("*activeForeground", fg),
                           ("*highlightBackground", bg), ("*TCombobox*Listbox.Background", field)]:
        win.option_add(pattern, value)
    win.configure(bg=bg)
    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor=line, darkcolor=bg,
                    lightcolor=bg, troughcolor=bg, arrowcolor=fg, selectbackground=sel, selectforeground="white")
    style.map(".", background=[("disabled", bg)], foreground=[("disabled", "#80848b")])
    style.configure("TButton", background=field, padding=(10, 4))
    style.map("TButton", background=[("pressed", sel), ("active", line)])
    style.configure("TScrollbar", background=line, troughcolor=bg, bordercolor=bg)
    try:  # DWMWA_USE_IMMERSIVE_DARK_MODE (Windows 10 2004+)
        win.update_idletasks()
        ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.windll.user32.GetParent(win.winfo_id()), 20,
                                                   ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass


def gui(hidden=False):
    import tkinter as tk
    from tkinter import messagebox, ttk
    import updates

    mods, enabled, working = {}, [], False

    def show(answer):
        """The list from a mod_loader answer: its status, or the status an action returns."""
        state = answer.get("status", answer)
        mods.clear()
        mods.update((m["id"], m) for m in state["mods"])
        enabled[:] = state["enabled"]
        picked = box.curselection()
        box.delete(0, "end")
        for m in mods.values():
            box.insert("end", f"[{'x' if m['id'] in enabled else ' '}] {m['name']}")
        if picked:
            box.selection_set(picked[0])
        details()

    def selected():
        if not box.curselection():
            raise RuntimeError("Select a mod first")
        return list(mods.values())[box.curselection()[0]]

    def details(*_):
        text.configure(state="normal")
        text.delete("1.0", "end")
        if box.curselection():
            m = selected()
            needs = ", ".join(mods[i]["name"] if i in mods else i for i in m.get("requires", []))
            text.insert("1.0", f"{m['name']} {m['version']}" + ("  (experimental)" if m.get("experimental") else "")
                        + (f"\nNeeds: {needs}" if needs else "") + "\n\n" + m["description"])
        text.configure(state="disabled")

    def busy(message, work, done):
        """work() on a worker thread with the buttons off; then done(its answer), or its error shown."""
        import queue, threading
        nonlocal working
        working, answers = True, queue.Queue()
        for control in bottom.winfo_children():
            control.configure(state="disabled")
        status["text"] = message

        def worker():
            try:
                answers.put((True, work()))
            except Exception as error:
                answers.put((False, error))

        def poll():
            nonlocal working
            if answers.empty():
                return win.after(100, poll)
            ok, value = answers.get()
            working = False
            win.attributes("-topmost", False)
            for control in bottom.winfo_children():
                control.configure(state="normal")
            if ok:
                return done(value)
            if hidden:
                raise SystemExit(f"selftest failed: {value}")
            text = str(value)
            if "before loading a campaign" in text:   # a mod's title-screen guard: a campaign opened mid-launch
                text = ("A campaign was started or loaded before every mod had finished loading, so the mods stopped "
                        "to protect it.\n\nClose Rule the Waves 3 without saving, click Launch again, and wait until "
                        "this window says the mods are loaded.")
            status["text"] = text.splitlines()[0]
            messagebox.showerror("Mod Manager", text)

        threading.Thread(target=worker, daemon=True).start()
        win.after(100, poll)

    def apply(want, message):
        busy(message, lambda: loader("apply", "--enabled", ",".join(want)),
             lambda answer: (show(answer), status.configure(text=answer["message"])))

    def toggle():
        if working:
            return
        m = selected()
        if m["id"] in enabled:
            apply([i for i in enabled if i != m["id"]], f"Turning off {m['name']}...")
        elif not m.get("experimental") or messagebox.askyesno("Experimental mod", f"{m['name']} is experimental. "
                "Play it in a separate test campaign and keep copies of saves you care about.\n\nTurn it on?"):
            apply(enabled + [m["id"]], f"Turning on {m['name']}...")

    def disable_all():
        if enabled and messagebox.askyesno("Disable all", "Turn every mod off and put the game's original files back?"):
            apply([], "Turning every mod off...")

    def launch():
        win.attributes("-topmost", True)   # stays over the game's title screen, where the wait message is needed
        busy("Loading the mods into the game. Don't start or load a campaign until this line says they're loaded.",
             lambda: loader("launch", "--accept-experimental"),
             lambda answer: status.configure(text="Mods loaded: you can start or load a campaign now."))

    def started(answer):
        show(answer)
        status["text"] = "Double-click a mod to turn it on or off. Close the game first."
        if hidden:
            print(f"selftest ok: {box.size()} mods listed, {len(enabled)} on")
            return win.destroy()
        check_updates()

    def check_updates():
        """A newer release on GitHub, offered once a start; offline or GitHub busy: just said on the status line."""
        import queue, threading
        results = queue.Queue()

        def worker():
            try:
                results.put(updates.check())
            except Exception as error:
                results.put(error)

        def poll():
            if results.empty():
                return win.after(250, poll)
            found = results.get()
            if isinstance(found, Exception):
                status["text"] = f"Couldn't check for updates: {found}"
            elif found and not working and messagebox.askyesno("Update", f"RTW3 mods {found[0]} is available (you "
                    f"have {updates.VERSION}).\n\n{found[3][:800]}\n\nUpdate now? Close the game first."):
                update(found)

        threading.Thread(target=worker, daemon=True).start()
        win.after(250, poll)

    def update(found):
        def work():
            state = loader("status")
            if state["running"]:
                raise RuntimeError("Close Rule the Waves 3 first, then open the Mod Manager again to update.")
            updates.install(updates.download(found[1], found[2]), GAME)
            keep = [i for i in state["enabled"] if (GAME / "Mods" / "Library" / i / "mod.json").is_file()]
            try:   # the mods that were on, in their new versions
                loader("apply", "--enabled", ",".join(keep))
            except RuntimeError as error:
                return f"Updated to {found[0]}, but the mods couldn't be turned back on: {error}"

        def done(problem):
            if problem:
                messagebox.showwarning("Update", problem)
            subprocess.Popen([sys.executable, str(HOME / "modman.pyw")])   # the new manager
            win.destroy()

        busy(f"Updating to {found[0]}...", work, done)

    def close():
        if working:
            messagebox.showinfo("Mod Manager", "Wait for the mod manager to finish before closing it.")
        else:
            win.destroy()

    win = tk.Tk()
    if hidden:
        win.withdraw()
    # An error in a button no guarded() wraps would otherwise only reach the (invisible) console.
    win.report_callback_exception = lambda *error: stopped("".join(traceback.format_exception(*error)))
    win.title(f"RTW3 Mod Manager {updates.VERSION}")
    win.protocol("WM_DELETE_WINDOW", close)
    dark(win)
    box = tk.Listbox(win, width=64, height=16, activestyle="none", font=("Consolas", 10), exportselection=False)
    box.pack(fill="both", expand=True, padx=8, pady=(8, 0))
    box.bind("<Double-1>", guarded(toggle))
    box.bind("<<ListboxSelect>>", details)
    text = tk.Text(win, height=10, wrap="word", font=("Segoe UI", 9), relief="flat", state="disabled")
    text.pack(fill="x", padx=8, pady=(6, 0))
    bottom = ttk.Frame(win)
    bottom.pack(fill="x", padx=8, pady=6)
    for label, fn in [("Enable / Disable", toggle), ("Disable all", disable_all), ("Launch", launch)]:
        ttk.Button(bottom, text=label, command=guarded(fn)).pack(side="left", padx=(0, 6))
    status = ttk.Label(win, text="Double-click a mod to turn it on or off. Close the game first.")
    status.pack(fill="x", padx=8, pady=(0, 6))
    busy("Reading the mods...", lambda: loader("bootstrap"), started)   # the first start records the game's build
    win.mainloop()


# Double-clicked, modman.pyw has no console: anything that stops it must be said in a box, or it just seems not to open.

def startup_problem():
    """Why the window can't open, said so a player can fix it, or None."""
    if not (GAME / "RTW3.exe").is_file() or not LOADER.is_file():
        return ("The Mods folder isn't in the Rule the Waves 3 game folder.\n\n"
                "In Steam, right-click Rule the Waves 3 > Manage > Browse local files, extract the whole ZIP there so "
                "the Mods folder sits next to RTW3.exe, then open Mods\\ModManager\\Mod Manager.exe.")
    try:
        import tkinter  # noqa: F401  (the window)
    except ImportError:
        return "This Python has no Tkinter, the part that draws windows. Open Mod Manager.exe instead."
    return None


def fail(text):
    """Windows' own message box: it works even when Tkinter is what's missing."""
    try:
        ctypes.windll.user32.MessageBoxW(None, text, "Mod Manager", 0x10)  # MB_ICONERROR
    except Exception:
        print(text)


def crash_log(details, folders=None):
    """The full error in modman-error.log (next to the manager, or in Temp if that folder can't be written): its path."""
    for folder in folders or [HOME, Path(tempfile.gettempdir())]:
        try:
            path = folder / "modman-error.log"
            path.write_text(details, encoding="utf-8")
            return path
        except OSError:
            continue
    return None


def stopped(details):
    """An error nothing else caught: saved and shown, never silent."""
    log = crash_log(details)
    fail("The Mod Manager hit an error:\n\n" + details.strip().splitlines()[-1]
         + (f"\n\nThe details are saved in {log}. Send that file when you ask for help." if log else ""))


if __name__ == "__main__":
    hidden = "--selftest" in sys.argv
    problem = startup_problem()
    if problem:
        print(problem) if hidden else fail(problem)
        sys.exit(1)
    try:
        gui(hidden)
    except Exception:
        if hidden:
            traceback.print_exc()
        else:
            stopped(traceback.format_exc())
        sys.exit(1)
