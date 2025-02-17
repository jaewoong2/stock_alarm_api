# services/log_service.py
from datetime import datetime


class LogService:
    def __init__(self):
        self.logs = []  # 메모리 내 로그 저장소

    def save_log(self, trade_info: dict):
        """
        trade_info에 타임스탬프를 추가하고 로그에 저장합니다.
        """
        trade_info["timestamp"] = datetime.utcnow().isoformat()
        self.logs.append(trade_info)

    def get_logs(self):
        """
        저장된 모든 로그를 반환합니다.
        """
        return self.logs
