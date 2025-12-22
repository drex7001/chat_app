try:
    import openai.types.responses.response_input_item_param as module
    print("Module dir:", [x for x in dir(module) if "Input" in x])
    
    # Check for InputImage or similar
    if hasattr(module, "InputImageContentPart"):
        print("InputImageContentPart:", module.InputImageContentPart.__annotations__)
    
except Exception as e:
    print(f"Error: {e}")
