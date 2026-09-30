import json, pathlib, re

ISO = json.loads(pathlib.Path("/tmp/iso.json").read_text())
OUT = pathlib.Path("/tmp/claude-0/-home-claude/0d0e2ed4-36a7-5572-b68c-9454ae6c8f69/scratchpad/deck/project/slides")
OUT.mkdir(parents=True, exist_ok=True)

BG, PANEL, LINE = "#FFFFFF", "#F5F7FB", "#DCE2EC"
INK, INK2, MUTED = "#16223A", "#46536B", "#7C8AA0"
BLUE, OCHRE = "#2C6CB0", "#C0762A"
EXTRUDE = "#E6EBF3"
SANS = "'IBM Plex Sans', Arial, sans-serif"
SERIF = "'Source Serif 4', Georgia, serif"

IMG = {
    "employment_sex": "/_blob/61c06428f3955e36eb20ea18b19c8346",
    "employment_age": "/_blob/e66471f6bbd8d3912ba04a0a1ad9029f",
    "employment_region": "/_blob/aec0bd174d49eac412e1b46754718d26",
    "informality": "/_blob/d784dcd1503107fce7a2166166a28dc4",
    "urban_rural": "/_blob/7019f32dbd372e78d5661de2b6102fdf",
    "household_types": "/_blob/f5c4edeff197348a367a215fc3da7f1b",
    "savings_gap": "/_blob/e8506e3952a83d76cb541cadb49be628",
    "completeness": "/_blob/c4f690dd2ffb916acab4f97764873343",
}
LABELS = json.loads(pathlib.Path("/tmp/iso_labels.json").read_text())

def iso(name, w, h):
    """Встроенный SVG, отмасштабированный под слайд (viewBox тянет содержимое)."""
    svg = ISO[name]
    svg = re.sub(r'width="\d+" height="\d+"', f'width="{w}" height="{h}"', svg, count=1)
    return svg


GRID = (f'<div style="position:absolute;left:0;top:0;width:1920px;height:1080px;overflow:hidden">'
        f'{ISO["grid"]}</div>')


def section(sid, body, notes, pad="128px 128px 160px", transition="fade"):
    return (f'<section id="{sid}" data-transition="{transition}" '
            f'style="background:{BG};color:{INK};font-family:{SANS};padding:{pad};'
            f'display:flex;flex-direction:column;gap:32px">{GRID}{body}'
            f'<aside>{notes}</aside></section>')


def head(title, sub):
    return (f'<div style="display:flex;flex-direction:column;gap:10px">'
            f'<h2 style="font-family:{SERIF};font-size:62px;font-weight:600;line-height:1.1;'
            f'color:{INK}">{title}</h2>'
            f'<p style="font-size:27px;color:{MUTED}">{sub}</p></div>')


def card(title, text, accent=BLUE, flex="1", width=None, title_size=26, text_size=23):
    w = f"width:{width};" if width else f"flex:{flex};"
    return (f'<div style="{w}display:flex;flex-direction:column;gap:10px;background:{PANEL};'
            f'padding:26px;border:1px solid {LINE};border-left:6px solid {accent};'
            f'border-radius:4px;box-shadow:12px 12px 0 {EXTRUDE}">'
            f'<h3 style="font-size:{title_size}px;font-weight:600;color:{accent}">{title}</h3>'
            f'<p style="font-size:{text_size}px;line-height:1.42;color:{INK2}">{text}</p></div>')


def stat(value, label, accent=INK, flex="1"):
    return (f'<div style="flex:{flex};display:flex;flex-direction:column;gap:8px;background:{PANEL};'
            f'padding:26px;border:1px solid {LINE};border-radius:4px;'
            f'box-shadow:12px 12px 0 {EXTRUDE}">'
            f'<p style="font-family:{SERIF};font-size:44px;font-weight:600;color:{accent}">{value}</p>'
            f'<p style="font-size:22px;line-height:1.35;color:{INK2}">{label}</p></div>')


def img(key, w, h, alt, extra=""):
    return (f'<img src="{IMG[key]}" alt="{alt}" style="width:{w}px;height:{h}px;'
            f'object-fit:contain;{extra}">')


def foot(text):
    return (f'<p style="position:absolute;left:128px;bottom:64px;font-size:23px;'
            f'color:{MUTED}">{text}</p>')


def write(sid, html):
    (OUT / f"{sid}.html").write_text(html, encoding="utf-8")
    print(f"{sid}.html  {len(html)} символов")


# ── 1. Обложка ────────────────────────────────────────────────────────────────
kpi = "".join([
    stat("236", "таблиц в 8 формах"),
    stat("72,6 млн", "строк обработано полностью"),
    stat("4,68 ГБ → 300 МБ", "CSV → parquet, сжатие в 16 раз", BLUE),
    stat("48 000 × 37", "объединённая таблица домохозяйств"),
])
cover = (
    f'{GRID}'
    f'<div style="position:absolute;right:96px;top:142px;width:760px;height:652px">{iso("cover_stack", 760, 652)}</div>'
    f'<div style="position:absolute;left:128px;top:128px;width:980px;display:flex;'
    f'flex-direction:column;gap:20px">'
    f'<p style="font-size:25px;font-weight:500;letter-spacing:3px;text-transform:uppercase;'
    f'color:{BLUE}">STAT.DATATHON-2026 &middot; Результат 1</p>'
    f'<h1 style="font-family:{SERIF};font-size:92px;font-weight:600;line-height:1.06;'
    f'color:{INK}">Дескриптивная аналитика датасетов</h1>'
    f'<p style="font-size:30px;line-height:1.4;color:{INK2}">Синтетические микроданные '
    f'БНС АСПР РК, 2021–2024</p></div>'
    f'<div style="position:absolute;left:128px;top:560px;width:1664px;display:flex;gap:26px">{kpi}</div>'
    f'<div style="position:absolute;left:128px;bottom:96px;width:1664px;display:flex;'
    f'justify-content:space-between;align-items:end;border-top:1px solid {LINE};padding:26px 0 0">'
    f'<div style="display:flex;flex-direction:column;gap:8px">'
    f'<p style="font-size:31px;font-weight:600;color:{INK}">Команда «Котлы чудес»</p>'
    f'<p style="font-size:25px;color:{INK2}">Арнас Жаксаликов &middot; Аружан Болат</p></div>'
    f'<p style="font-size:25px;color:{MUTED}">30 сентября 2026</p></div>'
)
write("cover", f'<section id="cover" data-transition="fade" style="background:{BG};color:{INK};'
                f'font-family:{SANS};padding:128px">{cover}'
                f'<aside>Мы обработали весь архив целиком, а не выборку: 236 таблиц, 72,6 миллиона '
                f'строк. Первым шагом перевели данные в parquet со сжатием — объём упал с 4,68 '
                f'гигабайт до 300 мегабайт, и после этого любой запрос по самой большой форме '
                f'отрабатывает за секунды на обычном ноутбуке. Главный результат подготовительного '
                f'этапа — объединённая таблица домохозяйств: 48 тысяч строк, 37 признаков, собранная '
                f'из четырёх форм обследования. Весь код и все графики этой презентации '
                f'воспроизводятся из репозитория одной командой.</aside></section>')

# ── 2. Состав архива ──────────────────────────────────────────────────────────
rows = [
    ("1t_god", "предприятие × показатель, год", "30 025 899", "4"),
    ("1t_kv", "то же, поквартально", "24 480 242", "16"),
    ("d004", "покупка или доход домохозяйства", "8 612 484", "192"),
    ("2t", "предприятие × показатель, оплата труда", "7 328 814", "4"),
    ("t001", "респондент обследования занятости", "1 885 110", "4"),
    ("d008", "член домохозяйства", "169 059", "4"),
    ("d002", "домохозяйство, субъективные оценки", "95 542", "8"),
    ("d006", "домохозяйство, жильё и благоустройство", "46 743", "4"),
]
ZEBRA = ' style="background:#F5F7FB"'
trs = "".join(
    f'<tr{"" if i % 2 else ZEBRA}>'
    f'<td style="font-weight:600;color:{BLUE}">{a}</td><td>{b}</td>'
    f'<td style="text-align:right">{c}</td><td style="text-align:right">{d}</td></tr>'
    for i, (a, b, c, d) in enumerate(rows))
table = (
    f'<table style="font-family:{SANS};font-size:24px;color:{INK2};padding:11px 16px">'
    f'<tr style="background:{PANEL}">'
    f'<th style="width:13%;text-align:left;font-size:22px;font-weight:600;color:{INK}">Форма</th>'
    f'<th style="width:45%;text-align:left;font-size:22px;font-weight:600;color:{INK}">Единица наблюдения</th>'
    f'<th style="width:22%;text-align:right;font-size:22px;font-weight:600;color:{INK}">Строк</th>'
    f'<th style="width:20%;text-align:right;font-size:22px;font-weight:600;color:{INK}">Файлов</th>'
    f'</tr>{trs}</table>')
steps = "".join(
    f'<p style="flex:1;font-size:22px;line-height:1.3;color:{INK2};text-align:center">{t}</p>'
    for t in ["parquet", "рынок труда", "мердж", "анализ", "графики"])
body = (
    head("Что в архиве", "Восемь форм с разными единицами наблюдения: от предприятия до члена домохозяйства")
    + table
    + f'<div style="display:flex;gap:36px;align-items:center">'
      f'<div style="width:1000px;display:flex;flex-direction:column;gap:6px">'
      f'<div style="width:1000px;height:182px">{iso("pipeline", 1000, 182)}</div>'
      f'<div style="display:flex;width:1000px">{steps}</div></div>'
    + card("Длинный формат", "30 млн строк в 1-Т — это не 30 млн предприятий, а 52 289: "
           "одна строка равна одному значению показателя.", BLUE, width="628px")
    + '</div>'
    + foot("Источник: synthetic_microdata_2021-2024_20260921 &middot; значения посчитаны на полном архиве")
)
write("data", section("data", body,
      "Первое, на что стоит обратить внимание — единица наблюдения у форм разная. Формы предприятий "
      "записаны в длинном формате: одна строка это одно значение одного показателя, поэтому тридцать "
      "миллионов строк годовой формы 1-Т — это всего пятьдесят две тысячи предприятий. Обследования "
      "домохозяйств устроены иначе, там строка это человек или покупка."))

# ── 3. Объединённая таблица ───────────────────────────────────────────────────
forms = [
    card("d008", "состав: размер, дети, пожилые, занятые, глава", BLUE, title_size=25, text_size=22),
    card("d006", "жильё: площадь, 42 удобства, 46 предметов ДП, земля", BLUE, title_size=25, text_size=22),
    card("d004", "деньги: доходы по 23 источникам, расходы по 7 блокам", BLUE, title_size=25, text_size=22),
    card("d002", "субъективные оценки условий жизни по шкалам", BLUE, title_size=25, text_size=22),
]
body = (
    head("Объединённая таблица домохозяйств", "Четыре формы D-серии сходятся по ключу NOMER без потерь")
    + f'<div style="display:flex;gap:44px;align-items:start">'
      f'<div style="width:700px;height:520px;overflow:hidden">{ISO["merge"]}</div>'
      f'<div style="width:920px;display:flex;flex-direction:column;gap:20px">'
      f'<div style="display:flex;gap:18px">{forms[:len(forms)//2]}</div>'
      f'<div style="display:flex;gap:18px">{forms[len(forms)//2:]}</div>'
      f'<div style="display:flex;gap:18px">'
      + stat("48 000 × 37", "12 000 домохозяйств × 4 года, «сирот» при соединении нет", OCHRE)
      + stat("11 704 / 11 931 / 11 958", "нашлись в жилищной, субъективной и денежной форме", INK)
      + '</div></div></div>'
    + foot("Панели между годами нет: номера домохозяйств перевыдаются, совпадение региона 5,4% при случайном уровне 5%")
)
write("merged", section("merged", body,
      "Это ядро всей дальнейшей работы. Четыре формы обследования домохозяйств связываются по ключу "
      "NOMER абсолютно чисто: ни одного домохозяйства не потерялось и ни одного лишнего не появилось. "
      "На выходе — сорок восемь тысяч строк и тридцать семь признаков, включая производные. Важное "
      "ограничение: панели между годами нет, номера перевыдаются каждый год."))

# ── 4. Заполненность и дрейф ──────────────────────────────────────────────────
drift = [("Колонка со значением", "GR1", "VAL_NUM"), ("Колонка региона", "KATO", "KATO1"),
         ("Колонок в 1-Т годовой", "16", "30"), ("Кодов ОКЭД", "83", "539"),
         ("Регионов в выборке", "17", "20"), ("Предприятий в 1-Т", "70 874", "52 289")]
dtrs = "".join(
    f'<tr{"" if i % 2 else ZEBRA}><td>{a}</td>'
    f'<td style="text-align:right">{b}</td>'
    f'<td style="text-align:right;color:{OCHRE};font-weight:600">{c}</td></tr>'
    for i, (a, b, c) in enumerate(drift))
body = (
    head("Заполненность и дрейф схемы", "Разреженность анкет — норма, а вот смена схемы ломает код")
    + f'<div style="display:flex;gap:44px;align-items:start">'
    + img("completeness", 1000, 477, "Заполненность десяти самых разреженных таблиц")
    + f'<div style="width:620px;display:flex;flex-direction:column;gap:16px">'
      f'<h3 style="font-size:26px;font-weight:600;color:{INK}">Что меняется между годами</h3>'
      f'<table style="font-family:{SANS};font-size:22px;color:{INK2};padding:10px 13px">'
      f'<tr style="background:{PANEL}">'
      f'<th style="width:50%;text-align:left;font-size:21px;font-weight:600;color:{INK}">Признак</th>'
      f'<th style="width:25%;text-align:right;font-size:21px;font-weight:600;color:{INK}">2021</th>'
      f'<th style="width:25%;text-align:right;font-size:21px;font-weight:600;color:{INK}">2024</th>'
      f'</tr>{dtrs}</table>'
      f'<p style="font-size:22px;line-height:1.4;color:{MUTED}">Рост с 17 до 20 регионов — реформа '
      f'2022 года: Абай, Жетісу, Ұлытау. Падение числа предприятий — смена охвата выгрузки.</p></div></div>'
    + foot("Отдельная ловушка: T-001 за 2022, строка 26332 — запятая внутри кавычек ломает автоопределение парсера")
)
write("quality", section("quality", body,
      "Слева заполненность таблиц. Треть непустых ячеек у формы d006 это не ошибка: в анкете с "
      "ветвлениями респондент просто не отвечает на неприменимые вопросы. Справа то, что ломает "
      "наивный код: колонка со значением переименована, код региона сменил разрядность, классификатор "
      "ОКЭД стал детальнее в шесть раз."))

# ── 5. Аномалия ───────────────────────────────────────────────────────────────
body = (
    head("Аномалия генератора", "Один регион искажает национальный показатель неформальной занятости вдвое")
    + f'<div style="display:flex;gap:40px;align-items:start">'
    + img("informality", 1120, 496, "Скачок доли работающих без договора в Алматинской области")
    + f'<div style="width:504px;display:flex;flex-direction:column;gap:18px">'
    + card("Что мы увидели", "Алматинская область: 6,3 → 5,4 → 4,8 → <b>40,7%</b>. База ответов при "
           "этом стабильна — около 13 тысяч заполненных значений.", OCHRE, title_size=25, text_size=22)
    + card("Что это значит", "Без этого региона ряд по стране ровный: 3,2 / 3,3 / 2,9 / <b>3,0%</b>. "
           "Скачок — сбой генератора, а не экономика.", BLUE, title_size=25, text_size=22)
    + f'<p style="font-size:22px;line-height:1.4;color:{MUTED}">Любая работа по неформальной занятости '
      f'обязана либо исключить регион, либо разобрать его как отдельный случай.</p></div></div>'
    + foot("Переменная ORB_TRDDOG формы T-001, база — респонденты с заполненным значением")
)
write("anomaly", section("anomaly", body,
      "Это находка, ради которой стоит делать дескриптивный этап всерьёз. Если бы мы сразу взяли тему "
      "неформальной занятости и посчитали показатель по стране, он вышел бы пять целых две десятых "
      "процента против трёх годом раньше — и выглядело бы это как рост неформальности. На самом деле "
      "весь рост обеспечен одним регионом, где показатель за год вырос в восемь раз при неизменном "
      "числе ответивших."))

# ── 6. Город и село ───────────────────────────────────────────────────────────
body = (
    head("Восстановленный разрез: город и село",
         "Поле K не описано в документации — три формы дают согласованный ответ")
    + img("urban_rural", 1400, 535, "Сравнение города и села по четырём показателям", "align-self:center")
    + f'<div style="display:flex;gap:30px">'
    + card("Решающий признак", "Земельный участок: 85,3% против 20,2%. Такой разрыв не объясняется "
           "ничем, кроме типа поселения.", BLUE, text_size=22)
    + card("Подтверждение из третьей формы", "Работа без договора: 2,8% при K = 1 и 7,2% при K = 2. "
           "Сельская неформальность втрое выше.", BLUE, text_size=22)
    + card("Что это открывает", "Разрез город–село в данных есть, просто он не подписан. Направление "
           "кодировки стоит подтвердить у организаторов.", OCHRE, text_size=22)
    + '</div>'
    + foot("Формы d006, d008 и t001, 2024 год &middot; 6 603 городских и 5 397 сельских домохозяйств")
)
write("urbanrural", section("urbanrural", body,
      "Поле K нигде не описано, принимает всего два значения, и его легко принять за номер "
      "домохозяйства — мы сначала так и сделали и ошиблись. Проверка по трём независимым формам даёт "
      "однозначный ответ. Решающий аргумент именно земля: восемьдесят пять процентов против двадцати."))

# ── 7. Рынок труда ────────────────────────────────────────────────────────────
body = (
    head("Рынок труда: динамика и возраст", "Форма T-001, около 470 тысяч респондентов в год")
    + f'<div style="display:flex;gap:40px;align-items:start">'
    + img("employment_sex", 800, 461, "Занятость мужчин и женщин с 2021 по 2024 год")
    + img("employment_age", 800, 503, "Занятость по возрастным группам и полу в 2024 году")
    + '</div>'
    + f'<div style="display:flex;gap:30px">'
    + card("Занятость снижается монотонно", "67,6 → 65,9% за четыре года, без единого года роста.",
           BLUE, text_size=22)
    + card("Гендерный разрыв не сокращается", "Около 7 п.п. все четыре года, максимум в группе 25–34.",
           OCHRE, text_size=22)
    + card("Возрастной профиль правдоподобен", "Пик в 25–44, обрыв после 65: с 70,9% до 8,9%.",
           BLUE, text_size=22)
    + '</div>'
    + foot("Классический NEET посчитать нельзя: в выгрузке 40 колонок из ~154 и нет признака обучения")
)
write("labour", section("labour", body,
      "Занятость падает четыре года подряд, без единого отскока. Гендерный разрыв держится около семи "
      "процентных пунктов и не сокращается. Правый график — проверка правдоподобия синтетики: "
      "возрастной профиль ведёт себя как настоящий, пик в двадцать пять–сорок четыре, обрыв после "
      "шестидесяти пяти в восемь раз."))

# ── 8. Регионы ────────────────────────────────────────────────────────────────
body = (
    head("Средняя цифра прячет расхождение", "Страна теряет 1,7 п.п. занятости, но разброс по регионам — 11,4 п.п.")
    + f'<div style="display:flex;gap:44px;align-items:start">'
    + img("employment_region", 800, 591, "Изменение занятости по регионам в процентных пунктах")
    + f'<div style="width:820px;display:flex;flex-direction:column;gap:18px">'
      f'<div style="display:flex;gap:18px">'
    + stat("+6,3", "п.п. в Астане — единственный выраженный рост", BLUE)
    + stat("−5,1", "п.п. в ВКО, следом СКО с −3,6 и Туркестанская с −3,1", OCHRE)
    + '</div>'
    + card("Гипотеза для Результата 2", "Если периферия теряет людей активного возраста и удерживает "
           "группу 65+, где занятость 8,9%, то национальное снижение демографическое, а не "
           "экономическое. Для политики это разные диагнозы.", BLUE, text_size=22)
    + card("Разрыв ряда", "Абай, Жетісу и Ұлытау появились только в 2022 году, поэтому изменение к "
           "2021 для них не считается.", OCHRE, text_size=22)
    + '</div></div>'
    + foot("Названия регионов сопоставлены по кодам КАТО и требуют сверки с официальным справочником")
)
write("regions", section("regions", body,
      "Национальная цифра говорит о снижении на один и семь десятых процентных пункта, и это выглядит "
      "как ровный тренд. На деле разброс между регионами — одиннадцать с лишним пунктов. Астана "
      "прибавила шесть и три десятых, Восточно-Казахстанская потеряла пять и одну десятую. Это два "
      "разных процесса под одной средней."))

# ── 9. Домохозяйства ──────────────────────────────────────────────────────────
body = (
    head("Бедность определяется числом иждивенцев",
         "Самая устойчивая закономерность на всех 11 948 домохозяйствах 2024 года")
    + img("household_types", 1480, 549, "Доход на душу и удовлетворённость по типам домохозяйств",
          "align-self:center")
    + f'<div style="display:flex;gap:30px">'
    + stat("в 2,4 раза", "ниже доход на душу у многодетных, чем у одиночек", OCHRE)
    + stat("4,99 против 2,04", "человек в домохозяйстве: нижний и верхний квинтиль", BLUE)
    + stat("−16%", "дохода на душу на каждого ребёнка (регрессия, R² = 0,375)", INK)
    + '</div>'
    + foot("Удовлетворённость у многодетных при этом самая высокая: 7,71 против 7,29 — парадокс благополучия")
)
write("households", section("households", body,
      "Вот самый устойчивый результат всего этапа. Доход на душу у многодетных семей в два с половиной "
      "раза ниже, чем у одиночек. По квинтилям картина ещё нагляднее: в нижнем квинтиле почти пять "
      "человек в домохозяйстве, в верхнем — два. Бедность в этих данных определяется не заработком, а "
      "числом иждивенцев."))

# ── 10. Ограничения и выводы ──────────────────────────────────────────────────
body = (
    head("Ограничение, которого нет в README", "Блоки доходов и расходов откалиброваны независимо друг от друга")
    + f'<div style="display:flex;gap:40px;align-items:start">'
    + img("savings_gap", 1120, 480, "Индекс доходов и расходов и норма сбережений")
    + f'<div style="width:504px;display:flex;flex-direction:column;gap:16px">'
    + card("Проверка на продовольствие", "Еда записана в вопросах 9–10 в натуральных единицах. Даже "
           "если засчитать все их поля как тенге, норма сбережений падает лишь до 56,9%.",
           OCHRE, title_size=24, text_size=21)
    + card("Связи между признаками", "Благоустройство ~ доход: <b>0,015</b>. Образование главы ~ доход: "
           "<b>0,014</b>. Благоустройство ~ удовлетворённость: <b>0,002</b>.", BLUE,
           title_size=24, text_size=21)
    + f'<p style="font-size:21px;line-height:1.4;color:{MUTED}">Работают только структурные признаки: '
      f'доля занятых 0,336, площадь ~ размер домохозяйства 0,268.</p></div></div>'
    + f'<div style="display:flex;gap:30px">'
    + card("Что это значит для выбора темы", "Гипотезы вида «обеспеченные живут в лучших условиях» на "
           "этих данных не проверяются. Работают темы про структуру домохозяйства и разрез город–село.",
           BLUE, text_size=22)
    + card("Результат 2, к 7 октября", "Детская бедность как структурный эффект плюс сельская "
           "неформальность. Код, данные и все графики — в репозитории проекта.", OCHRE, text_size=22)
    + '</div>'
    + foot("Стандартные ошибки на синтетике занижены (README организатора) — эффекты трактуем как нижнюю границу")
)
write("limits", section("limits", body,
      "Это наша главная методологическая находка. Норма сбережений по расчёту выходит шестьдесят шесть "
      "процентов. Мы проверили самое очевидное объяснение — что не хватает расходов на еду. Но даже "
      "если засчитать все числовые поля этих вопросов как тенге, норма сбережений падает только до "
      "пятидесяти семи процентов, при реальных для Казахстана десяти–пятнадцати. Значит, блоки доходов "
      "и расходов откалиброваны независимо. В README организатора этого ограничения нет."))

# ── 11. План работ: изометрическая гант-диаграмма ─────────────────────────────
TONE = {"ink": INK, "muted": MUTED}


def gantt_labels():
    out = []
    for L in LABELS["labels"]:
        w = 340 if L["align"] != "center" else 200
        left = {"left": L["x"], "right": L["x"] - w, "center": L["x"] - w / 2}[L["align"]]
        out.append(
            f'<p style="position:absolute;left:{left:.0f}px;top:{L["y"] - L["size"] * 0.8:.0f}px;'
            f'width:{w}px;text-align:{L["align"]};font-size:{L["size"]}px;'
            f'color:{TONE[L["tone"]]};font-weight:{600 if L["tone"] == "ink" else 400}">{L["text"]}</p>')
    return "".join(out)


legend = "".join(
    f'<div style="display:flex;gap:12px;align-items:center">'
    f'<x-shape kind="rect" style="width:26px;height:26px;background:{c};border-radius:3px"></x-shape>'
    f'<p style="font-size:23px;color:{INK2}">{t}</p></div>'
    for c, t in [(BLUE, "сделано"), (OCHRE, "следующий этап"), ("#6E86AD", "в плане")])

body = (
    head("План работ до финала", "Этапы конкурса от 21 сентября до 20 октября")
    + f'<div style="position:relative;width:1180px;height:580px;align-self:center">'
      f'{iso("gantt", 1180, 580)}{gantt_labels()}</div>'
    + f'<div style="display:flex;gap:46px;align-items:center">{legend}'
      f'<p style="font-size:23px;color:{MUTED}">Результат 1 сдан 30 сентября, впереди гипотезы и '
      f'методология к 7 октября</p></div>'
    + foot("График по регламенту конкурса STAT.DATATHON-2026")
)
write("gantt", section("gantt", body,
      "Где мы находимся. Дескриптивная аналитика закрыта тридцатого сентября — это синяя полоса. "
      "Следующий этап, оранжевый, это гипотезы и методология к седьмому октября. Дальше завершение "
      "проекта к двенадцатому, техническая проверка на допуск и финал двадцатого октября."))
