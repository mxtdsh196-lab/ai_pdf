# 磨砂玻璃效果演示

> 磨砂玻璃必须压在内容上才看得出来。在白纸上它就是一块浅色矩形。

## 1. 默认参数（不传 grain）

::: fx frost
完全用默认值，颗粒应该肉眼可见
:::

## 2. 压在渐变上（真玻璃效果）

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 opacity=40
磨砂玻璃压在渐变上，下层色彩透上来
:::

## 3. 粗颗粒

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 opacity=45 grain=6
颗粒放大到 6pt，砂面感最重
:::

## 4. 细颗粒

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 opacity=40 grain=2
颗粒 2pt，更细腻
:::

## 5. 明亮配色

::: fx frost bg=gradient bg-c1=0EA5E9 bg-c2=F59E0B bg-angle=45 opacity=42
青橙渐变上的磨砂
:::

## 6. 深色配色

::: fx frost bg=gradient bg-c1=1E293B bg-c2=4C1D95 bg-angle=200 opacity=48
深色渐变上的磨砂，对比最明显
:::