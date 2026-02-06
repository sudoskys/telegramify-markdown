def singleton(cls):
    """Singleton pattern decorator"""
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


class Symbol:
    def __init__(self):
        self.heading_level_1: str = "\N{PUSHPIN}"                   # 📌
        self.heading_level_2: str = "\N{PENCIL}"                    # ✏️
        self.heading_level_3: str = "\N{BOOKS}"                     # 📚
        self.heading_level_4: str = "\N{BOOKMARK}"                  # 🔖
        self.image: str = "\N{FRAME WITH PICTURE}"               # 🖼
        self.link: str = "\N{LINK SYMBOL}"                       # 🔗
        self.task_completed: str = "\N{WHITE HEAVY CHECK MARK}"  # ✅
        self.task_uncompleted: str = "\N{BALLOT BOX WITH CHECK}" # ☑️


@singleton
class RenderConfig:
    def __init__(self):
        self._markdown_symbol = Symbol()
        self._cite_expandable = True

    @property
    def markdown_symbol(self) -> Symbol:
        return self._markdown_symbol

    @property
    def cite_expandable(self) -> bool:
        return self._cite_expandable

    @cite_expandable.setter
    def cite_expandable(self, value: bool):
        self._cite_expandable = value


# Global accessor function for accessing the RenderConfig singleton
def get_runtime_config() -> RenderConfig:
    return RenderConfig()
