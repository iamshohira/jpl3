import jpl3
import numpy as np
import pandas as pd
import datetime
import os

def run_test():
    print("=== JPL3 Integration Test Start ===\n")

    # 1. Figureの作成
    # jpl3.figure(1) は DecoFigureオブジェクト（Matplotlib互換）を返します
    print("[1] Creating Figure...")
    fig = jpl3.figure(1) 

    # サブプロットの作成
    axs = fig.subplots(2, 2)
    fig.suptitle("JPL3 Test Project")
    fig.subplots_adjust(hspace=0.4, wspace=0.3)

    # -----------------------------------------------------------
    # Test A: 基本的な NumPy Plot
    # -----------------------------------------------------------
    print(" - Plotting NumPy arrays...")
    ax1 = axs[0, 0]
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    ax1.plot(x, y, label="Sin Wave", color="blue")
    ax1.set_title("NumPy Array")
    ax1.legend()

    # -----------------------------------------------------------
    # Test B: Pandas DataFrame & Series
    # -----------------------------------------------------------
    print(" - Plotting Pandas DataFrame...")
    ax2 = axs[0, 1]
    df = pd.DataFrame({
        'A': np.arange(10),
        'B': np.random.rand(10) * 10
    })
    ax2.plot(df['A'], df['B'], marker='o', linestyle='--', color='green', label="DataFrame Data")
    ax2.set_title("Pandas Data")
    ax2.legend()

    # -----------------------------------------------------------
    # Test C: DateTime & Masked Array
    # -----------------------------------------------------------
    print(" - Plotting DateTime & Masked Array...")
    ax3 = axs[1, 0]
    # 日付データの生成
    dates = [datetime.date(2025, 1, 1) + datetime.timedelta(days=i) for i in range(20)]
    values = np.random.randn(20).cumsum()
    
    # Masked Array (値が負の部分をマスク)
    masked_values = np.ma.masked_where(values < 0, values)
    
    ax3.plot(dates, values, color='lightgray', label="Original")
    ax3.plot(dates, masked_values, marker='s', color='red', markersize=4, label="Positive (Masked)")
    
    # 日付フォーマットの自動調整
    fig.autofmt_xdate()
    ax3.set_title("DateTime & Masked")
    ax3.legend()

    # -----------------------------------------------------------
    # Test D: Imshow & Colorbar (オブジェクト参照のテスト)
    # -----------------------------------------------------------
    print(" - Plotting Imshow & Colorbar...")
    ax4 = axs[1, 1]
    img_data = np.random.rand(10, 10)
    
    # imshowは AxesImage オブジェクトを返す
    im = ax4.imshow(img_data, cmap='viridis', interpolation='nearest')
    
    # colorbarには mappable (im) を渡す必要がある
    # jpl3 はこれを "figs[0].axes[3].images[0]" のように正しく記録できるかテスト
    fig.colorbar(im, ax=ax4, label="Intensity")
    ax4.set_title("Imshow & Colorbar")

    # -----------------------------------------------------------
    # 2. ファイルへの保存 (jpl3.save)
    # -----------------------------------------------------------
    save_filename = "test_output.jem3"
    print(f"\n[2] Saving to '{save_filename}'...")
    jpl3.save(save_filename)
    
    if os.path.exists(save_filename):
        print(" -> Save success.")
    else:
        print(" -> Save FAILED.")

    # -----------------------------------------------------------
    # 3. アプリケーション起動 (jpl3.show)
    # -----------------------------------------------------------
    print("\n[3] Launching JEMViewer3 (jpl3.show)...")
    try:
        # これを実行すると、一時ファイルが作成され、JEMViewer3が起動するはずです
        # 起動したJEMViewer3は「新規プロジェクト」として振る舞うはずです
        jpl3.show()
        print(" -> Launch command executed.")
    except Exception as e:
        print(f" -> Launch FAILED: {e}")
        print("    (JEMViewer3がインストールされていない場合はエラーになります)")

    print("\n=== Test Finished ===")

if __name__ == "__main__":
    run_test()