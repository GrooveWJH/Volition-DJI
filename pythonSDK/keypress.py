import sys
from pynput import keyboard

def on_press(key):
    """
    当按键被按下时调用的回调函数。
    """
    try:
        # 尝试打印可打印字符
        print(f'Key pressed: {key.char}')
    except AttributeError:
        # 处理特殊按键 (e.g., Ctrl, Alt, Shift, Esc)
        print(f'Special key pressed: {key}')

    # 如果按下的是 'Esc' 键，则停止监听
    if key == keyboard.Key.esc:
        print('Escape key detected, stopping listener...')
        # 返回 False 会停止 Listener
        return False

# --- 主程序 ---

print("Starting keyboard listener...")
print("This program will print all keystrokes in real-time WITHOUT interfering with other applications.")
print("Running on: " + sys.platform)
print("\n--- Press the 'Esc' key in any window to stop this script ---")

# 使用 with 语句来确保监听器被正确管理
# 重点：我们没有设置 suppress=True，所以它不会干扰其他程序。
try:
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
except Exception as e:
    print(f"An error occurred: {e}")
    print("On macOS, this usually means you need to grant accessibility permissions.")
    print("On Linux, you might need to run without sudo.")

print("\nListener stopped. Exiting.")