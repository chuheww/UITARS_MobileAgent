import base64
import requests

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def inference_chat_uitars(chat, model, api_url, token):
    headers = {
        "Content-Type": "application/json",
        'Accept': 'application/json',
        "Authorization": f"Bearer {token}"
    }

    data = {
        "model": model,
        "messages": [],
        "max_tokens": 2048,
        'temperature': 0.0,
        "seed": 1234
    }

    # for role, content in chat:
    #     data["messages"].append({"role": role, "content": content})

    for message in chat:
        data["messages"].append({
            "role": message["role"],
            "content": message["content"]
        })

    while True:
        try:
            res = requests.post(api_url, headers=headers, json=data)
            res_json = res.json()
            res_content = res_json['choices'][0]['message']['content']
        except:
            print("Network Error:")
            try:
                print(res.json())
            except:
                print("Request Failed")
        else:
            break
    
    return res_content


def inference_chat(chat, model, api_url, token):
    headers = {
        "Content-Type": "application/json",
        'Accept': 'application/json',
        "Authorization": f"Bearer {token}"
    }

    data = {
        "model": model,
        "messages": [],
        "max_tokens": 2048,
        'temperature': 0.0,
        "seed": 1234
    }

    for role, content in chat:
        data["messages"].append({"role": role, "content": content})

    # for message in chat:
    #     data["messages"].append({
    #         "role": message["role"],
    #         "content": message["content"]
    #     })

    while True:
        try:
            res = requests.post(api_url, headers=headers, json=data)
            res_json = res.json()
            res_content = res_json['choices'][0]['message']['content']
        except:
            print("Network Error:")
            try:
                print(res.json())
            except:
                print("Request Failed")
        else:
            break

    return res_content