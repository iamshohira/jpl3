import jpl3
import numpy as np
import pandas as pd

def run_multi_fig_test():
    print("=== JPL3 Multi-Figure Test Start ===\n")

    # 1. 2つのFigureを作成
    # jpl3.figure(N) で N > 1 の場合、[fig0, fig1, ...] のリストが返ります
    print("[1] Creating 2 Figures...")
    figs = jpl3.figure(2)
    
    fig0 = figs[0]
    fig1 = figs[1]

    # -----------------------------------------------------------
    # Figure 0 への描画 (正弦波)
    # -----------------------------------------------------------
    print("[2] Drawing on Figure 0 (Main Window)...")
    ax0 = fig0.add_subplot(111)
    
    x = np.linspace(0, 10, 50)
    y = np.sin(x)
    
    # NumPy配列の保存テスト
    ax0.plot(x, y, 'r-o', label='Sin(x)')
    ax0.set_title("Figure 0: Sine Wave")
    ax0.legend()
    ax0.set_xlabel("Time [s]")
    ax0.set_ylabel("Amplitude")

    # -----------------------------------------------------------
    # Figure 1 への描画 (散布図)
    # -----------------------------------------------------------
    print("[3] Drawing on Figure 1 (Added Window)...")
    ax1 = fig1.add_subplot(111)
    
    # Pandas DataFrameの保存テスト
    df = pd.DataFrame({
        'x': np.random.rand(50),
        'y': np.random.rand(50),
        'size': np.random.randint(10, 100, 50)
    })
    
    ax1.scatter(df['x'], df['y'], s=df['size'], c='blue', alpha=0.5, label='Random Data')
    ax1.set_title("Figure 1: Pandas Scatter")
    ax1.legend()
    ax1.grid(True)

    # -----------------------------------------------------------
    # 4. アプリケーション起動
    # -----------------------------------------------------------
    print("\n[4] Launching JEMViewer3...")
    try:
        # 期待される動作:
        # 1. JEMViewer3が起動する
        # 2. 自動的に「Figure 0」と「Figure 1」の2つのウィンドウ（またはタブ）が表示される
        # 3. Figure 1 はコード上の add_figure() によって生成されたものとして認識される
        jpl3.show()
        # jpl3.save("multi_fig_test_output.jem3")
        print(" -> Launch command executed.")
    except Exception as e:
        print(f" -> Error: {e}")

    print("\n=== Test Finished ===")

if __name__ == "__main__":
    run_multi_fig_test()