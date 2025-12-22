try:
    import agents
    from agents import TResponseInputItem
    import typing
    
    print("TResponseInputItem:", TResponseInputItem)
    if hasattr(TResponseInputItem, "__args__"):
         print("Args:", TResponseInputItem.__args__)
except Exception as e:
    print(f"Error: {e}")
