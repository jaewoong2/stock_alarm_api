# Define a custom exception for your service
class ServiceException(Exception):
    def __init__(self, name: str, detail: str):
        self.name = name
        self.detail = detail
