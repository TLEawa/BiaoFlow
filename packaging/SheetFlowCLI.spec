import os

a = Analysis(
    ["cli_entry.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=["openpyxl", "yaml"],
    noarchive=False,
)
a.binaries = [
    item
    for item in a.binaries
    if os.path.basename(item[0]).lower() not in {"icuuc.dll", "icudt78.dll"}
]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sheetflow",
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="sheetflow-cli")
