from .core import DecoFigure, JPLSession
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
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec

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

# 全てのアクティブなプロジェクトを保持するリスト
_active_projects = []

class Project:
    """
    JPL3のプロジェクト（セッション）クラス。
    """
    def __init__(self):
        self.session = JPLSession()
        # プロジェクトIDの発行（リスト内のインデックス等を利用）
        self.id = len(_active_projects)
        # グローバルリストに登録
        _active_projects.append(self)

    def figure(self, num_of_figure=1):
        """
        このプロジェクトにFigureを追加します。
        """
        new_figs = []
        current_count = len(self.session.figures)
        
        for i in range(num_of_figure):
            fig_idx = current_count + i
            if fig_idx > 0:
                self.session.add_setup_log("add_figure()")
            
            self.session.add_log(f"figs[{fig_idx}].clear()")
            
            fig = DecoFigure(self.session, fig_id=fig_idx)
            self.session.figures.append(fig)
            new_figs.append(fig)
        
        if num_of_figure == 1:
            return new_figs[0]
        else:
            return new_figs

    def save(self, filename, cleanup=True):
        """
        現在のプロジェクトの内容を.jem3ファイルとして保存します。
        """
        if isinstance(filename, Path):
            filename = str(filename)

        # --- 1. data.npz ---
        npz_filename = "data.npz"
        npz_path = os.path.join(self.session.clipboard_dir, npz_filename)
        
        if self.session.blobs:
            np.savez_compressed(npz_path, **self.session.blobs)
        else:
            np.savez_compressed(npz_path)

        # --- 2. notebook.json ---
        setup_code = LOADER_SCRIPT + "\n" + "\n".join(self.session.setup_logs)
        main_code = "\n".join(self.session.logs)
        
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
        
        notebook_path = os.path.join(self.session.temp_dir, "notebook.json")
        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook_data, f, indent=4)
            
        # --- 3. zipファイルの作成 ---
        if not filename.endswith(".jem3"):
            filename += ".jem3"
            
        with zipfile.ZipFile(filename, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(notebook_path, arcname="notebook.json")
            if os.path.exists(npz_path):
                zf.write(npz_path, arcname=f"clipboard/{npz_filename}")
                    
        # --- 4. クリーンアップ (インスタンス単位) ---
        if cleanup:
            for fig in self.session.figures:
                plt.close(fig)
            self.session.cleanup()
            # ここでは gc.collect() は呼ばず、呼び出し元に任せるか最後にまとめて行う

    def show(self):
        """
        現在のプロジェクトを一時ファイルに保存し、JEMViewer3アプリを起動して表示します。
        """
        fd, temp_path = tempfile.mkstemp(suffix=".jem3", prefix=f"jpl3_preview_p{self.id}_")
        os.close(fd)
        
        try:
            # showは破壊的な変更を行わないよう cleanup=False
            self.save(temp_path, cleanup=False)
            
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

            print(f"Launching JEMViewer3 (Project {self.id}) from: {app_path}")
            subprocess.Popen(cmd)

        except Exception as e:
            print(f"[Error] Failed to launch JEMViewer3: {e}")
            raise


# -----------------------------------------------------
# Global API (Wrapper for All Projects)
# -----------------------------------------------------

_default_project = None

def project():
    """新しいプロジェクトを作成して返します。"""
    return Project()

def figure(num_of_figure=1):
    """
    [Backward Compatibility]
    デフォルトプロジェクトをリセット（新規作成）し、Figureを追加します。
    """
    global _default_project
    
    # 既存のデフォルトプロジェクトがある場合、アクティブリストから除外して破棄
    if _default_project is not None:
        if _default_project in _active_projects:
            _active_projects.remove(_default_project)
        _default_project.session.cleanup()
    
    _default_project = Project()
    return _default_project.figure(num_of_figure)

def show():
    """
    全てのアクティブなプロジェクトに対して show() を実行します。
    """
    if not _active_projects:
        print("Warning: No active projects to show.")
        return

    for proj in _active_projects:
        proj.show()

def save(filename, cleanup=True):
    """
    全てのアクティブなプロジェクトを保存します。
    ファイル名は {basename}_{project_id}.jem3 となります。
    
    Args:
        filename (str): ベースとなるファイル名 (例: "output.jem3")
        cleanup (bool): 保存後にリソースを解放するかどうか
    """
    if not _active_projects:
        print("Warning: No active projects to save.")
        return

    # 拡張子の処理
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".jem3"
    
    # 全プロジェクトをループして保存
    for proj in _active_projects:
        # project.id を使って一意なファイル名を生成
        target_filename = f"{base}_{proj.id}{ext}"
        print(f"Saving project {proj.id} to {target_filename}...")
        proj.save(target_filename, cleanup=cleanup)
    
    if cleanup:
        # リストをクリア
        _active_projects.clear()
        
        # デフォルトプロジェクト参照もクリア
        global _default_project
        _default_project = None
        
        gc.collect()