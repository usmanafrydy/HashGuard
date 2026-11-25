"""HashGuard desktop interface."""

from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from src.baseline_manager import (
    create_baseline,
    load_baseline,
    save_baseline,
    validate_baseline,
)
from src.change_detector import compare_folder_with_baseline
from src.report_formatter import format_report


def save_in_background(folder, destination, results):
    try:
        baseline = create_baseline(folder)
        save_baseline(baseline, destination)
    except Exception as error:
        message = f"Could not save baseline: {error}"
        for note in getattr(error, "__notes__", ()):
            message += f"\n{note}"
        results.put((None, message))
    else:
        results.put((baseline, f"Baseline saved: {destination}"))


def load_in_background(folder, source, results):
    try:
        if folder.is_symlink() or folder.is_junction():
            raise ValueError(
                "Select a folder that is not a symbolic link or junction."
            )

        if source.resolve().is_relative_to(folder.resolve()):
            raise ValueError(
                "Choose a baseline stored outside the monitored folder."
            )

        baseline = load_baseline(source)
        validate_baseline(baseline, selected_folder=folder)
    except Exception as error:
        results.put((None, f"Could not load baseline: {error}"))
    else:
        results.put((baseline, f"Baseline loaded: {source}"))


def compare_in_background(baseline, folder, results):
    """Compare against the active baseline and prepare the text report."""
    try:
        comparison = compare_folder_with_baseline(baseline, folder)
        report = format_report(baseline, comparison)
    except Exception as error:
        results.put((None, f"Could not compare folder: {error}"))
    else:
        results.put((comparison, report))


def build_window(window):
    window.title("HashGuard")
    window.minsize(500, 160)

    panel = ttk.Frame(window, padding=20)
    panel.pack(fill="both", expand=True)

    path_text = tk.StringVar(master=window, value="No folder selected")
    status_text = tk.StringVar(master=window)
    results = SimpleQueue()
    active_baseline = None

    def write_report(text):
        report_box.configure(state="normal")
        report_box.delete("1.0", "end")
        report_box.insert("1.0", text)
        report_box.yview_moveto(0)
        report_box.configure(state="disabled")

    def choose_folder():
        nonlocal active_baseline

        folder = filedialog.askdirectory(
            parent=window,
            title="Choose a folder to monitor",
            mustexist=True,
        )
        if not folder:
            return

        selected = Path(folder)
        if selected != Path(path_text.get()):
            active_baseline = None
            path_text.set(str(selected))
            status_text.set("No active baseline.")
            write_report("")
            compare_button.state(["disabled"])

        create_button.state(["!disabled"])
        load_button.state(["!disabled"])

    def show_baseline_result(baseline, message):
        nonlocal active_baseline
        active_baseline = baseline

        if active_baseline is None:
            message += "\nNo active baseline."
        else:
            state = "Complete" if active_baseline["complete"] else "Incomplete"
            files = active_baseline["files"]
            failures = active_baseline["failed_files"]
            message += (
                f"\n{state} | Files recorded: {len(files)}"
                f" | Errors: {len(failures)}"
            )
            if failures:
                first = failures[0]
                message += f"\nFirst error: {first['path']} - {first['error']}"

        status_text.set(message)

    def show_comparison_result(comparison, report_or_error):
        if comparison is None:
            status_text.set(report_or_error)
            return

        write_report(report_or_error)
        summary = comparison["summary"]
        if (
            not comparison["baseline_complete"]
            or not comparison["current_scan_complete"]
            or summary["unverified"] > 0
        ):
            message = "Verification is incomplete."
        else:
            message = "Comparison finished."
        status_text.set(f"{message} File results: {summary['total']}.")

    def wait_for_result(on_result):
        try:
            value, message = results.get_nowait()
        except Empty:
            window.after(100, wait_for_result, on_result)
            return

        on_result(value, message)
        for button in (choose_button, create_button, load_button):
            button.state(["!disabled"])
        compare_button.state(
            ["!disabled"] if active_baseline is not None else ["disabled"]
        )

    def run_job(target, arguments, progress, on_result):
        write_report("")
        for button in (choose_button, create_button, load_button, compare_button):
            button.state(["disabled"])
        status_text.set(progress)

        try:
            worker = Thread(target=target, args=(*arguments, results))
            worker.start()
        except RuntimeError as error:
            results.put((None, f"Could not start operation: {error}"))

        window.after(100, wait_for_result, on_result)

    def run_baseline_job(target, filename, progress):
        nonlocal active_baseline
        active_baseline = None
        folder = Path(path_text.get())
        run_job(target, (folder, Path(filename)), progress, show_baseline_result)

    def start_baseline():
        folder = Path(path_text.get())

        filename = filedialog.asksaveasfilename(
            parent=window,
            title="Save a new baseline outside the monitored folder",
            initialdir=str(folder.parent),
            initialfile="hashguard-baseline.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            confirmoverwrite=False,
        )
        if not filename:
            return

        run_baseline_job(
            save_in_background,
            filename,
            "Scanning files and saving the baseline...",
        )

    def choose_baseline_file():
        folder = Path(path_text.get())

        filename = filedialog.askopenfilename(
            parent=window,
            title="Load a HashGuard baseline",
            initialdir=str(folder.parent),
            filetypes=[("JSON files", "*.json")],
        )
        if not filename:
            return

        run_baseline_job(
            load_in_background,
            filename,
            "Checking the baseline...",
        )

    def start_comparison():
        if active_baseline is None:
            return

        folder = Path(path_text.get())
        run_job(
            compare_in_background,
            (active_baseline, folder),
            "Comparing files...",
            show_comparison_result,
        )

    ttk.Label(panel, text="Selected folder").pack(anchor="w")

    ttk.Label(
        panel,
        textvariable=path_text,
        wraplength=460,
        justify="left",
    ).pack(anchor="w", pady=(4, 12))

    choose_button = ttk.Button(
        panel,
        text="Choose Folder",
        command=choose_folder,
    )
    choose_button.pack(anchor="w")

    create_button = ttk.Button(
        panel,
        text="Create Baseline",
        command=start_baseline,
        state="disabled",
    )
    create_button.pack(anchor="w", pady=6)

    load_button = ttk.Button(
        panel,
        text="Load Baseline",
        command=choose_baseline_file,
        state="disabled",
    )
    load_button.pack(anchor="w", pady=(0, 6))

    compare_button = ttk.Button(
        panel, text="Compare", command=start_comparison, state="disabled"
    )
    compare_button.pack(anchor="w", pady=(0, 6))

    ttk.Label(
        panel,
        textvariable=status_text,
        wraplength=460,
        justify="left",
    ).pack(anchor="w")

    report_box = ScrolledText(
        panel, wrap="word", width=64, height=12, state="disabled"
    )
    report_box.pack(fill="both", expand=True, pady=(8, 0))


if __name__ == "__main__":
    root = tk.Tk()
    build_window(root)
    root.mainloop()