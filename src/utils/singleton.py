import threading
from functools import wraps


def singleton(cls):
    """
    类装饰器：将一个类变成单例类

    使用示例:
        @singleton
        class MyClass:
            pass

        obj1 = MyClass()
        obj2 = MyClass()
        assert obj1 is obj2  # True
    """
    instances = {}
    lock = threading.Lock()

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            with lock:
                if cls not in instances:
                    instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
