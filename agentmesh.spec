# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve().parent

datas = []
for source, target in [
    ("frontend/dist", "frontend/dist"),
    ("agentmesh/skills", "agentmesh/skills"),
    ("config-template.yaml", "."),
]:
    source_path = project_root / source
    if source_path.exists():
        datas.append((str(source_path), target))

hiddenimports = []
for package_name in [
    "agentmesh.models",
    "agentmesh.tools",
    "agentmesh.memory.tools",
    "uvicorn",
]:
    hiddenimports += collect_submodules(package_name)


a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AgentMesh",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AgentMesh",
)
