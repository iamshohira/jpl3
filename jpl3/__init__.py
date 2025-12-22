from .core import DecoFigure, reset_session, get_session
import os
import json
import zipfile
import datetime
import tempfile
import subprocess
import platform
import shutil
import io
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import gc

# -----------------------------------------------------
# Helper Code Injection
# -----------------------------------------------------
LOADER_SCRIPT = """
import pandas as pd
import datetime
import numpy as np
import io

# Load the single data archive
try:
    # clipboard() is expected to return the path to the extracted file provided by JEMViewer3
    _archive_path = clipboard("data.npz")
    _archive = np.load(_archive_path)
except Exception as e:
    print(f"Warning: Could not load data.npz: {e}")
    _archive = {}

def _load_npy(key):
    return _archive[key]

def _load_csv(key, **kwargs):
    # Extract bytes from uint8 array and read as CSV
    bytes_data = _archive[key].tobytes()
    return pd.read_csv(io.BytesIO(bytes_data), **kwargs)
"""

def figure(num_of_figure=1):
    """
    JEM3出力用のFigureオブジェクトを作成します。
    """
    reset_session()
    session = get_session()
    
    # --- Cell 1: Setup Phase ---
    # add_figure() などの環境構築コマンドは setup_logs に記録する
    
    figs = []
    
    # Figure 0 はデフォルトで存在するため、セットアップログへの追加は不要
    # figs[0].clear() は「操作」の一部として通常のログ(Cell 2)へ記録する
    session.add_log("figs[0].clear()")
    
    fig0 = DecoFigure(fig_id=0)
    figs.append(fig0)
    
    # 2つ目以降のFigureを追加
    for i in range(1, num_of_figure):
        # 環境構築: Figureの追加は Cell 1 (Setup)
        session.add_setup_log("add_figure()")
        
        # 操作: 初期化(clear)は Cell 2 (Operations)
        session.add_log(f"figs[{i}].clear()")
        
        fig = DecoFigure(fig_id=i)
        figs.append(fig)
    
    if num_of_figure == 1:
        return figs[0]
    else:
        return figs

def save(filename, cleanup=True):
    """
    現在のセッションの内容を.jem3ファイルとして保存します。
    """
    session = get_session()
    
    if isinstance(filename, Path):
        filename = str(filename)

    # --- 1. data.npz の作成 (メモリ上のblobをファイルに書き出し) ---
    npz_filename = "data.npz"
    npz_path = os.path.join(session.clipboard_dir, npz_filename)
    
    if session.blobs:
        np.savez_compressed(npz_path, **session.blobs)
    else:
        np.savez_compressed(npz_path)

    # --- 2. notebook.json の作成 (2セル構成) ---
    
    # Cell 1: ヘルパー関数定義 + 初期セットアップ(add_figure)
    setup_code = LOADER_SCRIPT + "\n" + "\n".join(session.setup_logs)
    
    # Cell 2: 実際のプロット操作(clearを含む)
    main_code = "\n".join(session.logs)
    
    cells = [
        {
            "code": setup_code,
            "description": "JPL3 Setup & Initialization",
            "expanded": False
        },
        {
            "code": main_code,
            "description": "JPL3 Generated Operations",
            "expanded": True
        }
    ]
        
    notebook_data = {
        "version": "3.0",
        "created": datetime.datetime.now().isoformat(),
        "cells": cells,
        "addons": []
    }
    
    notebook_path = os.path.join(session.temp_dir, "notebook.json")
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook_data, f, indent=4)
        
    # --- 3. zipファイルの作成 ---
    if not filename.endswith(".jem3"):
        filename += ".jem3"
        
    with zipfile.ZipFile(filename, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(notebook_path, arcname="notebook.json")
        if os.path.exists(npz_path):
            zf.write(npz_path, arcname=f"clipboard/{npz_filename}")
                
    # --- 4. クリーンアップ ---
    if cleanup:
        plt.close('all')
        reset_session()
        gc.collect()

def show():
    """
    現在作成中のFigureを一時ファイルに保存し、JEMViewer3アプリを起動して表示します。
    """
    fd, temp_path = tempfile.mkstemp(suffix=".jem3", prefix="jpl3_preview_")
    os.close(fd)
    
    try:
        save(temp_path)
        
        current_os = platform.system()
        app_path = None
        cmd = []

        if current_os == "Darwin":
            candidates = [
                "/Applications/JEMViewer3.app",
                os.path.expanduser("~/Applications/JEMViewer3.app")
            ]
            for p in candidates:
                if os.path.exists(p):
                    app_path = p
                    break
            if app_path:
                cmd = ["open", "-a", app_path, temp_path]
            else:
                raise FileNotFoundError("JEMViewer3.app not found")

        elif current_os == "Windows":
            candidates = [
                r"C:\Program Files\JEMViewer3\JEMViewer3.exe",
                r"C:\Program Files (x86)\JEMViewer3\JEMViewer3.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\JEMViewer3\JEMViewer3.exe")
            ]
            for p in candidates:
                if os.path.exists(p):
                    app_path = p
                    break
            if app_path:
                cmd = [app_path, temp_path]
            else:
                raise FileNotFoundError("JEMViewer3.exe not found")

        else:
            raise OSError(f"Unsupported operating system: {current_os}")

        print(f"Launching JEMViewer3 from: {app_path}")
        subprocess.Popen(cmd)

    except Exception as e:
        print(f"[Error] Failed to launch JEMViewer3: {e}")
        raise