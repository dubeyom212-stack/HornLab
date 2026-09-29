"""Install the practice reset/instrument update into an existing HornLab folder."""

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile, ZIP_DEFLATED


FILES = (
    "app.py", "coach.py", "instruments.py",
    "static/practice-core.js", "static/practice-room.js",
    "static/workspace.js", "static/workspace.css", "templates/workspace.html",
)
BASE = "https://raw.githubusercontent.com/dubeyom212-stack/HornLab/codex/advanced-practice-workspace/"


def main():
    root = Path.cwd()
    if not (root / "app.py").is_file() or not (root / "templates/workspace.html").is_file():
        raise SystemExit("Open your HornLab app folder first, then run this updater again.")
    pending = {}
    for name in FILES:
        request = Request(BASE + name, headers={"User-Agent": "HornLab-Updater/1.0"})
        with urlopen(request, timeout=30) as response:
            content = response.read(1_000_001)
        if not content or len(content) > 1_000_000:
            raise SystemExit(f"Unexpected download for {name}. No files changed.")
        source = content.decode("utf-8")
        if name.endswith(".py"):
            compile(source, name, "exec")
        pending[name] = content
    previous = {name: (root / name).read_bytes() if (root / name).exists() else None for name in FILES}
    backup_dir = Path.home() / ".config/hornlab/backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / ("practice-source-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".zip")
    with ZipFile(backup, "x", ZIP_DEFLATED) as archive:
        for name, content in previous.items():
            if content is not None:
                archive.writestr(name, content)
    changed = []
    try:
        for name, content in pending.items():
            changed.append(name)
            (root / name).write_bytes(content)
    except OSError:
        for name in changed:
            if previous[name] is None:
                (root / name).unlink(missing_ok=True)
            else:
                (root / name).write_bytes(previous[name])
        raise
    print("Updated practice tools and instrument guidance.")
    print(f"Previous source files saved to {backup}")
    print("Practice data and your Groq key were not changed. Go to Web and click Reload.")


if __name__ == "__main__":
    main()
