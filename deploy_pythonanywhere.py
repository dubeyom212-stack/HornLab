"""Install the tested HornLab source while retaining the host's database/config."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import quote
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED

HERE = Path(tempfile.mkdtemp(prefix="hornlab-accounts-"))
RELEASE = HERE / "release"
MANIFEST = {'commit': '9a0f18ed84dd03d032665b69c6e04baa0cd48842', 'files': {'ACCOUNTS.md': '8815e1ee6fa15ed8eb9c6db858a582a7342941f14a17129e1c5486a0725dd30c', 'AI_SETUP.md': 'b4a580dbfd73cd7761168f32725292b776c7967e3790cf0909f70c975557dd54', 'PILOT.md': 'b3f81d53831a4cb1e97d4aee11012a36206b9f48ab294651708c0b1f3bc274b2', 'README.md': 'f77e5fb1014d91015545eb4ba1c1472c36dd7e8512963434185792a335c6c58e', 'RUN.md': 'f4883e2cee5cc55c49dc36a31a2858dc74f5825b047b13b31e3616cbcc07d657', 'WEB.md': 'c23e1ea1d12485dd2e23b3c11d5cbb1488835bff96807939915e4be230450308', 'accounts.py': '7955eacabad09c6624c358761a356ca4ef6e939562bfc22d0a5f3e430d8c8113', 'app.py': 'e7943aa2626aaed1fdb53720e3ba5241fdce8be8d34a70298dec890c106d0d35', 'coach.py': 'b82f57506cb68b6132d867dfc5c003b2e31e607fb47f49d134d05804428d5b85', 'database.py': 'a8b2fe4a7d577552d9282934237f0bb952ac216a7cf155a8c9116f520634f664', 'instruments.py': '2916093a50924bc4d68e3d0e5c2712857eed5bd79412df5972d356daeaff6cf0', 'requirements.txt': '126f906be17b5573d5a4ea47dcc468d223d4a0a7bde0d3dcc8025155bdb30ff4', 'static/accounts.css': 'ce824e41a4340290e5b3ef10e05e6eb094129ed1d88e033931f72fac4d40cd46', 'static/coach.js': '031aa1a10acbdd6cfee15842593da596b0d29b9c0473d203d6fc8344c9667734', 'static/hornlab-logo.svg': 'a9b50e0477c24b8d2a009b425d5b98a9d71b5fff4b8130a45e1682deca6893d4', 'static/hornlab-mark.svg': 'a3f8420d4ac4c9515e0417361428877cf6ccd068875339aa1c5ae1be50fd609b', 'static/images/field.jpg': '51cd6801de133be94655b47f977454ed25459ac91b4c656c717b3530990ed409', 'static/images/marching.jpg': '79a0061873b5d89e176c6fc67eb2ebcbfe257bd3d81a880f4445e5f71d03aee7', 'static/images/outside-practice.jpeg': 'bea4e0be4c426b586c19ae219ea6a1a31afb0e61b93660e4e29b5d10cead15c2', 'static/metronome.js': 'a7e30cb140cbadf1d1f0490d126b17be9a2cca897cdb3595280aaee5e15f0ce2', 'static/practice-core.js': 'd60c218fb0f73f110f4fcca6c45508fb176492c4d3da1f553449399cddc9d91c', 'static/practice-room.js': '8c610fc6c48e7b931d13b8c64e058eedcc63cfe8aeb7502918f316374146e1a0', 'static/recorder.js': '51751bc4ff4b17789c2a2c851226c2ecf2bb440512c61d0564506b386fbd5308', 'static/style.css': '6832f8c7e613003dac736d493c33a922e33972a7bdce075c2931dc512c4a268d', 'static/workspace.css': '0e7164974d9868cfadaab1e864aa8643109b8d666250390a1c0b775e7def9de5', 'static/workspace.js': 'd7faa282255c93d1534ad753c6b8f74522f6bd1aa4117714fd92aa25b109b9b8', 'templates/_about_content.html': '18c3a683f25033d8788e8e0733de8a901814524e431e6858527974dea2114429', 'templates/about.html': '1a80dbe8ae4065d998ff021628324f7774db4a7e593c2e12234c9663615f1789', 'templates/account.html': '45fb3664f7800c05e5a0a408dd92bc48e3800caf6a98b848358ac2d8c8c2e38e', 'templates/base.html': 'e49f884ac589ddb4bd6c6b3bb149183295ffd71b21e83225ea356aabe75a8127', 'templates/index.html': '59f7dcaf11fe45f170d115e09c8b890d3fb45ff89f8f8813e0dff6eea40ea6f5', 'templates/library.html': 'ba2c5f806de6becbce6943144d0f819bb5c8d882c3528a3f75cf60acc80279f8', 'templates/prepare.html': '4cde28f057b639eb47505929266a94d1c5533222fbaf7d97829c6cf28a4bfff8', 'templates/project.html': '8787393ae5302ffe65a57522d88c0932ad8953db88c14532e003fdcd31d29623', 'templates/setup.html': 'd805d6863e771965fdcdca9620e963e901e799c39c351bd9e0461811315a0725', 'templates/workspace.html': '51e1f05f13d778491f6f2be92ec11f2d1082849f92f35e626f51e9fdb9327a52', 'test_accounts.py': '3a467544e08049f5f050025d83981d73d125dd5d21d74e64ad5a76eb0e79b1ed', 'test_app.py': '1bdf426dd791fa2a60318656c7c9ecc46db0a4b4596b78af18806559f78bf066', 'test_coach.py': 'fe11f7f9077d8d96229a97607ed33e091c4050ade36045df6f36f44060c605a6', 'test_instruments.py': '74e3918fc457186768f436cb5677143dadafcbc3feedbd8592ff05d4c3c928a3', 'test_metronome.cjs': '426d68cf52ce0c07ec36b37817d5c35261e1346e8b978310d126ad3a0740d62f', 'test_practice.cjs': 'dcce5d01f5694e892f2553030887fdc3842b3f943ed5684957758db6ec606939', 'test_tracking.py': '7df787ab478a8fb8011a6e10638e4072dcb258bbb8ed421123c1d743b3b310eb', 'update_practice.py': 'ffe39e210a05de98c0d01c263184c7325844e44af2378c351527c5202b72b8f9'}}
TABLES = ("profile", "practice_item", "practice_session", "practice_goal", "passage", "passage_result", "session_receipt")


def database_path(app):
    from sqlalchemy.engine import make_url
    url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise RuntimeError("Expected the existing site's on-disk SQLite database.")
    path = Path(url.database)
    return path if path.is_absolute() else Path(app.instance_path) / path


def counts(path):
    if not path.exists():
        return {}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        available = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in TABLES if name in available}


def load_site(wsgi):
    namespace = runpy.run_path(str(wsgi))
    app = namespace["application"]
    root = Path(app.root_path).resolve()
    if not (root / "app.py").is_file():
        raise RuntimeError("The WSGI application does not point to the expected HornLab source.")
    return app, root, database_path(app).resolve()


def download_release():
    base = "https://raw.githubusercontent.com/dubeyom212-stack/HornLab/" + MANIFEST["commit"] + "/"
    for number, (name, digest) in enumerate(MANIFEST["files"].items(), 1):
        request = Request(base + quote(name, safe="/"), headers={"User-Agent": "HornLab-Release-Installer/1.0"})
        with urlopen(request, timeout=30) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000 or hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f"Release checksum mismatch: {name}")
        path = RELEASE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if number % 10 == 0 or number == len(MANIFEST["files"]):
            print(f"Downloaded and verified {number}/{len(MANIFEST['files'])} source files.", flush=True)


def verify_release():
    for name, digest in MANIFEST["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] in {"instance", ".env", ".git"}:
            raise RuntimeError("Unexpected path in the source package.")
        if hashlib.sha256((RELEASE / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Release checksum mismatch: {name}")


def stage_tests():
    environment = dict(os.environ)
    environment["HORNLAB_DATABASE_URI"] = "sqlite:///:memory:"
    # The test suite mocks provider calls; no live coaching request is needed.
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-q"], cwd=RELEASE,
                            env=environment, capture_output=True, text=True, timeout=90)
    if result.returncode:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Host tests failed before any live source files were replaced.")
    print(result.stderr.strip(), flush=True)


def validate_live(wsgi):
    code = """
import json,runpy,sys
app=runpy.run_path(sys.argv[1])["application"]
client=app.test_client()
root=client.get("/",base_url="https://hornlab.pythonanywhere.com")
assert root.status_code==302 and root.location.endswith("/login"),"Workspace must require sign-in"
about=client.get("/about",base_url="https://hornlab.pythonanywhere.com")
assert about.status_code==200,"Public About page failed"
assert client.get("/api/profiles").status_code==401,"Anonymous profile access must be rejected"
login=client.get("/login",base_url="https://hornlab.pythonanywhere.com")
assert login.status_code==200,"Sign-in page failed"
cookie=login.headers.get("Set-Cookie","")
assert all(flag in cookie for flag in ("Secure","HttpOnly","SameSite=Lax")),"Session cookie flags failed"
print(json.dumps({"workspace_requires_signin":True,"public_about":True,"anonymous_api_rejected":True,"secure_cookie_flags":True}))
"""
    result = subprocess.run([sys.executable, "-c", code, str(wsgi)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError("Installed source validation failed.")
    return json.loads(result.stdout.strip().splitlines()[-1])


def install(wsgi, backup_base):
    download_release()
    verify_release()
    app, root, database = load_site(wsgi)
    print(json.dumps({"source":str(root),"database":str(database),"release":MANIFEST["commit"],
                      "flask":importlib.metadata.version("Flask"),
                      "flask_sqlalchemy":importlib.metadata.version("Flask-SQLAlchemy")}), flush=True)
    stage_tests()
    stamp = datetime.now(timezone.utc).strftime("accounts-%Y%m%dT%H%M%S-%fZ")
    backup = backup_base / stamp
    backup.mkdir(parents=True, mode=0o700)
    previous = {}
    with ZipFile(backup / "previous-source.zip", "x", ZIP_DEFLATED) as archive:
        for name in MANIFEST["files"]:
            path = root / name
            if root != path.parent.resolve() and root not in path.parent.resolve().parents:
                raise RuntimeError(f"Unexpected linked source directory: {name}")
            previous[name] = path.read_bytes() if path.exists() else None
            if previous[name] is not None:
                archive.writestr(name, previous[name])
    (backup / "previous-source.zip").chmod(0o600)
    shutil.copy2(wsgi, backup / "wsgi.py")
    (backup / "wsgi.py").chmod(0o600)
    if database.exists():
        with sqlite3.connect(str(database)) as source, sqlite3.connect(str(backup / "hornlab.db")) as destination:
            source.backup(destination)
        (backup / "hornlab.db").chmod(0o600)
    before = counts(database)
    changed = []
    try:
        for name in MANIFEST["files"]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".hornlab-next")
            shutil.copyfile(RELEASE / name, temporary)
            os.replace(temporary, path)
            changed.append(name)
        validation = validate_live(wsgi)
        after = counts(database)
        if any(after.get(name, 0) < value for name, value in before.items()):
            raise RuntimeError("Existing practice row counts decreased.")
    except Exception:
        for name in reversed(changed):
            path = root / name
            if previous[name] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous[name])
        raise
    receipt = {"commit":MANIFEST["commit"],"backup":str(backup),"source":str(root),
               "files_updated":len(changed),"before":before,"after":after,"validation":validation}
    (backup / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print("DEPLOYMENT_READY " + json.dumps(receipt), flush=True)
    print("Source and data checks passed. Reload the web app in the Web tab.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wsgi",type=Path,default=Path("/var/www/hornlab_pythonanywhere_com_wsgi.py"))
    parser.add_argument("--backup-dir",type=Path,default=Path.home()/".config/hornlab/backups")
    parser.add_argument("--inspect",action="store_true")
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    if args.inspect:
        app,root,database=load_site(args.wsgi)
        print(json.dumps({"source":str(root),"instance":app.instance_path,"database":str(database),
                          "rows":counts(database),"flask":importlib.metadata.version("Flask"),
                          "flask_sqlalchemy":importlib.metadata.version("Flask-SQLAlchemy")}), flush=True)
    elif args.apply:
        install(args.wsgi,args.backup_dir)
    else:
        parser.error("Choose --inspect or --apply.")


if __name__ == "__main__":
    main()
