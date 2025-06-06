import os
import time
import subprocess
from PIL import Image
import ast,re


def get_screenshot(adb_path):
    command = adb_path + " shell rm /sdcard/screenshot.png"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(0.5)
    command = adb_path + " shell screencap -p /sdcard/screenshot.png"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(0.5)
    command = adb_path + " pull /sdcard/screenshot.png ./screenshot"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    image_path = "./screenshot/screenshot.png"
    save_path = "./screenshot/screenshot.jpg"
    image = Image.open(image_path)
    image.convert("RGB").save(save_path, "JPEG")
    os.remove(image_path)


def tap(adb_path, x, y):
    command = adb_path + f" shell input tap {x} {y}"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def type(adb_path, text):
    text = text.replace("\\n", "_").replace("\n", "_")
    for char in text:
        if char == ' ':
            command = adb_path + f" shell input text %s"
            subprocess.run(command, capture_output=True, text=True, shell=True)
        elif char == '_':
            command = adb_path + f" shell input keyevent 66"
            subprocess.run(command, capture_output=True, text=True, shell=True)
        elif 'a' <= char <= 'z' or 'A' <= char <= 'Z' or char.isdigit():
            command = adb_path + f" shell input text {char}"
            subprocess.run(command, capture_output=True, text=True, shell=True)
        elif char in '-.,!?@\'°/:;()':
            command = adb_path + f" shell input text \"{char}\""
            subprocess.run(command, capture_output=True, text=True, shell=True)
        else:
            command = adb_path + f" shell am broadcast -a ADB_INPUT_TEXT --es msg \"{char}\""
            subprocess.run(command, capture_output=True, text=True, shell=True)


def slide(adb_path, x1, y1, x2, y2):
    command = adb_path + f" shell input swipe {x1} {y1} {x2} {y2} 500"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def back(adb_path):
    command = adb_path + f" shell input keyevent 4"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    
    
def home(adb_path):
    command = adb_path + f" shell am start -a android.intent.action.MAIN -c android.intent.category.HOME"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def long_press(adb_path, x, y, duration=1000):
    """
    模拟长按操作（通过滑动相同坐标+持续时间实现）
    参数:
        adb_path: ADB 可执行文件路径
        x, y: 屏幕坐标
        duration: 持续时间（毫秒）
    """
    command = f"{adb_path} shell input swipe {x} {y} {x} {y} {duration}"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def scroll(adb_path, x, y, direction="down", distance=500, duration=300):

    if direction == "down":
        command = f"{adb_path} shell input swipe {x} {y} {x} {y - distance} {duration}"
    elif direction == "up":
        command = f"{adb_path} shell input swipe {x} {y} {x} {y + distance} {duration}"
    elif direction == "right":
        command = f"{adb_path} shell input swipe {x} {y} {x - distance} {y} {duration}"
    elif direction == "left":
        command = f"{adb_path} shell input swipe {x} {y} {x + distance} {y} {duration}"
    else:
        print(f"Invalid scroll direction: {direction}")
        return
    subprocess.run(command, capture_output=True, text=True, shell=True)



def drag(adb_path, x1, y1, x2, y2, duration=300):
    """
    模拟拖拽操作
    参数:
        adb_path: ADB 可执行文件路径
        x1, y1: 起始坐标
        x2, y2: 结束坐标
        duration: 拖拽持续时间（毫秒）
    """
    command = f"{adb_path} shell input swipe {x1} {y1} {x2} {y2} {duration}"
    subprocess.run(command, capture_output=True, text=True, shell=True)


def execute_action(action, adb_path):
    try:
        # 使用 ast 模块安全解析动作字符串
        node = ast.parse(action, mode='eval').body
        action_type = node.func.id
        kwargs = {}

        for keyword in node.keywords:
            key = keyword.arg
            value = ast.literal_eval(keyword.value)
            kwargs[key] = value

        def parse_box(box_str):
            match = re.search(r'\((\d+\.?\d*),\s*(\d+\.?\d*)\)', str(box_str))
            if match:
                x, y = float(match.group(1)), float(match.group(2))
                return x,y  # 转换为整数像素
            else:
                print(f"Invalid box format: {box_str}")
                return (0.0, 0.0)

        # 后续执行动作...
        if action_type == "click":
            box = parse_box(kwargs.get("start_box", [0, 0]))
            tap(adb_path, box[0], box[1])

        elif action_type == "long_press":
            box = parse_box(kwargs.get("start_box", [0, 0]))
            long_press(adb_path, box[0], box[1])

        elif action_type == "type":
            content = kwargs.get("content", "")
            type(adb_path, content)

        elif action_type == "scroll":
            box = parse_box(kwargs.get("start_box", [0, 0]))
            direction = kwargs.get("direction", "down")
            scroll(adb_path, box[0], box[1], direction)

        elif action_type == "drag":
            start = parse_box(kwargs.get("start_box", [0, 0]))
            end = parse_box(kwargs.get("end_box", [0, 0]))
            drag(adb_path, start[0], start[1], end[0], end[1])

        elif action_type == "press_home":
            home(adb_path)

        elif action_type == "press_back":
            back(adb_path)

        elif action_type == "finished":
            print("任务已完成:", kwargs.get("content", ""))
            return "STOP"
        elif action_type == "wait":
            duration = kwargs.get("duration", 2)
            time.sleep(duration)


        else:
            print(f"Unknown action type: {action_type}")

        time.sleep(2)
        return None

    except Exception as e:
        print(f"Error executing action: {action}, Error: {e}")
        return None