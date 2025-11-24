import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import numpy.ma as ma
import jpl3

def run_comprehensive_test():
    print("=== Start Comprehensive Test for DecoFigure ===\n")

    # 1. DecoFigureの初期化
    fig = jpl3.figure(1)
    
    # 3x3 のグリッドを作成して様々なプロットを配置
    # (subplotsもndarrayを返すため、正しく処理されるかテスト)
    axs = fig.subplots(3, 3)
    
    # 見やすくするためにレイアウト調整
    fig.subplots_adjust(hspace=0.4, wspace=0.3)
    fig.suptitle("DecoFigure Comprehensive Test")

    # ---------------------------------------------------------
    # Test 1: 基本的な NumPy Array と Line2D
    # ---------------------------------------------------------
    ax1 = axs[0, 0]
    x_np = np.linspace(0, 10, 100)
    y_np = np.sin(x_np)
    # ndarrayの保存と読み出し、kwargs(color, label)のテスト
    ax1.plot(x_np, y_np, color='blue', label='NumPy Sin')
    ax1.set_title("1. NumPy Array & Plot")
    ax1.legend()

    # ---------------------------------------------------------
    # Test 2: Pandas DataFrame & Series
    # ---------------------------------------------------------
    ax2 = axs[0, 1]
    df = pd.DataFrame({
        'A': np.arange(10),
        'B': np.random.rand(10) * 10
    })
    # DataFrameの列(Series)を渡すテスト (.csv保存の確認)
    ax2.plot(df['A'], df['B'], marker='o', linestyle='--', color='green')
    ax2.set_title("2. Pandas DataFrame Columns")

    # ---------------------------------------------------------
    # Test 3: DateTime (Python datetime & Pandas Timestamp)
    # ---------------------------------------------------------
    ax3 = axs[0, 2]
    dates = [datetime.date(2025, 1, 1) + datetime.timedelta(days=i) for i in range(10)]
    values = np.random.randint(0, 10, 10)
    # Python標準のdatetimeオブジェクトリストのテスト
    ax3.plot(dates, values, color='orange')
    
    # PandasのDatetimeIndexのテスト (csv保存時の parse_dates 確認)
    ts_index = pd.date_range('2025-02-01', periods=10)
    ts_values = pd.Series(np.random.rand(10) * 5 + 5, index=ts_index)
    ax3.plot(ts_index, ts_values.values, color='red', linestyle=':')
    
    # 日付フォーマットの自動調整
    fig.autofmt_xdate() 
    ax3.set_title("3. DateTime Objects")

    # ---------------------------------------------------------
    # Test 4: Masked Array (欠損値) & Scatter
    # ---------------------------------------------------------
    ax4 = axs[1, 0]
    x_ma = np.linspace(0, 10, 20)
    y_raw = np.cos(x_ma)
    # データの一部をマスク（無効化）する
    y_ma = ma.masked_where(y_raw < 0, y_raw)
    
    # MaskedArray専用の保存ロジック(data/mask分離)のテスト
    # Scatter (PathCollection) のテスト
    ax4.scatter(x_ma, y_ma, c='purple', s=50, label='Masked Cos')
    ax4.set_title("4. MaskedArray & Scatter")

    # ---------------------------------------------------------
    # Test 5: Categorical Data & Bar Plot
    # ---------------------------------------------------------
    ax5 = axs[1, 1]
    categories = pd.Categorical(["Apple", "Banana", "Cherry", "Apple"])
    counts = [10, 15, 7, 12]
    
    # カテゴリカルデータの保存と復元(astype('category'))のテスト
    # Bar (Patch) のテスト
    ax5.bar(categories, counts, color=['red', 'yellow', 'purple', 'green'])
    ax5.set_title("5. Categorical & Bar")

    # ---------------------------------------------------------
    # Test 6: Fill Between (PolyCollection)
    # ---------------------------------------------------------
    ax6 = axs[1, 2]
    x_fill = np.linspace(0, 5, 50)
    y1 = np.sin(x_fill)
    y2 = np.sin(x_fill) - 0.5
    
    # 複数のndarray引数を持つ関数のテスト
    ax6.fill_between(x_fill, y1, y2, color='cyan', alpha=0.3)
    ax6.set_title("6. Fill Between")

    # ---------------------------------------------------------
    # Test 7: Histogram (戻り値が複雑なメソッド)
    # ---------------------------------------------------------
    ax7 = axs[2, 0]
    data_hist = np.random.randn(1000)
    
    # histは (n, bins, patches) を返す。
    # 戻り値に含まれる patches が正しく登録されるかテスト
    n, bins, patches = ax7.hist(data_hist, bins=20, color='gray', edgecolor='black')
    ax7.set_title("7. Histogram")

    # ---------------------------------------------------------
    # Test 8: Imshow (2D Array / Image)
    # ---------------------------------------------------------
    ax8 = axs[2, 1]
    img_data = np.random.rand(10, 10)
    
    # 2D配列の保存と AxesImage の登録テスト
    im = ax8.imshow(img_data, cmap='viridis', interpolation='nearest')
    fig.colorbar(im, ax=ax8) # Colorbarのテスト
    ax8.set_title("8. Imshow (Image)")

    # ---------------------------------------------------------
    # Test 9: Text & Annotations
    # ---------------------------------------------------------
    ax9 = axs[2, 2]
    ax9.axis('off') #軸を消すメソッド
    
    # 文字列引数のクォート処理のテスト
    ax9.text(0.5, 0.5, "Hello\nDecoFigure!", ha='center', va='center', fontsize=12)
    
    # 辞書型引数 (arrowprops) の再帰的シリアライズテスト
    ax9.annotate('Look here', xy=(0.2, 0.2), xytext=(0.8, 0.8),
                 arrowprops=dict(facecolor='black', shrink=0.05))
    ax9.set_title("9. Text & Annotation")

    print("\n=== Test Finished. Copy the output below to verify reproduction ===\n")
    jpl3.show()

if __name__ == "__main__":
    run_comprehensive_test()