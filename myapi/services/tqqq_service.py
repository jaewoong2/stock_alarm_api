import datetime
import math
import numpy as np
import requests
import yfinance as yf

from myapi.utils.config import Settings

DATA_RANGE_DAYS = 400


class TqqqService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_data(self):
        """
        yfinance를 사용하여 TQQQ의 데이터를 다운로드하고, 종가 리스트, 현재 가격,
        마지막 데이터의 타임스탬프(시장 시간)를 반환합니다.
        """
        ticker = "TQQQ"
        # 400일간의 데이터를 받아 200일 SMA 계산에 충분한 데이터를 확보합니다.
        data = yf.download(ticker, period="400d", interval="1d")

        if data is None:
            raise ValueError("데이터를 불러올 수 없습니다.")

        if data.empty:
            raise ValueError("데이터를 불러올 수 없습니다.")

        # 'Close' 컬럼이 Series 형태인지 확인 후 리스트로 변환
        # 만약 Series가 아니라면 values 속성을 사용하여 변환합니다.
        closes = data["Close"].values.tolist()
        current_price = closes[-1]

        # pandas Timestamp 객체를 UNIX 타임스탬프로 변환 (초 단위)
        market_time = data.index[-1].timestamp()

        return {
            "closes": closes,
            "currentPrice": current_price,
            "marketTime": market_time,
        }

    def fetch_data_api(self):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/TQQQ?range={DATA_RANGE_DAYS}d&interval=1d"
        response = requests.get(url, headers={"User-Agent": "curl/7.68.0"})
        response.raise_for_status()
        json_data = response.json()

        result = json_data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        meta = result["meta"]
        current_price = meta["regularMarketPrice"]
        # 마지막 종가를 현재 가격으로 갱신
        closes[-1] = current_price
        market_time = meta["regularMarketTime"]
        return {
            "closes": closes,
            "currentPrice": current_price,
            "marketTime": market_time,
        }

    def compute_moving_average(self, data, window):
        """
        data 리스트에 대해 period 기간의 단순 이동평균을 계산하여 리스트로 반환합니다.
        데이터가 부족한 앞부분은 NaN으로 채웁니다.
        """
        return [
            np.mean(data[i - window : i]) if i >= window else np.nan
            for i in range(1, len(data) + 1)
        ]

    def compute_envelope(self, ma_series, factor=1.1):
        """
        이동평균 시리즈의 각 값에 factor를 곱한 envelope 시리즈를 반환합니다.
        NaN인 값은 그대로 NaN 처리합니다.
        """
        envelope = [
            val * factor if not math.isnan(val) else float("nan") for val in ma_series
        ]
        return envelope

    def adjust_to_friday(self, date):
        """
        전달받은 datetime 객체가 토요일이나 일요일이면 금요일 날짜로 조정하여 반환합니다.
        (Python에서는 Monday=0 ... Sunday=6)
        """
        weekday = date.weekday()
        if weekday == 5:  # Saturday
            return date - datetime.timedelta(days=1)
        elif weekday == 6:  # Sunday
            return date - datetime.timedelta(days=2)
        return date

    def get_latest_value(self, series):
        """
        주어진 시리즈에서 뒤에서부터 첫 번째로 NaN이 아닌 값을 반환합니다.
        """
        for val in reversed(series):
            if not math.isnan(val):
                return val
        return float("nan")

    def generate_recommendation(
        self, current_price, latest_ma, latest_envelope, layout="medium"
    ):
        """
        현재 가격과 200일 MA, envelope 값을 바탕으로 매매 추천 문구를 반환합니다.
        layout에 따라 medium과 large에서 출력 문구가 약간 다릅니다.
        """
        if current_price > latest_envelope:
            return "SPLG 매수"
        elif latest_ma < current_price <= latest_envelope:
            return "TQQQ 매수"
        else:  # current_price <= latest_ma
            return "TQQQ, SPLG 풀매도 / BIL 풀매수"

    def display_stats(self, current_price, latest_envelope, latest_ma):
        """
        현재 가격, envelope 상한, 200일 MA 통계 정보를 콘솔에 출력합니다.
        """
        result = {}

        if isinstance(current_price, list):
            result["current_price"] = f"현재 종가: ${current_price[0]:.2f}"
        else:
            result["current_price"] = f"현재 종가: ${current_price:.2f}"

        result["latest_envelope"] = f"Envelope 상한: ${latest_envelope:.2f}"
        result["latest_ma"] = f"200일 MA: ${latest_ma:.2f}"

        return result

    def get_actions(self):
        data = self.fetch_data_api()
        closes = data["closes"]
        current_price = data["currentPrice"]
        market_time = data["marketTime"]

        # 200일 이동평균과 envelope 계산
        ma200 = self.compute_moving_average(closes, 200)
        envelope = self.compute_envelope(ma200, factor=1.1)

        # 마지막 시장 날짜를 금요일 기준으로 조정
        market_date = datetime.datetime.fromtimestamp(market_time)
        market_date_friday = self.adjust_to_friday(market_date)
        formatted_date = market_date_friday.strftime("%y/%m/%d")

        # 헤더 정보 출력
        print(f"TQQQ 200일선 매매법 ({formatted_date} 본장 기준)")

        # 최신 MA와 envelope 값 얻기
        latest_ma = self.get_latest_value(ma200)
        latest_envelope = latest_ma * 1.1 if not math.isnan(latest_ma) else float("nan")

        # 매매 추천 문구 생성 및 출력
        recommendation = self.generate_recommendation(
            current_price, latest_ma, latest_envelope
        )

        result = self.display_stats(current_price, latest_envelope, latest_ma)

        result["recommendation"] = recommendation

        # 통계 정보 출력
        return result

    def recommend_to_message(self, message):
        text_message = (
            "📊 TQQQ 200일선 매매법 주식 정보 (네이버 금융)\n\n"
            f"💰 현재 종가: {message['current_price'].replace('현재 종가: ', '')}\n"
            f"📏 Envelope 상한: {message['latest_envelope'].replace('Envelope 상한: ', '')}\n"
            f"📉 200일 MA: {message['latest_ma'].replace('200일 MA: ', '')}\n\n"
            f"✅ 추천: {message['recommendation']}\n\n"
            "🔗 [네이버 금융 보기](https://m.stock.naver.com/worldstock/etf/TQQQ.O/total)"
        )

        return text_message
