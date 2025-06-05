from utils import parse_action_to_structure_output, parsing_response_to_pyautogui_code

if __name__ == '__main__':
    
    mock_response = f"""Thought: Click on the search bar at the top of the screen\nAction: left_single(start_box='(573,322')"""
    # mock_response = mock_response.replace("Thought:", "Action_Summary:")

    original_image_height = 1080
    original_image_width = 1920
    model_type = "qwen25vl"
    mock_response_dict = parse_action_to_structure_output(mock_response, 1000, original_image_height, original_image_width, model_type)
    parsed_pyautogui_code = parsing_response_to_pyautogui_code(mock_response_dict, original_image_height, original_image_width)
    print(parsed_pyautogui_code)