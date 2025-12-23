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
import io
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
    1つのプロジェクト（セッション）の状態を管理するクラス。
    ログ、バイナリデータ、一時ディレクトリを保持する。
    """
    def __init__(self):
        self.logs = []        # 通常の操作ログ（Cell 2用）
        self.setup_logs = []  # 初期化・構成ログ（Cell 1用）
        self.data_counter = 0
        self.temp_dir = tempfile.mkdtemp(prefix="jpl3_temp_")
        self.clipboard_dir = os.path.join(self.temp_dir, "clipboard")
        os.makedirs(self.clipboard_dir, exist_ok=True)
        self.figures = []     # このセッションに紐づくFigureリスト
        
        # データを一時ファイルではなくメモリ上に保持する辞書
        self.blobs = {}

    def add_log(self, command):
        """通常の操作ログを追加"""
        self.logs.append(command)

    def add_setup_log(self, command):
        """初期化・構成用のログを追加"""
        self.setup_logs.append(command)

    def get_new_key(self):
        """データ識別のためのユニークキーを発行"""
        key = f"data_{self.data_counter}"
        self.data_counter += 1
        return key

    def store_blob(self, key, data):
        """データをメモリ(blobs)に格納"""
        self.blobs[key] = data

    def cleanup(self):
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            warnings.warn(f"Failed to cleanup temp dir: {e}")
        self.blobs.clear()
        self.figures.clear()

# -----------------------------------------------------
# DecoFigure Class
# -----------------------------------------------------

class DecoFigure(Figure):
    def __init__(self, session, fig_id, *args, **kwargs):
        """
        session: このFigureが所属するJPLSessionインスタンス
        fig_id: セッション内でのFigure ID (0, 1, 2...)
        """
        self.session = session  # セッションをインスタンス変数として保持
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
        self.exclude = re.compile(
            r'get_.*|stale_callback|draw|apply_aspect|ArtistList|set_id|_.*|__.*|clear|clf|sca$'
        )
        
        super().__init__(*args, **kwargs)
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

        try:
            members = inspect.getmembers(obj)
        except Exception:
            return

        for name, fn in members:
            try:
                if self.exclude.match(name) or not inspect.isroutine(fn):
                    continue
                
                if hasattr(fn, '_deco_original'):
                    continue 

                setattr(obj, name, self._print_function(name, obj)(fn))

            except Exception:
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
                result = fn(*args, **kwargs) 
                
                should_log = False
                if self.call_from == "interactive":
                    should_log = True
                else:
                    try:
                        stack = inspect.stack()
                        caller_frame = stack[1]
                        caller_file = caller_frame.filename
                        if caller_file and os.path.abspath(caller_file) == self.call_from:
                             should_log = True
                    except Exception:
                        pass
                
                if should_log:
                    header = self._header(obj)
                    if header: 
                        func_name = f"{header}.{name}"
                        # self.session を使用してログを記録
                        command = self._save_emulate_command(func_name, *args, **kwargs)
                        self.session.add_log(command)
                
                self._scan_and_register_new_artists(obj)
                
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
    
    def _to_csv_bytes(self, obj, **kwargs):
        buf = io.BytesIO()
        obj.to_csv(buf, **kwargs)
        return np.frombuffer(buf.getvalue(), dtype=np.uint8)

    def _emulate_args(self, x):
        # self.session を使用
        session = self.session
        
        # 1. 登録済みアーティスト
        header = self._header(x)
        if header:
            return header

        try:
            # 2. ファイル保存が必要な型 -> メモリ上のblobsに保存
            if isinstance(x, ma.MaskedArray):
                d_key = session.get_new_key()
                m_key = session.get_new_key()
                session.store_blob(d_key, x.data)
                session.store_blob(m_key, x.mask)
                return f'np.ma.MaskedArray(data=_load_npy("{d_key}"), mask=_load_npy("{m_key}"))'

            if isinstance(x, np.ndarray):
                key = session.get_new_key()
                session.store_blob(key, x)
                return f'_load_npy("{key}")'

            if isinstance(x, pd.Series):
                key = session.get_new_key()
                session.store_blob(key, self._to_csv_bytes(x, index=True, header=True))
                
                if pd.api.types.is_datetime64_any_dtype(x.dtype):
                    return f'_load_csv("{key}", index_col=0, header=0, parse_dates=[{x.name!r}]).squeeze("columns")'
                elif pd.api.types.is_categorical_dtype(x.dtype):
                    return f'_load_csv("{key}", index_col=0, header=0).squeeze("columns").astype("category")'
                else:
                    return f'_load_csv("{key}", index_col=0, header=0).squeeze("columns")'

            if isinstance(x, pd.DataFrame):
                key = session.get_new_key()
                session.store_blob(key, self._to_csv_bytes(x, index=True))
                return f'_load_csv("{key}", index_col=0)'
                
            if isinstance(x, pd.DatetimeIndex):
                key = session.get_new_key()
                session.store_blob(key, self._to_csv_bytes(pd.Series(x), index=True, header=False))
                return f'_load_csv("{key}", index_col=0, header=None, parse_dates=True).index'

            if isinstance(x, (pd.Categorical, pd.CategoricalIndex)):
                key = session.get_new_key()
                session.store_blob(key, self._to_csv_bytes(pd.Series(x), index=False, header=True))
                return f'_load_csv("{key}", header=0).squeeze("columns").astype("category")'

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