"""Сборка HTML-слайдов презентации. Редакционная вёрстка: сетка, линейки, акцент."""
import json
import pathlib

OUT = pathlib.Path("/tmp/claude-0/-home-claude/0d0e2ed4-36a7-5572-b68c-9454ae6c8f69/scratchpad/deck/project/slides")
OUT.mkdir(parents=True, exist_ok=True)

BG, INK, INK2, MUTED = "#FFFFFF", "#14161A", "#55606E", "#8B96A5"
RULE, RULE_SOFT = "#14161A", "#DDE1E7"
RED, TEAL, NEUTRAL = "#C4362F", "#0E9B8E", "#7A8594"
DISPLAY = "'Oswald', 'Arial Narrow', sans-serif"
SANS = "'IBM Plex Sans', Arial, sans-serif"
MONO = "'IBM Plex Mono', 'Courier New', monospace"

IMG = json.loads(pathlib.Path("/tmp/blobs.json").read_text())


def chrome(kicker, num, total=10):
    """Верхняя строка: рубрика слева, номер справа, под ними жирная линейка."""
    return (f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
            f'border-bottom:3px solid {RULE};padding:0 0 14px">'
            f'<p style="font-size:21px;font-weight:600;letter-spacing:3px;text-transform:uppercase;'
            f'color:{RED}">{kicker}</p>'
            f'<p style="font-family:{MONO};font-size:21px;color:{MUTED}">{num:02d} / {total}</p></div>')


def title(h, sub=None):
    out = (f'<h2 style="font-family:{DISPLAY};font-size:66px;font-weight:500;line-height:1.06;'
           f'letter-spacing:-0.5px;color:{INK}">{h}</h2>')
    if sub:
        out += f'<p style="font-size:27px;line-height:1.35;color:{INK2}">{sub}</p>'
    return f'<div style="display:flex;flex-direction:column;gap:12px">{out}</div>'


def stat(value, label, accent=INK, first=False):
    """Крупное число без рамки: разделителем служит вертикальная линейка."""
    border = "" if first else f"border-left:1px solid {RULE_SOFT};padding:0 0 0 34px;"
    return (f'<div style="flex:1;{border}display:flex;flex-direction:column;gap:10px">'
            f'<p style="font-family:{MONO};font-size:42px;font-weight:600;letter-spacing:-1px;'
            f'color:{accent}">{value}</p>'
            f'<p style="font-size:22px;line-height:1.35;color:{INK2}">{label}</p></div>')


def stats(items):
    cells = "".join(stat(v, l, a, i == 0) for i, (v, l, a) in enumerate(items))
    return f'<div style="display:flex;gap:34px">{cells}</div>'


def note(n, head, text, accent=RED, width=None, size=23):
    """Пункт с номером на полях — вместо карточки с тенью."""
    w = f"width:{width};" if width else "flex:1;"
    return (f'<div style="{w}display:flex;gap:20px;border-top:1px solid {RULE_SOFT};padding:20px 0 0">'
            f'<p style="font-family:{MONO};font-size:24px;font-weight:600;color:{accent};'
            f'width:34px">{n}</p>'
            f'<div style="flex:1;display:flex;flex-direction:column;gap:8px">'
            f'<h3 style="font-size:25px;font-weight:600;color:{INK}">{head}</h3>'
            f'<p style="font-size:{size}px;line-height:1.45;color:{INK2}">{text}</p></div></div>')


def notes(items, gap=34):
    body = "".join(note(f"{i + 1:02d}", h, t, a) for i, (h, t, a) in enumerate(items))
    return f'<div style="display:flex;gap:{gap}px">{body}</div>'


def table(headers, rows, widths, aligns=None):
    aligns = aligns or ["left"] * len(headers)
    th = "".join(
        f'<th style="width:{w};text-align:{a};font-size:21px;font-weight:600;'
        f'letter-spacing:1.5px;text-transform:uppercase;color:{MUTED}">{h}</th>'
        for h, w, a in zip(headers, widths, aligns))
    trs = []
    for r in rows:
        tds = "".join(f'<td style="text-align:{a}">{c}</td>' for c, a in zip(r, aligns))
        trs.append(f"<tr>{tds}</tr>")
    return (f'<table style="font-family:{SANS};font-size:24px;color:{INK};padding:14px 0">'
            f"<tr>{th}</tr>{''.join(trs)}</table>")


def img(key, w, h, alt, extra=""):
    return (f'<img src="{IMG[key]}" alt="{alt}" style="width:{w}px;height:{h}px;'
            f'object-fit:contain;{extra}">')


def foot(text):
    return (f'<p style="position:absolute;left:112px;bottom:60px;width:1696px;font-size:21px;'
            f'color:{MUTED};border-top:1px solid {RULE_SOFT};padding:16px 0 0">{text}</p>')


def slide(sid, body, notes_text, pad="96px 112px 150px"):
    html = (f'<section id="{sid}" data-transition="fade" style="background:{BG};color:{INK};'
            f'font-family:{SANS};padding:{pad};display:flex;flex-direction:column;gap:30px">'
            f'{body}<aside>{notes_text}</aside></section>')
    (OUT / f"{sid}.html").write_text(html, encoding="utf-8")
    print(f"{sid}.html  {len(html)}")


# ── 01 Обложка ────────────────────────────────────────────────────────────────
cover = (
    f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
    f'border-bottom:3px solid {RULE};padding:0 0 14px">'
    f'<p style="font-size:21px;font-weight:600;letter-spacing:3px;text-transform:uppercase;'
    f'color:{RED}">STAT.DATATHON-2026 &middot; Результат 1</p>'
    f'<p style="font-family:{MONO};font-size:21px;color:{MUTED}">30.09.2026</p></div>'
    f'<div style="display:flex;flex-direction:column;gap:18px">'
    f'<h1 style="font-family:{DISPLAY};font-size:116px;font-weight:500;line-height:0.98;'
    f'letter-spacing:-2px;color:{INK}">Дескриптивная<br>аналитика датасетов</h1>'
    f'<p style="font-size:30px;line-height:1.35;color:{INK2};width:1100px">Синтетические '
    f'микроданные Бюро национальной статистики АСПР РК, 2021–2024</p></div>'
    f'<div style="flex:1"></div>'
    + stats([("236", "таблиц в восьми формах", INK),
             ("72,6 млн", "строк обработано полностью", INK),
             ("4,68 ГБ → 300 МБ", "CSV сведён в parquet", RED),
             ("48 000 × 37", "объединённая таблица", INK)])
    + f'<div style="display:flex;justify-content:space-between;align-items:end;'
      f'border-top:3px solid {RULE};padding:24px 0 0">'
      f'<div style="display:flex;flex-direction:column;gap:8px">'
      f'<p style="font-family:{DISPLAY};font-size:34px;font-weight:500;letter-spacing:0.5px;'
      f'color:{INK}">Команда «Котлы чудес»</p>'
      f'<p style="font-size:24px;color:{INK2}">Арнас Жаксаликов &middot; Аружан Болат</p></div>'
      f'<p style="font-family:{MONO};font-size:22px;color:{MUTED}">01 / 10</p></div>'
)
slide("cover", cover,
      "Мы обработали весь архив целиком, а не выборку: двести тридцать шесть таблиц, семьдесят два "
      "с половиной миллиона строк. Первым шагом перевели данные в parquet — объём упал с четырёх с "
      "лишним гигабайт до трёхсот мегабайт, и после этого любой запрос по самой большой форме "
      "отрабатывает за секунды. Главный результат подготовительного этапа — объединённая таблица "
      "домохозяйств на сорок восемь тысяч строк. Вся презентация, включая графики, воспроизводится "
      "из репозитория одной командой.", pad="96px 112px 96px")

# ── 02 Состав архива ──────────────────────────────────────────────────────────
rows = [("1t_god", "предприятие × показатель, год", "30 025 899", "4"),
        ("1t_kv", "то же, поквартально", "24 480 242", "16"),
        ("d004", "покупка или доход домохозяйства", "8 612 484", "192"),
        ("2t", "предприятие × показатель, оплата труда", "7 328 814", "4"),
        ("t001", "респондент обследования занятости", "1 885 110", "4"),
        ("d008", "член домохозяйства", "169 059", "4"),
        ("d002", "домохозяйство, субъективные оценки", "95 542", "8"),
        ("d006", "домохозяйство, жильё и благоустройство", "46 743", "4")]
rows = [(f'<span style="color:{RED}">{a}</span>', b,
         f'<span style="font-family:{MONO}">{c}</span>',
         f'<span style="font-family:{MONO}">{d}</span>') for a, b, c, d in rows]
slide("data",
      chrome("Данные", 2)
      + title("Что в архиве", "Восемь форм с разными единицами наблюдения: от предприятия до члена домохозяйства")
      + table(["Форма", "Единица наблюдения", "Строк", "Файлов"], rows,
              ["13%", "45%", "22%", "20%"], ["left", "left", "right", "right"])
      + notes([("Длинный формат",
                "30 млн строк в форме 1-Т — это не 30 млн предприятий, а 52 289: одна строка равна "
                "одному значению одного показателя.", RED),
               ("Конвейер из пяти шагов",
                "parquet → рынок труда → мердж → анализ → графики. DuckDB считает потоково, "
                "достаточно 4 ГБ оперативной памяти.", RED)])
      + foot("Источник: synthetic_microdata_2021-2024_20260921 &middot; все значения посчитаны на полном архиве"),
      "Единица наблюдения у форм разная. Формы предприятий записаны в длинном формате: одна строка "
      "это одно значение одного показателя, поэтому тридцать миллионов строк годовой формы 1-Т — это "
      "всего пятьдесят две тысячи предприятий. Обследования домохозяйств устроены иначе, там строка "
      "это человек или покупка.")

# ── 03 Объединённая таблица ───────────────────────────────────────────────────
forms = [("d008", "состав домохозяйства: размер, дети, пожилые, занятые, глава", "12 000"),
         ("d006", "жильё: площадь, 42 удобства, 46 предметов длительного пользования", "11 704"),
         ("d004", "деньги: доходы по 23 источникам, расходы по 7 блокам", "11 948"),
         ("d002", "субъективные оценки условий жизни по шкалам", "11 931")]
form_rows = "".join(
    f'<div style="display:flex;gap:26px;align-items:baseline;border-top:1px solid {RULE_SOFT};'
    f'padding:18px 0 0">'
    f'<p style="font-family:{MONO};font-size:26px;font-weight:600;color:{RED};width:92px">{k}</p>'
    f'<p style="flex:1;font-size:24px;line-height:1.4;color:{INK2}">{d}</p>'
    f'<p style="font-family:{MONO};font-size:24px;color:{INK};width:130px;text-align:right">{n}</p></div>'
    for k, d, n in forms)
slide("merged",
      chrome("Данные", 3)
      + title("Объединённая таблица домохозяйств",
              "Четыре формы D-серии сходятся по ключу NOMER без потерь")
      + f'<div style="display:flex;flex-direction:column;gap:0">{form_rows}</div>'
      + f'<div style="border-top:3px solid {RULE};padding:26px 0 0">'
      + stats([("48 000 × 37", "12 000 домохозяйств × 4 года", RED),
               ("0", "потерянных при соединении записей", INK),
               ("37", "признаков, включая производные", INK)])
      + '</div>'
      + f'<p style="font-size:23px;line-height:1.45;color:{INK2};width:1400px">Производные признаки: '
        f'доход и расходы на душу, норма сбережений, площадь на человека, индекс жилищной депривации, '
        f'доля занятых, тип поселения. Глава домохозяйства определяется по RODSTVO = 1 — ровно одна '
        f'строка на домохозяйство.</p>'
      + foot("Панели между годами нет: номера домохозяйств перевыдаются, совпадение региона 5,4% при случайном уровне 5%"),
      "Это ядро всей дальнейшей работы. Четыре формы связываются по ключу NOMER абсолютно чисто: ни "
      "одного домохозяйства не потерялось и ни одного лишнего не появилось. На выходе сорок восемь "
      "тысяч строк и тридцать семь признаков. Важное ограничение: панели между годами нет, номера "
      "перевыдаются каждый год.")

# ── 04 Заполненность и дрейф ──────────────────────────────────────────────────
drift = [("Колонка со значением", "GR1", "VAL_NUM"), ("Колонка региона", "KATO", "KATO1"),
         ("Колонок в 1-Т годовой", "16", "30"), ("Кодов ОКЭД", "83", "539"),
         ("Регионов в выборке", "17", "20"), ("Предприятий в 1-Т", "70 874", "52 289")]
drift = [(a, f'<span style="font-family:{MONO};color:{INK2}">{b}</span>',
          f'<span style="font-family:{MONO};color:{RED};font-weight:600">{c}</span>')
         for a, b, c in drift]
slide("quality",
      chrome("Качество", 4)
      + title("Заполненность и дрейф схемы",
              "Разреженность анкет — норма, а вот смена схемы ломает код")
      + f'<div style="display:flex;gap:48px;align-items:start">'
      + img("completeness", 990, 472, "Заполненность десяти самых разреженных таблиц")
      + f'<div style="width:648px;display:flex;flex-direction:column;gap:10px">'
      + table(["Что меняется", "2021", "2024"], drift, ["50%", "25%", "25%"],
              ["left", "right", "right"])
      + f'<p style="font-size:22px;line-height:1.4;color:{INK2}">Рост с 17 до 20 регионов — реформа '
        f'2022 года: Абай, Жетісу, Ұлытау. Падение числа предприятий — смена охвата выгрузки.</p>'
        f'</div></div>'
      + foot("Отдельная ловушка: T-001 за 2022, строка 26332 — запятая внутри кавычек ломает автоопределение парсера"),
      "Слева заполненность таблиц. Треть непустых ячеек у формы d006 это не ошибка: в анкете с "
      "ветвлениями респондент не отвечает на неприменимые вопросы. Справа то, что ломает наивный код: "
      "колонка со значением переименована, код региона сменил разрядность, классификатор ОКЭД стал "
      "детальнее в шесть раз.")

# ── 05 Аномалия ───────────────────────────────────────────────────────────────
slide("anomaly",
      chrome("Качество", 5)
      + title("Аномалия генератора",
              "Один регион искажает национальный показатель неформальной занятости вдвое")
      + f'<div style="display:flex;gap:48px;align-items:start">'
      + img("informality", 1090, 482, "Скачок доли работающих без договора в Алматинской области")
      + f'<div style="width:548px;display:flex;flex-direction:column;gap:22px">'
      + note("01", "Что мы увидели", "Алматинская область: 6,3 → 5,4 → 4,8 → <b>40,7%</b>. База "
             "ответов при этом стабильна, около 13 тысяч заполненных значений.", RED, size=22)
      + note("02", "Что это значит", "Без этого региона ряд по стране ровный: 3,2 / 3,3 / 2,9 / "
             "<b>3,0%</b>. Скачок — сбой генератора, а не экономика.", RED, size=22)
      + '</div></div>'
      + foot("Переменная ORB_TRDDOG формы T-001 &middot; база — респонденты с заполненным значением"),
      "Это находка, ради которой стоит делать дескриптивный этап всерьёз. Если бы мы сразу взяли тему "
      "неформальной занятости и посчитали показатель по стране, он вышел бы пять целых две десятых "
      "процента против трёх годом раньше, и выглядело бы это как рост неформальности. На самом деле "
      "весь рост обеспечен одним регионом, где показатель за год вырос в восемь раз при неизменном "
      "числе ответивших.")

# ── 06 Город и село ───────────────────────────────────────────────────────────
slide("urbanrural",
      chrome("Находка", 6)
      + title("Восстановленный разрез: город и село",
              "Поле K не описано в документации — три независимые формы дают согласованный ответ")
      + img("urban_rural", 1380, 528, "Сравнение города и села по четырём показателям",
            "align-self:center")
      + notes([("Решающий признак",
                "Земельный участок: 85,3% против 20,2%. Такой разрыв не объясняется ничем, кроме "
                "типа поселения.", RED),
               ("Подтверждение из третьей формы",
                "Работа без договора: 2,8% при K = 1 и 7,2% при K = 2. Сельская неформальность "
                "втрое выше городской.", RED),
               ("Что это открывает",
                "Разрез город–село в данных есть, просто он не подписан. Направление кодировки "
                "стоит подтвердить у организаторов.", RED)])
      + foot("Формы d006, d008 и t001, 2024 год &middot; 6 603 городских и 5 397 сельских домохозяйств"),
      "Поле K нигде не описано, принимает всего два значения, и его легко принять за номер "
      "домохозяйства — мы сначала так и сделали и ошиблись. Проверка по трём независимым формам даёт "
      "однозначный ответ. Решающий аргумент именно земля: восемьдесят пять процентов против двадцати.")

# ── 07 Рынок труда ────────────────────────────────────────────────────────────
slide("labour",
      chrome("Рынок труда", 7)
      + title("Динамика и возрастной профиль", "Форма T-001, около 470 тысяч респондентов в год")
      + f'<div style="display:flex;gap:48px;align-items:start">'
      + img("employment_sex", 790, 455, "Занятость мужчин и женщин с 2021 по 2024 год")
      + img("employment_age", 790, 497, "Занятость по возрастным группам и полу в 2024 году")
      + '</div>'
      + notes([("Занятость снижается монотонно", "67,6 → 65,9% за четыре года, без единого года роста.", RED),
               ("Гендерный разрыв не сокращается", "Около 7 п.п. все четыре года, максимум в группе 25–34.", RED),
               ("Возрастной профиль правдоподобен", "Пик в 25–44, обрыв после 65: с 70,9% до 8,9%.", RED)])
      + foot("Классический NEET посчитать нельзя: в выгрузке 40 колонок из ~154 и нет признака обучения"),
      "Занятость падает четыре года подряд, без единого отскока. Гендерный разрыв держится около семи "
      "процентных пунктов. Правый график — проверка правдоподобия синтетики: возрастной профиль ведёт "
      "себя как настоящий, пик в двадцать пять–сорок четыре, обрыв после шестидесяти пяти в восемь раз.")

# ── 08 Регионы ────────────────────────────────────────────────────────────────
slide("regions",
      chrome("Рынок труда", 8)
      + title("Средняя цифра прячет расхождение",
              "Страна теряет 1,7 п.п. занятости, но разброс по регионам — 11,4 п.п.")
      + f'<div style="display:flex;gap:48px;align-items:start">'
      + img("employment_region", 790, 584, "Изменение занятости по регионам в процентных пунктах")
      + f'<div style="width:858px;display:flex;flex-direction:column;gap:26px">'
      + stats([("+6,3", "п.п. в Астане — единственный выраженный рост", TEAL),
               ("−5,1", "п.п. в ВКО, следом СКО с −3,6", RED)])
      + note("01", "Что стоит проверить",
             "Если периферия теряет людей активного возраста и удерживает группу 65+, где занятость "
             "8,9%, то национальное снижение демографическое, а не экономическое. Для политики это "
             "разные диагнозы.", RED, size=22)
      + note("02", "Разрыв ряда",
             "Абай, Жетісу и Ұлытау появились только в 2022 году, поэтому изменение к 2021 для них "
             "не считается.", RED, size=22)
      + '</div></div>'
      + foot("Названия регионов сопоставлены по кодам КАТО и требуют сверки с официальным справочником"),
      "Национальная цифра говорит о снижении на один и семь десятых пункта, и это выглядит как ровный "
      "тренд. На деле разброс между регионами одиннадцать с лишним пунктов. Астана прибавила шесть и "
      "три десятых, Восточно-Казахстанская потеряла пять и одну десятую. Это два разных процесса под "
      "одной средней.")

# ── 09 Домохозяйства ──────────────────────────────────────────────────────────
slide("households",
      chrome("Находка", 9)
      + title("Бедность определяется числом иждивенцев",
              "Самая устойчивая закономерность на всех 11 948 домохозяйствах 2024 года")
      + img("household_types", 1450, 538, "Доход на душу и удовлетворённость по типам домохозяйств",
            "align-self:center")
      + f'<div style="border-top:3px solid {RULE};padding:24px 0 0">'
      + stats([("в 2,4 раза", "ниже доход на душу у многодетных, чем у одиночек", RED),
               ("4,99 / 2,04", "человек в домохозяйстве: нижний и верхний квинтиль", INK),
               ("−16%", "дохода на душу на каждого ребёнка, R² = 0,375", RED)])
      + '</div>'
      + foot("Удовлетворённость у многодетных при этом самая высокая: 7,71 против 7,29 — парадокс благополучия"),
      "Самый устойчивый результат всего этапа. Доход на душу у многодетных семей в два с половиной "
      "раза ниже, чем у одиночек. По квинтилям картина ещё нагляднее: в нижнем квинтиле почти пять "
      "человек в домохозяйстве, в верхнем два. Бедность в этих данных определяется не заработком, а "
      "числом иждивенцев.")

# ── 10 Ограничение достоверности ──────────────────────────────────────────────
slide("limits",
      chrome("Методология", 10)
      + title("Ограничение, которого нет в README",
              "Блоки доходов и расходов откалиброваны независимо друг от друга")
      + f'<div style="display:flex;gap:48px;align-items:start">'
      + img("savings_gap", 1090, 467, "Индекс доходов и расходов и норма сбережений")
      + f'<div style="width:548px;display:flex;flex-direction:column;gap:22px">'
      + note("01", "Проверка на продовольствие",
             "Еда записана в вопросах 9–10 в натуральных единицах. Даже если засчитать все их поля "
             "как тенге, норма сбережений падает лишь до 56,9%.", RED, size=22)
      + note("02", "Связи между признаками",
             "Благоустройство ~ доход: <b>0,015</b>. Образование главы ~ доход: <b>0,014</b>. "
             "Работают только структурные признаки.", RED, size=22)
      + '</div></div>'
      + f'<div style="display:flex;gap:48px;border-top:3px solid {RULE};padding:24px 0 0">'
        f'<div style="flex:1;display:flex;flex-direction:column;gap:8px">'
        f'<h3 style="font-family:{DISPLAY};font-size:28px;font-weight:500;letter-spacing:0.5px;'
        f'color:{INK}">Что это значит для выбора темы</h3>'
        f'<p style="font-size:23px;line-height:1.4;color:{INK2}">Гипотезы вида «обеспеченные живут в '
        f'лучших условиях» на этих данных не проверяются. Работают темы про структуру домохозяйства '
        f'и разрез город–село.</p></div>'
        f'<div style="flex:1;display:flex;flex-direction:column;gap:8px">'
        f'<h3 style="font-family:{DISPLAY};font-size:28px;font-weight:500;letter-spacing:0.5px;'
        f'color:{RED}">Что нужно уточнить у организаторов</h3>'
        f'<p style="font-size:23px;line-height:1.4;color:{INK2}">Справочник кодов KCP для форм 1-Т '
        f'и 2-Т и направление кодировки поля K. Без них часть архива остаётся нечитаемой.</p>'
        f'</div></div>'
      + foot("Стандартные ошибки на синтетике занижены (README организатора) — эффекты трактуем как нижнюю границу"),
      "Наша главная методологическая находка. Норма сбережений по расчёту выходит шестьдесят шесть "
      "процентов. Мы проверили самое очевидное объяснение — что не хватает расходов на еду. Но даже "
      "если засчитать все числовые поля этих вопросов как тенге, норма сбережений падает только до "
      "пятидесяти семи процентов, при реальных для Казахстана десяти–пятнадцати. Значит, блоки "
      "доходов и расходов откалиброваны независимо.")
