좋아요. TradingView의 **슈퍼트렌드(Supertrend)** 가 매수/매도 신호를 내는 **정확한 로직**을 핵심만 딱 정리해 드릴게요.

# 핵심 개요

- **입력값**: `ATR 길이(atrLength)`와 `배수(multiplier)`. 기본은 많이들 10과 3을 씁니다. 슈퍼트렌드는 **ATR 기반 추세 추종 지표**입니다. ([TradingView][1])
- **밴드 계산**: 중심값 `hl2 = (high+low)/2`에서 ATR×배수를 더/빼 상·하단 기본 밴드를 만든 뒤, 이전 값과의 조건으로 “최종 밴드”를 갱신합니다(아래 수식). **종가가 밴드를 넘어서면 추세가 전환**되고 선의 위치/색이 바뀝니다. ([TradingView][2])
- **신호 원리**:

  - 종가가 슈퍼트렌드 선 **위로 마감 → 상승 추세로 전환(매수 측 시그널)**
  - 종가가 **아래로 마감 → 하락 추세로 전환(매도 측 시그널)**
    전환은 _바가 닫힐 때_ 확정하는 게 표준입니다. ([TradingView][2])

---

## 정확한 계산 로직(TradingView 공식)

1. 기본 밴드
   `hl2 = (high + low) / 2`
   `basicUpperBand = hl2 + multiplier × ATR`
   `basicLowerBand = hl2 - multiplier × ATR`

2. 최종 밴드(이전 값과 비교해 “끌고 가는” 방식)

```
upperBand = (basicUpperBand < upperBand[1] or close[1] > upperBand[1]) ? basicUpperBand : upperBand[1]
lowerBand = (basicLowerBand > lowerBand[1] or close[1] < lowerBand[1]) ? basicLowerBand : lowerBand[1]
```

3. 추세/선 결정

```
if ATR가 아직 계산 전 → 초기상태는 하락
else if superTrend[1] == upperBand[1]
    trend = close > upperBand ? 상승 : 하락
else
    trend = close < lowerBand ? 하락 : 상승

superTrend = (trend == 상승) ? lowerBand : upperBand
```

위 로직이 TradingView 헬프의 공식 정의입니다. ([TradingView][2])

---

## 매수·매도 신호가 뜨는 순간

- **매수(Buy)**: 직전 바까지 하락 추세(선이 캔들 위/빨강)였는데, 이번 바 **종가가 상단 밴드(upperBand)를 돌파**하며 추세가 **상승**으로 바뀌는 시점. 선이 \*\*가격 아래(초록)\*\*로 이동합니다. ([TradingView][2])
- **매도(Sell)**: 반대로 직전까지 상승 추세였는데 **종가가 하단 밴드(lowerBand) 밑으로 마감**하며 추세가 **하락**으로 전환될 때. 선이 \*\*가격 위(빨강)\*\*로 이동합니다. ([TradingView][2])

> 팁: 횡보장에선 잦은 전환(휩쏘)이 날 수 있어, **ATR 길이나 배수(multiplier)를 키우면** 민감도가 낮아져 신호가 덜 자주 뜹니다. ([TradingView][2])

---

## Pine Script로 구현/활용(내장 함수)

TradingView에는 내장 함수 `ta.supertrend()`가 있어서 **선 값과 방향을 동시에 반환**합니다. 보통 `direction`이 **상승=1, 하락=-1**으로 나오며, 방향 변화를 신호로 씁니다. ([offline-pixel.github.io][3], [Stack Overflow][4])

```pinescript
//@version=6
indicator("Simple Supertrend Signals", overlay=true)
factor    = input.float(3.0, "Factor", step=0.1)
atrLength = input.int(10, "ATR Length")

[st, dir] = ta.supertrend(factor, atrLength)

// 선 그리기
plot(st, color = dir == 1 ? color.green : color.red, linewidth=2)

// 전환 시점에 라벨(매수/매도) 표시
buySignal  = ta.change(dir) and dir == 1
sellSignal = ta.change(dir) and dir == -1
plotshape(buySignal,  title="Buy",  style=shape.triangleup,   location=location.belowbar, size=size.tiny)
plotshape(sellSignal, title="Sell", style=shape.triangledown, location=location.abovebar, size=size.tiny)
```

- `ta.supertrend()` 사용 예시와 시그니처는 여러 공식/준공식 자료에 동일하게 소개됩니다. (마이그레이션 가이드, 커뮤니티 예시 등) ([TradingView][5])
