from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FlowerSymbol:
    flower: str
    symbol: str
    summary: str


@dataclass(frozen=True)
class LessonConfig:
    lesson_title: str
    subtitle: str
    preview_message: str
    preview_tip: str
    flower_symbols: list[FlowerSymbol]
    lotus_traits: list[str]
    question_guidance: list[str]
    reflection_prompt: str
    reflection_prompt_hint: str
    teacher_summary_template: str
    homework_template: str
    stage_names: list[str] = field(default_factory=list)


AilianShuoLesson = LessonConfig(
    lesson_title="《爱莲说》第二课时",
    subtitle="课堂互动 AI 助手",
    preview_message="课前已借助小猿学习机完成字词与翻译预习，请带着理解走进课文。",
    preview_tip="本节课将聚焦三种花的象征意义、作者态度与写作手法，并进一步思考“出淤泥而不染”的现实启示。",
    flower_symbols=[
        FlowerSymbol(
            flower="菊",
            symbol="隐逸者",
            summary="菊花常被视为远离尘俗、安于淡泊的人物代表。",
        ),
        FlowerSymbol(
            flower="牡丹",
            symbol="富贵者",
            summary="牡丹象征世人普遍追逐的富贵与显达，也折射趋炎附势的社会风气。",
        ),
        FlowerSymbol(
            flower="莲",
            symbol="君子",
            summary="莲象征品行高洁、不同流合污、内心正直的君子形象。",
        ),
    ],
    lotus_traits=[
        "出淤泥而不染，象征身处复杂环境却能坚守本心。",
        "濯清涟而不妖，象征品格清正、姿态端庄而不媚俗。",
        "中通外直，象征内心通达、行为正直。",
        "不蔓不枝，象征做人简净，不攀附、不旁逸。",
        "香远益清，象征美好品德影响深远。",
        "亭亭净植，可远观而不可亵玩，象征庄重自持、令人敬重。",
    ],
    question_guidance=[
        "可以围绕三种花的对比来提问，看看作者为什么要这样安排内容。",
        "可以围绕作者的态度来提问，比较他为什么赞美莲、又为什么写到菊和牡丹。",
        "可以围绕写作手法来提问，思考对比、衬托怎样服务文章主旨。",
        "可以把问题再问深一层，看看这些分析最后怎样落到“出淤泥而不染”上。",
    ],
    reflection_prompt="“出淤泥而不染”是莲最可贵的品质。但在现实生活中，有人认为“近墨者黑”，人很难不受环境影响。你更认同哪种观点？请结合自己的经历或见闻谈一谈。",
    reflection_prompt_hint="可以先表明你更认同哪一种观点，再结合经历或见闻说明理由，最后回到莲的品质。",
    teacher_summary_template=(
        "一、人物形象\n"
        "今天我们借助三种花，明确了菊代表隐逸者，牡丹代表追逐富贵者，莲代表品德高洁的君子。\n\n"
        "二、写作手法\n"
        "作者把三种花放在一起写，通过比较突出莲的高洁形象；其中既有衬托，也有对世俗风气的映照。\n\n"
        "三、核心主旨\n"
        "《爱莲说》借赞美莲花，表达作者洁身自好、不与世俗同流合污的精神追求，也提醒我们在现实生活中坚守原则。"
    ),
    homework_template=(
        "1. 背诵并默写《爱莲说》关键语句，尤其关注描写莲品质的句子。\n"
        "2. 结合自己的生活经历，写一段80至120字的小练笔：你如何理解“出淤泥而不染”？"
    ),
    stage_names=[
        "预习过渡",
        "课文理解",
        "学生问 AI",
        "AI 问学生",
        "教师总结",
    ],
)
