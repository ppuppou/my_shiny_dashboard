from shiny import render, ui
from shiny.express import input

ui.panel_title("Hello Shiny!")
ui.input_slider("n", "N을 입력해주세요", 0, 100, 20)
ui.input_selectize(
    "var", "옵션을 선택해주세요",
    choices=["bill_length_mm", "body_mass_g"]
)

@render.text
def txt():
    return f"입력받은 숫자의 2배는 {input.n() * 2} 입니다."

@render.text
def txt2():
    return f"선택하신 옵션은 {input.var()} 입니다."

@render.plot
def hist():
    from matplotlib import pyplot as plt
    from palmerpenguins import load_penguins
    df = load_penguins()
    df[input.var()].hist(grid=False)
    plt.xlabel(input.var())
    plt.ylabel("count")