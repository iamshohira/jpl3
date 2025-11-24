import os
import shutil
import zipfile
import json
import datetime
import inspect
import re
import warnings
import tempfile
import sys
from functools import wraps
import numpy as np
import numpy.ma as ma
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.artist import Artist

# -----------------------------------------------------
# Session Management
# -----------------------------------------------------

class JPLSession:
    """
    現在のセッション状態（ログ、一時ファイル、カウンタ）を管理するシングルトン
    """
    def __init__(self):
        self.logs = [] 
        self.data_counter = 0
        self.temp_dir = tempfile.mkdtemp(prefix="jpl3_temp_")
        self.clipboard_dir = os.path.join(self.temp_dir, "clipboard")
        os.makedirs(self.clipboard_dir, exist_ok=True)
        self.figures = []

    def add_log(self, command):
        self.logs.append(command)

    def get_new_filename(self, ext):
        filename = f"data_{self.data_counter}{ext}"
        self.data_counter += 1
        return filename

    def get_filepath(self, filename):
        return os.path.join(self.clipboard_dir, filename)

    def cleanup(self):
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            warnings.warn(f"Failed to cleanup temp dir: {e}")

_session = None

def get_session():
    global _session
    if _session is None:
        _session = JPLSession()
    return _session

def reset_session():
    global _session
    if _session:
        _session.cleanup()
    _session = JPLSession()

# -----------------------------------------------------
# DecoFigure Class
# -----------------------------------------------------

class DecoFigure(Figure):
    def __init__(self, fig_id, *args, **kwargs):
        self._fig_id = fig_id
        self.artist_map = {}
        # 追跡対象のリスト
        self.childs_tree = {
            DecoFigure: ['axes'],
            Axes: ['lines', 'patches', 'collections', 'images', 'texts'],
        }
        
        # 呼び出し元の特定（対話モードかどうか）
        try:
            if hasattr(sys.modules['__main__'], '__file__') and sys.modules['__main__'].__file__:
                self.call_from = os.path.abspath(sys.modules['__main__'].__file__)
            else:
                self.call_from = "interactive"
        except (AttributeError, KeyError, NameError):
            self.call_from = "interactive"
        
        # 除外リスト
        # sca$ : scatterが巻き込まれないよう末尾一致に変更
        self.exclude = re.compile(
            r'get_.*|stale_callback|draw|apply_aspect|ArtistList|set_id|_.*|__.*|clear|clf|sca$'
        )
        
        # matplotlib.figure.Figure の初期化
        super().__init__(*args, **kwargs)
        
        # 自分自身を登録
        self._register_artists_recursive(self, f"figs[{self._fig_id}]")

    def _register_artists_recursive(self, obj, header):
        if obj is None or id(obj) in self.artist_map:
            return
            
        self.artist_map[id(obj)] = header
        self._decorate_methods(obj)
        
        obj_type = type(obj)
        if obj_type in self.childs_tree:
            for child_list_name in self.childs_tree[obj_type]:
                try:
                    child_list = getattr(obj, child_list_name)
                    for i, child in enumerate(child_list):
                        child_header = f"{header}.{child_list_name}[{i}]"
                        self._register_artists_recursive(child, child_header)
                except AttributeError:
                    pass 

    def _decorate_methods(self, obj):
        if hasattr(obj, '_deco_decorated'):
            return 

        # メンバー取得時のエラーガード
        try:
            members = inspect.getmembers(obj)
        except Exception:
            return

        for name, fn in members:
            # 個別のメソッドデコレート失敗がループ全体を止めないように try-except を内部に配置
            try:
                if self.exclude.match(name) or not inspect.isroutine(fn):
                    continue
                
                if hasattr(fn, '_deco_original'):
                    continue 

                # ラッパーの適用
                setattr(obj, name, self._print_function(name, obj)(fn))

            except Exception:
                # 警告が出すぎるとうるさいので、個別の失敗は黙殺して次へ進む
                pass
        
        setattr(obj, '_deco_decorated', True)

    def _safe_flatten(self, obj):
        if isinstance(obj, Artist):
            yield obj
        elif isinstance(obj, np.ndarray):
            if obj.dtype == object:
                for item in obj.flat:
                    yield from self._safe_flatten(item)
        elif isinstance(obj, (list, tuple)) or (hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes))):
            for item in obj:
                yield from self._safe_flatten(item)
        else:
            pass

    def _print_function(self, name, obj):
        def wrapper(fn): 
            @wraps(fn)
            def decorate(*args, **kwargs):
                # --- 関数実行 ---
                result = fn(*args, **kwargs) 
                
                # --- コマンドのロギング判定 ---
                should_log = False
                
                if self.call_from == "interactive":
                    should_log = True
                else:
                    try:
                        # 呼び出し元のフレームを取得
                        stack = inspect.stack()
                        caller_frame = stack[1]
                        caller_file = caller_frame.filename
                        
                        # 呼び出し元がメインスクリプトと一致する場合のみログする
                        if caller_file and os.path.abspath(caller_file) == self.call_from:
                             should_log = True
                    except Exception:
                        pass
                
                if should_log:
                    header = self._header(obj)
                    if header: 
                        func_name = f"{header}.{name}"
                        command = self._save_emulate_command(func_name, *args, **kwargs)
                        get_session().add_log(command)
                
                # --- 新規アーティスト登録 (実行後にスキャン) ---
                self._scan_and_register_new_artists(obj)
                
                # --- 戻り値の登録 ---
                if result is not None:
                    for item in self._safe_flatten(result):
                        if isinstance(item, Artist):
                            self._scan_and_register_new_artists(obj)

                return result

            decorate._deco_original = fn 
            return decorate
        return wrapper

    def _scan_and_register_new_artists(self, obj):
        obj_header = self._header(obj)
        if not obj_header:
            return

        obj_type = type(obj)
        if obj_type in self.childs_tree:
            for child_list_name in self.childs_tree[obj_type]:
                try:
                    child_list = getattr(obj, child_list_name)
                    for i, child in enumerate(child_list):
                        if id(child) not in self.artist_map:
                            child_header = f"{obj_header}.{child_list_name}[{i}]"
                            self._register_artists_recursive(child, child_header)
                except AttributeError:
                    pass
    
    def _header(self, obj):
        obj_id = id(obj)
        return self.artist_map.get(obj_id, None)

    # ---------------------------------------------------------
    # Argument Emulation (Serializer)
    # ---------------------------------------------------------
    
    def _emulate_args(self, x):
        session = get_session()
        
        # 1. 登録済みアーティスト
        header = self._header(x)
        if header:
            return header

        try:
            # 2. ファイル保存が必要な型
            if isinstance(x, ma.MaskedArray):
                d_name = session.get_new_filename(".npy")
                m_name = session.get_new_filename(".npy")
                np.save(session.get_filepath(d_name), x.data, allow_pickle=False)
                np.save(session.get_filepath(m_name), x.mask, allow_pickle=False)
                return f'np.ma.MaskedArray(data=np.load(clipboard("{d_name}")), mask=np.load(clipboard("{m_name}")))'

            if isinstance(x, np.ndarray):
                fname = session.get_new_filename(".npy")
                np.save(session.get_filepath(fname), x, allow_pickle=False)
                return f'np.load(clipboard("{fname}"))'

            if isinstance(x, pd.Series):
                fname = session.get_new_filename(".csv")
                x.to_csv(session.get_filepath(fname), index=True, header=True)
                
                if pd.api.types.is_datetime64_any_dtype(x.dtype):
                    return f'pd.read_csv(clipboard("{fname}"), index_col=0, header=0, parse_dates=[{x.name!r}]).squeeze("columns")'
                elif pd.api.types.is_categorical_dtype(x.dtype):
                    return f'pd.read_csv(clipboard("{fname}"), index_col=0, header=0).squeeze("columns").astype("category")'
                else:
                    return f'pd.read_csv(clipboard("{fname}"), index_col=0, header=0).squeeze("columns")'

            if isinstance(x, pd.DataFrame):
                fname = session.get_new_filename(".csv")
                x.to_csv(session.get_filepath(fname), index=True)
                return f'pd.read_csv(clipboard("{fname}"), index_col=0)'
                
            if isinstance(x, pd.DatetimeIndex):
                fname = session.get_new_filename(".csv")
                pd.Series(x).to_csv(session.get_filepath(fname), index=True, header=False)
                return f'pd.read_csv(clipboard("{fname}"), index_col=0, header=None, parse_dates=True).index'

            if isinstance(x, (pd.Categorical, pd.CategoricalIndex)):
                fname = session.get_new_filename(".csv")
                pd.Series(x).to_csv(session.get_filepath(fname), index=False, header=True)
                return f'pd.read_csv(clipboard("{fname}"), header=0).squeeze("columns").astype("category")'

            # 3. 基本型
            typ = type(x)
            if typ in (int, float, bool, type(None)):
                return str(x)
            if typ == str:
                return repr(x)

            # 4. 再生可能なコンストラクタ
            if isinstance(x, datetime.datetime):
                return repr(x)
            if isinstance(x, datetime.date):
                return repr(x)
            if isinstance(x, pd.Timestamp):
                return f'pd.Timestamp("{x.isoformat()}")'

            # 5. コンテナ (再帰)
            if typ == list:
                return f"[{', '.join(self._emulate_args(item) for item in x)}]"
            if typ == tuple:
                items_str = ', '.join(self._emulate_args(item) for item in x)
                if len(x) == 1: items_str += ','
                return f"({items_str})"
            if typ == dict:
                return f"{{{', '.join(f'{self._emulate_args(k)}: {self._emulate_args(v)}' for k, v in x.items())}}}"
                
            # 6. フォールバック
            return repr(x)

        except Exception as e:
            warnings.warn(f"emulate_args failed for type {type(x)}: {e}")
            return f'"<unserializable object: {type(x).__name__}>"'

    def _save_emulate_command(self, function_name, *args, **kwargs):
        str_args = []
        for arg in args:
            str_args.append(self._emulate_args(arg))
        for k, v in kwargs.items():
            str_args.append(f"{k} = {self._emulate_args(v)}")
        return f"{function_name}({','.join(str_args)})"