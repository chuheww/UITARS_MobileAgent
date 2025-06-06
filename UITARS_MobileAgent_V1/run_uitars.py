import os
import time
import copy
import torch
import shutil
import re
import logging
import sys
from logging.handlers import RotatingFileHandler
from PIL import Image, ImageDraw

from MobileAgent.api import inference_chat,encode_image,inference_chat_uitars
from MobileAgent.text_localization import ocr
from MobileAgent.icon_localization import det
from MobileAgent.controller import get_screenshot, tap, slide, type, back, home,drag,scroll,long_press,execute_action
from MobileAgent.prompt import get_reflect_prompt, get_memory_prompt, get_process_prompt,get_action_prompt_uitars
from MobileAgent.chat import init_action_chat_uitars, init_reflect_chat, init_memory_chat, add_response_uitars, add_response_two_image,add_response,add_box_token

from modelscope import snapshot_download, AutoModelForCausalLM, AutoTokenizer, GenerationConfig

from dashscope import MultiModalConversation
import dashscope
import concurrent

from codes.utils import parse_action_to_structure_output,parsing_response_to_pyautogui_code,convert_coordinates

####################################### Edit your Setting #########################################
# Your ADB path
adb_path = "/home/hello/ww/android_sdk/platform-tools/adb"

# Your instruction
instruction = "在抖音中找到一个关于大熊猫的视频，转发给QQ的楚河"

# Your model
API_url_uitars = "http://127.0.0.1:8000/v1/chat/completions"

# Your model API Token
token_uitars = "uitars-secret-key"


# Your GPT-4o API URL
API_url = "https://model-bridge.okeeper.com//v1/chat/completions"

# Your GPT-4o API Token
token = "sk-zkdCgk67ewUdn0tcc1SY4fC62vLYCrG3Rd28D6TJwszl9OxVbbqy"

# Choose between "api" and "local". api: use the qwen api. local: use the local qwen checkpoint
caption_call_method = "api"

# Choose between "qwen-vl-plus" and "qwen-vl-max" if use api method. Choose between "qwen-vl-chat" and "qwen-vl-chat-int4" if use local method.
caption_model = "qwen-vl-plus"

# If you choose the api caption call method, input your Qwen api here
qwen_api = "sk-8bbc5ee5baa848a297b4b719a343a63e"

###################################################################################################

def get_perception_infos(adb_path, screenshot_file):#获取感知信息
    get_screenshot(adb_path)
    width, height = Image.open(screenshot_file).size

    return width, height



# 配置日志记录器
logger = logging.getLogger('UITARS')
logger.setLevel(logging.INFO)

# 文件处理器（UTF-8 + 日志轮转）
file_handler = RotatingFileHandler(
    'uitars.log',
    maxBytes=1024*1024*10,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)

# 控制台处理器（可选）
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# 日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

### Load caption model ###
device = "cuda"
torch.manual_seed(1234)


thoughts = []
actions = []
history_images = []
history_responses = []
history_n = 5

max_pixels = 16384 * 28 * 28
min_pixels = 100 * 28 * 28

action = ""
completed_requirements = ""
memory = ""
insight = ""
temp_file = "temp"
screenshot = "screenshot"
if not os.path.exists(temp_file):
    os.mkdir(temp_file)
else:
    shutil.rmtree(temp_file)
    os.mkdir(temp_file)
if not os.path.exists(screenshot):
    os.mkdir(screenshot)
error_flag = False


iter = 0
while True:
    iter += 1
    if iter == 1:
        screenshot_file = "./screenshot/screenshot.jpg"
        width, height = get_perception_infos(adb_path, screenshot_file)
        shutil.rmtree(temp_file)
        os.mkdir(temp_file)

    ##uitars-messages 构建
    base64_image = encode_image(screenshot_file)
    history_images.append(base64_image)

    messages, images = [], []
    if len(history_images) > history_n:
        history_images = history_images[-history_n:]

    if isinstance(history_images, list):
        pass
    else:
        raise TypeError(f"Unidentified images type: {type(history_images)}")

    for turn, image in enumerate(history_images):
        images.append(image)

    image_num = 0
    if len(history_responses) > 0:
        for history_idx, history_response in enumerate(history_responses):
            # send at most history_n images to the model
            if history_idx + history_n > len(history_responses):
                encoded_string = images[image_num]
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}"}}]
                })
                image_num += 1

                messages.append({
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": add_box_token(history_response)}
                    ]
                })

        encoded_string = images[image_num]
        messages.append({
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}"}}]
        })
        image_num += 1

    else:
        encoded_string = images[image_num]
        messages.append({
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}"}}]
        })
        image_num += 1

    chat_action_init = init_action_chat_uitars(instruction)
    chat_action = add_response_uitars(chat_action_init, messages)

    output_action = inference_chat_uitars(chat_action, 'ij5/uitars', API_url_uitars, token_uitars)
    history_responses.append(output_action)

    thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:)", output_action, re.DOTALL)
    action_match = re.search(r"Action:\s*(.*?)(?=\n|$)", output_action, re.DOTALL)

    thought = thought_match.group(1).strip() if thought_match else ""
    thoughts.append(thought)
    action_pre = action_match.group(1).strip() if action_match else ""
    model_type = "qwen25vl"
    # model_type = "qwen2vl"
    mock_response_dict = parse_action_to_structure_output(action_pre, 1000, height, width,model_type)
    parsed_pyautogui_code = parsing_response_to_pyautogui_code(mock_response_dict, height,width)
    action = convert_coordinates(mock_response_dict,height, width, model_type=model_type)
    actions.append(action)

    status = "#" * 10 + " 推理 " + "#" * 10
    logger.info(f"\n{status}\n{output_action}\n{'#' * len(status)}\n")

    # 执行动作
    stop_flag = execute_action(action, adb_path)
    if stop_flag == "STOP":
        break

    last_screenshot_file = "./screenshot/last_screenshot.jpg"
    if os.path.exists(last_screenshot_file):
        os.remove(last_screenshot_file)
    os.rename(screenshot_file, last_screenshot_file)
    
    width, height = get_perception_infos(adb_path, screenshot_file)
    shutil.rmtree(temp_file)
    os.mkdir(temp_file)

    # prompt_planning = get_process_prompt(instruction, thoughts, thoughts, actions, completed_requirements, add_info)
    # chat_planning = init_memory_chat()
    # chat_planning = add_response("user", prompt_planning, chat_planning)
    # output_planning = inference_chat(chat_planning, 'gpt-3.5-turbo', API_url, token)
    # chat_planning = add_response("assistant", output_planning, chat_planning)
    # status = "#" * 50 + " Planning " + "#" * 50
    # print(status)
    # print(output_planning)
    # print('#' * len(status))
    # completed_requirements = output_planning.split("### Completed contents ###")[-1].replace("\n", " ").strip()
    #
    os.remove(last_screenshot_file)
