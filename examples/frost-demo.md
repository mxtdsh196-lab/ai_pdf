# 磨砂玻璃效果演示

> 配方来自 css.glass / Zero-Style 玻璃拟态规范：**白色半透明层 + 背景模糊 + 细白边**，不带颗粒。
> 关键是「背景被揉化」而不是「叠噪点」——后者是纱窗，不是玻璃。

## 1. 标准玻璃（紫粉背景）

::: fx frost bg=gradient bg-c1=7C3AED bg-c2=EC4899 bg-angle=120 opacity=20
磨砂玻璃压在紫粉渐变上，下层色彩被揉化后透上来，文字保持清晰
:::

## 2. 蓝色玻璃

::: fx frost bg=gradient bg-c1=2547A8 bg-c2=0EA5E9 bg-angle=135 opacity=20
蓝青渐变上的磨砂玻璃
:::

## 3. 玻璃再实一点

::: fx frost bg=gradient bg-c1=7C3AED bg-c2=EC4899 bg-angle=120 opacity=35
opacity=35，玻璃层更白更实，背景更淡
:::

## 4. 玻璃再透一点

::: fx frost bg=gradient bg-c1=7C3AED bg-c2=EC4899 bg-angle=120 opacity=12
opacity=12，几乎全透，只看得到淡淡的雾
:::

## 5. 绿橙玻璃

::: fx frost bg=gradient bg-c1=10B981 bg-c2=F59E0B bg-angle=45 opacity=22
绿橙渐变上的磨砂
:::

## 6. 深色玻璃

::: fx frost bg=gradient bg-c1=1E293B bg-c2=4C1D95 bg-angle=200 opacity=25
深色渐变上的磨砂，边缘高光最明显
:::

## 7. 白纸上（没有背景参照）

::: fx frost
白纸上没有东西可透，只有一层淡雾——这是正常的，玻璃需要参照物
:::