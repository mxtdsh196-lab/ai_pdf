# 磨砂玻璃效果演示

> 真磨砂玻璃的关键是「透过它看到的东西是模糊的」。只叠颗粒和半透明白层是假的。

## 1. 默认（背景模糊 + 颗粒）

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 opacity=22
磨砂玻璃压在渐变上，下层色彩被揉化后透上来
:::

## 2. 模糊更强的背景

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 bg-blur=4 opacity=188 opacity=26
bg-blur=48，背景糊得更彻底，像浴室玻璃
:::

## 3. 几乎不模糊（对照）

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 bg-blur=4 opacity=18
bg-blur=4，能看清底下渐变的形状，磨砂感最弱
:::

## 4. 粗颗粒

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 opacity=26 grain=7 grain-a=50
颗粒 7pt，砂面质感最重
:::

## 5. 细颗粒

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 opacity=20 grain=2
颗粒 2pt，接近宣纸
:::

## 6. 深色底

::: fx frost bg=gradient bg-c1=1E293B bg-c2=4C1D95 bg-angle=200 opacity=30
深色渐变上的磨砂，对比最明显
:::

## 7. 明亮配色

::: fx frost bg=gradient bg-c1=0EA5E9 bg-c2=F59E0B bg-angle=45 opacity=24
青橙渐变上的磨砂
:::