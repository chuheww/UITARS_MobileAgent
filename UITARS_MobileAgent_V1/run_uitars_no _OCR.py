import os
import time
import copy
import torch
import shutil
from PIL import Image, ImageDraw

from MobileAgent.api import inference_chat
from MobileAgent.text_localization import ocr
from MobileAgent.icon_localization import det
from MobileAgent.controller import get_screenshot, tap, slide, type, back, home,drag,scroll,long_press,execute_action
from MobileAgent.prompt import get_reflect_prompt, get_memory_prompt, get_process_prompt,get_action_prompt_uitars
from MobileAgent.chat import init_action_chat, init_reflect_chat, init_memory_chat, add_response, add_response_two_image

from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
from modelscope import snapshot_download, AutoModelForCausalLM, AutoTokenizer, GenerationConfig

from dashscope import MultiModalConversation
import dashscope
import concurrent

import re
from codes.utils import parse_action_to_structure_output,parsing_response_to_pyautogui_code,convert_coordinates
import ast

####################################### Edit your Setting #########################################
# Your ADB path
adb_path = "/home/hello/ww/android_sdk/platform-tools/adb"

# Your instruction
instruction = "Open 酷我音乐, search for song: 天下,and then play the song"

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

# You can add operational knowledge to help Agent operate more accurately.
add_info = "If you want to tap an icon of an app, use the action \"Open app\". If you want to exit an app, use the action \"Home\""

# Reflection Setting: If you want to improve the operating speed, you can disable the reflection agent. This may reduce the success rate.
reflection_switch = False

# Memory Setting: If you want to improve the operating speed, you can disable the memory unit. This may reduce the success rate.
memory_switch = False
###################################################################################################


def get_all_files_in_folder(folder_path):
    file_list = []
    for file_name in os.listdir(folder_path):
        file_list.append(file_name)
    return file_list


def draw_coordinates_on_image(image_path, coordinates): # 在图片上绘制坐标点
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    point_size = 10
    for coord in coordinates:
        draw.ellipse((coord[0] - point_size, coord[1] - point_size, coord[0] + point_size, coord[1] + point_size), fill='red')
    output_image_path = './screenshot/output_image.png'
    image.save(output_image_path)
    return output_image_path


def crop(image, box, i): # 裁剪图片
    image = Image.open(image)
    x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
    if x1 >= x2-10 or y1 >= y2-10:
        return
    cropped_image = image.crop((x1, y1, x2, y2))
    cropped_image.save(f"./temp/{i}.jpg")


def generate_local(tokenizer, model, image_file, query):#生成response
    query = tokenizer.from_list_format([
        {'image': image_file},
        {'text': query},
    ])
    response, _ = model.chat(tokenizer, query=query, history=None)
    return response


def process_image(image, query):
    dashscope.api_key = qwen_api
    image = "file://" + image
    messages = [{
        'role': 'user',
        'content': [
            {
                'image': image
            },
            {
                'text': query
            },
        ]
    }]
    response = MultiModalConversation.call(model=caption_model, messages=messages)
    
    try:
        response = response['output']['choices'][0]['message']['content'][0]["text"]
    except:
        response = "This is an icon."
    
    return response


def generate_api(images, query):#生成response
    icon_map = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_image, image, query): i for i, image in enumerate(images)}
        
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            response = future.result()
            icon_map[i + 1] = response
    
    return icon_map


def merge_text_blocks(text_list, coordinates_list):#合并文本块
    merged_text_blocks = []
    merged_coordinates = []

    sorted_indices = sorted(range(len(coordinates_list)), key=lambda k: (coordinates_list[k][1], coordinates_list[k][0]))
    sorted_text_list = [text_list[i] for i in sorted_indices]
    sorted_coordinates_list = [coordinates_list[i] for i in sorted_indices]

    num_blocks = len(sorted_text_list)
    merge = [False] * num_blocks

    for i in range(num_blocks):
        if merge[i]:
            continue
        
        anchor = i
        
        group_text = [sorted_text_list[anchor]]
        group_coordinates = [sorted_coordinates_list[anchor]]

        for j in range(i+1, num_blocks):
            if merge[j]:
                continue

            if abs(sorted_coordinates_list[anchor][0] - sorted_coordinates_list[j][0]) < 10 and \
            sorted_coordinates_list[j][1] - sorted_coordinates_list[anchor][3] >= -10 and sorted_coordinates_list[j][1] - sorted_coordinates_list[anchor][3] < 30 and \
            abs(sorted_coordinates_list[anchor][3] - sorted_coordinates_list[anchor][1] - (sorted_coordinates_list[j][3] - sorted_coordinates_list[j][1])) < 10:
                group_text.append(sorted_text_list[j])
                group_coordinates.append(sorted_coordinates_list[j])
                merge[anchor] = True
                anchor = j
                merge[anchor] = True

        merged_text = "\n".join(group_text)
        min_x1 = min(group_coordinates, key=lambda x: x[0])[0]
        min_y1 = min(group_coordinates, key=lambda x: x[1])[1]
        max_x2 = max(group_coordinates, key=lambda x: x[2])[2]
        max_y2 = max(group_coordinates, key=lambda x: x[3])[3]

        merged_text_blocks.append(merged_text)
        merged_coordinates.append([min_x1, min_y1, max_x2, max_y2])

    return merged_text_blocks, merged_coordinates


def get_perception_infos(adb_path, screenshot_file):#获取感知信息
    get_screenshot(adb_path)
    
    width, height = Image.open(screenshot_file).size

    return width, height


### Load caption model ###
device = "cuda"
torch.manual_seed(1234)
if caption_call_method == "local":
    if caption_model == "qwen-vl-chat":
        model_dir = snapshot_download('qwen/Qwen-VL-Chat', revision='v1.1.0')
        model = AutoModelForCausalLM.from_pretrained(model_dir, device_map=device, trust_remote_code=True).eval()
        model.generation_config = GenerationConfig.from_pretrained(model_dir, trust_remote_code=True)
    elif caption_model == "qwen-vl-chat-int4":
        qwen_dir = snapshot_download("qwen/Qwen-VL-Chat-Int4", revision='v1.0.0')
        model = AutoModelForCausalLM.from_pretrained(qwen_dir, device_map=device, trust_remote_code=True,use_safetensors=True).eval()
        model.generation_config = GenerationConfig.from_pretrained(qwen_dir, trust_remote_code=True, do_sample=False)
    else:
        print("If you choose local caption method, you must choose the caption model from \"Qwen-vl-chat\" and \"Qwen-vl-chat-int4\"")
        exit(0)
    tokenizer = AutoTokenizer.from_pretrained(qwen_dir, trust_remote_code=True)
elif caption_call_method == "api":
    pass
else:
    print("You must choose the caption model call function from \"local\" and \"api\"")
    exit(0)


### Load ocr and icon detection model ###
# groundingdino_dir = snapshot_download('AI-ModelScope/GroundingDINO', revision='v1.0.0')
# groundingdino_model = pipeline('grounding-dino-task', model=groundingdino_dir,device='gpu')
# ocr_detection = pipeline(Tasks.ocr_detection, model='damo/cv_resnet18_ocr-detection-line-level_damo', device='gpu')
# ocr_recognition = pipeline(Tasks.ocr_recognition, model='damo/cv_convnextTiny_ocr-recognition-document_damo', device='gpu')


thought_history = []
summary_history = []
action_history = []
summary = ""
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



    prompt_action = get_action_prompt_uitars(instruction,  width, height,summary_history, action_history, summary, action, add_info, error_flag, completed_requirements, memory)
    chat_action = init_action_chat()
    chat_action = add_response("user", prompt_action, chat_action, screenshot_file)

    output_action = inference_chat(chat_action, 'ij5/uitars', API_url_uitars, token_uitars)

    ###修改部分
    #原来
    # thought = output_action.split("Thought")[-1].split("Action")[0].replace("\n", " ").replace(":", "").replace("  ", " ").strip()
    # summary = output_action.split("Operation")[-1].replace("\n", " ").replace("  ", " ").strip()
    # action = output_action.split("Action")[-1].split("Operation")[0].replace("\n", " ").replace("  ", " ").strip()
    #原来

    #修改
    thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:)", output_action, re.DOTALL)
    action_match = re.search(r"Action:\s*(.*?)(?=\n|$)", output_action, re.DOTALL)

    thought = thought_match.group(1).strip() if thought_match else ""
    action_pre = action_match.group(1).strip() if action_match else ""
    model_type = "qwen25vl"
    # model_type = "qwen2vl"
    mock_response_dict = parse_action_to_structure_output(action_pre, 1000, height, width,
                                                          model_type)
    parsed_pyautogui_code = parsing_response_to_pyautogui_code(mock_response_dict, height,
                                                               width)
    action = convert_coordinates(mock_response_dict,height, width, model_type=model_type)
    summary = thought   ##需要修改
    # 修改
    ##修改部分


    chat_action = add_response("assistant", output_action, chat_action)
    status = "#" * 50 + " Decision " + "#" * 50
    print(status)
    print(output_action)
    print('#' * len(status))
    
    if memory_switch:    #不使用
        prompt_memory = get_memory_prompt(insight)
        chat_action = add_response("user", prompt_memory, chat_action)
        output_memory = inference_chat(chat_action, 'gpt-4o', API_url, token)
        chat_action = add_response("assistant", output_memory, chat_action)
        status = "#" * 50 + " Memory " + "#" * 50
        print(status)
        print(output_memory)
        print('#' * len(status))
        output_memory = output_memory.split("### Important content ###")[-1].split("\n\n")[0].strip() + "\n"
        if "None" not in output_memory and output_memory not in memory:
            memory += output_memory

    # 执行动作
    stop_flag = execute_action(action, adb_path)
    if stop_flag == "STOP":
        break

    
    width, height = get_perception_infos(adb_path, screenshot_file)
    shutil.rmtree(temp_file)
    os.mkdir(temp_file)
    

    


    thought_history.append(thought)
    summary_history.append(summary)
    action_history.append(action)

    prompt_planning = get_process_prompt(instruction, thought_history, summary_history, action_history, completed_requirements, add_info)
    chat_planning = init_memory_chat()
    chat_planning = add_response("user", prompt_planning, chat_planning)
    output_planning = inference_chat(chat_planning, 'gpt-3.5-turbo', API_url, token)
    chat_planning = add_response("assistant", output_planning, chat_planning)
    status = "#" * 50 + " Planning " + "#" * 50
    print(status)
    print(output_planning)
    print('#' * len(status))
    completed_requirements = output_planning.split("### Completed contents ###")[-1].replace("\n", " ").strip()

