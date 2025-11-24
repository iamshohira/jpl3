from .core import DecoFigure, reset_session, get_session
import os
import json
import zipfile
import datetime
import tempfile
import subprocess
import platform
import shutil

def figure(num_of_figure=1):
    """
    JEM3出力用のFigureオブジェクトを作成します。
    
    Parameters
    ----------
    num_of_figure : int
        作成するFigureの数。
    
    Returns
    -------
    DecoFigure | List[DecoFigure]
        作成されたFigureオブジェクト。
    """
    # セッションをリセット（以前のログや一時ファイルをクリア）
    reset_session()
    session = get_session()
    
    # 必須ライブラリのインポート文をログの冒頭に追加
    session.add_log("import pandas as pd")
    session.add_log("import datetime")
    
    figs = []
    
    # JEM3用の初期化コマンドをログに追加
    # Figure 0 はデフォルトで存在するため、clear()のみ
    session.add_log("figs[0].clear()")
    
    # 最初のFigureを作成・登録
    fig0 = DecoFigure(fig_id=0)
    figs.append(fig0)
    
    # 2つ目以降のFigureを作成
    for i in range(1, num_of_figure):
        # JEM3上でFigureを追加するコマンド
        session.add_log("add_figure()")
        # 追加されたFigureもデフォルトでsubplotがあるためclear()
        session.add_log(f"figs[{i}].clear()")
        
        fig = DecoFigure(fig_id=i)
        figs.append(fig)
    
    if num_of_figure == 1:
        return figs[0]
    else:
        return figs

def save(filename):
    """
    現在のセッションの内容を.jem3ファイルとして保存します。
    
    Parameters
    ----------
    filename : str
        保存先のファイル名（例: "output.jem3"）
    """
    session = get_session()
    
    # --- notebook.json の作成 ---
    cells = []
    
    # 蓄積されたログをcellsに変換
    for log_line in session.logs:
        cell = {
            "code": log_line,
            "description": "from jpl3",
            "expanded": True
        }
        cells.append(cell)
        
    notebook_data = {
        "version": "3.0",
        "created": datetime.datetime.now().isoformat(),
        "cells": cells,
        "addons": []
    }
    
    # notebook.json を一時ディレクトリに保存
    notebook_path = os.path.join(session.temp_dir, "notebook.json")
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook_data, f, indent=4)
        
    # --- zipファイルの作成 ---
    # filenameが .jem3 で終わっていない場合は補完
    if not filename.endswith(".jem3"):
        filename += ".jem3"
        
    with zipfile.ZipFile(filename, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. notebook.json をルートに追加
        zf.write(notebook_path, arcname="notebook.json")
        
        # 2. clipboardディレクトリの中身を追加
        for root, _, files in os.walk(session.clipboard_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                # zip内パス: clipboard/filename
                rel_path = os.path.join("clipboard", file)
                zf.write(abs_path, arcname=rel_path)
                
    # print(f"Successfully saved to {filename}")

def show():
    """
    現在作成中のFigureを一時ファイルに保存し、JEMViewer3アプリを起動して表示します。
    """
    # 1. 一時ファイルの作成 (.jem3)
    fd, temp_path = tempfile.mkstemp(suffix=".jem3", prefix="jpl3_preview_")
    os.close(fd)
    
    try:
        # 現在の状態を一時ファイルに保存
        save(temp_path)
        
        # 2. OS判定とアプリパスの探索
        current_os = platform.system()
        app_path = None
        cmd = []

        if current_os == "Darwin":  # macOS
            # macOS標準のアプリケーションフォルダ、またはユーザーフォルダを探す
            candidates = [
                "/Applications/JEMViewer3.app",
                os.path.expanduser("~/Applications/JEMViewer3.app")
            ]
            for p in candidates:
                if os.path.exists(p):
                    app_path = p
                    break
            
            if app_path:
                # macOSでは 'open -a AppPath FilePath' コマンドを使用するのが一般的で安全
                cmd = ["open", "-a", app_path, temp_path]
            else:
                raise FileNotFoundError("JEMViewer3.app not found in /Applications or ~/Applications")

        elif current_os == "Windows": # Windows
            # Briefcase (MSI) のインストール先候補
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
                raise FileNotFoundError(
                    "JEMViewer3.exe not found. Please check if it is installed in 'Program Files' or 'AppData'."
                )

        else:
            raise OSError(f"Unsupported operating system: {current_os}")

        # 3. アプリケーションの起動
        print(f"Launching JEMViewer3 from: {app_path}")
        subprocess.Popen(cmd)

    except Exception as e:
        print(f"[Error] Failed to launch JEMViewer3: {e}")
        raise