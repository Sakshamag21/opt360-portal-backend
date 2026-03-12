

class Response:
    def __init__(self, success: bool, message: str, data: dict = None):
        self.success = success
        self.message = message
        self.data = data or {}

    def to_dict(self):
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data
        }
    
    @staticmethod
    def success(message: str, data: dict = None):
        return Response(True, message, data).to_dict()

    @staticmethod
    def error(message: str, data: dict = None):
        return Response(False, message, data).to_dict()