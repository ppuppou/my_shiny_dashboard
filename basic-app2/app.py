from shiny.express import input, ui, render
from shiny import App, reactive
ui.page_opts(title="적용버튼 사용하기", fillable=True)
ui.input_checkbox_group("fruits", "좋아하는 과일 선택:", ["사과", "바나나", "체리"])
ui.input_action_button("apply", "Apply")
# 사용자가 Apply를 눌렀을 때만 반영
applied_fruits = reactive.Value([])
@reactive.effect
@reactive.event(input.apply)
def _():
    applied_fruits.set(input.fruits())
@render.text
def selected_fruits():
    fruits = applied_fruits()
    return f"선택한 과일: {', '.join(fruits)}" if fruits else "선택된 과일이 없습니다."