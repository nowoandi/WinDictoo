"""UI/interface translations — separate from Config.language (the Whisper
speech-recognition language). Config.ui_language selects which of these the
app's own buttons/labels/dialogs render in.

State-keyed lookups (state_label/tray_label) rely on windictoo.app.State
being a StrEnum whose values ("idle", "recording", ...) already match this
module's "state.*"/"tray.*" key suffixes — no import of .app needed here,
which keeps this module a leaf with no dependency on the rest of the app.
"""

from __future__ import annotations

SUPPORTED = ("ru", "en", "de", "fr", "es", "zh", "tr", "hy")

# Native-script names for the interface-language picker (Settings -> Основные).
UI_LANGS: list[tuple[str, str]] = [
    ("Русский", "ru"),
    ("English", "en"),
    ("Deutsch", "de"),
    ("Français", "fr"),
    ("Español", "es"),
    ("中文", "zh"),
    ("Türkçe", "tr"),
    ("Հայերեն", "hy"),
]

_current: str = "ru"

# Shown on the onboarding welcome screen — one greeting per interface
# language the app ships with. Deliberately NOT a translated string: the
# whole point is showing every language at once. Order is presentational
# (Armenian sits ahead of French by request), so it intentionally differs
# from UI_LANGS, which drives the actual language picker.
GREETINGS: list[str] = ["Привет", "Hello", "Hallo", "Բարև", "Bonjour", "Hola", "你好", "Merhaba"]


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in SUPPORTED else "ru"


def get_language() -> str:
    return _current


STRINGS: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- common
    "common.later": {
        "ru": "Позже", "en": "Later", "de": "Später", "fr": "Plus tard",
        "es": "Más tarde", "zh": "稍后", "tr": "Sonra", "hy": "Ավելի ուշ",
    },
    "common.copy": {
        "ru": "⧉ Копировать", "en": "⧉ Copy", "de": "⧉ Kopieren", "fr": "⧉ Copier",
        "es": "⧉ Copiar", "zh": "⧉ 复制", "tr": "⧉ Kopyala", "hy": "⧉ Պատճենել",
    },
    "common.copied": {
        "ru": "Скопировано ✓", "en": "Copied ✓", "de": "Kopiert ✓", "fr": "Copié ✓",
        "es": "Copiado ✓", "zh": "已复制 ✓", "tr": "Kopyalandı ✓", "hy": "Պատճենվեց ✓",
    },
    "common.error_with": {
        "ru": "Ошибка: {error}", "en": "Error: {error}", "de": "Fehler: {error}",
        "fr": "Erreur : {error}", "es": "Error: {error}", "zh": "错误：{error}",
        "tr": "Hata: {error}", "hy": "Սխալ․ {error}",
    },
    "common.loading_model": {
        "ru": "Загрузка модели…", "en": "Loading model…", "de": "Modell wird geladen…",
        "fr": "Chargement du modèle…", "es": "Cargando modelo…", "zh": "正在加载模型…",
        "tr": "Model yükleniyor…", "hy": "Մոդելը բեռնվում է…",
    },
    "common.model_loaded": {
        "ru": "Модель загружена ✓", "en": "Model loaded ✓", "de": "Modell geladen ✓",
        "fr": "Modèle chargé ✓", "es": "Modelo cargado ✓", "zh": "模型已加载 ✓",
        "tr": "Model yüklendi ✓", "hy": "Մոդելը բեռնված է ✓",
    },
    "unit.mb": {
        "ru": "{n} МБ", "en": "{n} MB", "de": "{n} MB", "fr": "{n} Mo",
        "es": "{n} MB", "zh": "{n} MB", "tr": "{n} MB", "hy": "{n} ՄԲ",
    },
    "unit.gb": {
        "ru": "{n} ГБ", "en": "{n} GB", "de": "{n} GB", "fr": "{n} Go",
        "es": "{n} GB", "zh": "{n} GB", "tr": "{n} GB", "hy": "{n} ԳԲ",
    },
    "common.press_keys": {
        "ru": "Нажмите клавиши…", "en": "Press keys…", "de": "Tasten drücken…",
        "fr": "Appuyez sur les touches…", "es": "Pulsa las teclas…", "zh": "请按下按键…",
        "tr": "Tuşlara basın…", "hy": "Սեղմեք ստեղները…",
    },

    # ------------------------------------------------------------- main window
    "main.state_loading_model": {
        "ru": "Загружаю модель…", "en": "Loading model…", "de": "Lade Modell…",
        "fr": "Chargement du modèle…", "es": "Cargando modelo…", "zh": "正在加载模型…",
        "tr": "Model yükleniyor…", "hy": "Բեռնում եմ մոդելը…",
    },
    "main.esc_cancel": {
        "ru": "Esc — отмена", "en": "Esc — cancel", "de": "Esc — abbrechen",
        "fr": "Échap — annuler", "es": "Esc: cancelar", "zh": "Esc — 取消",
        "tr": "Esc — iptal", "hy": "Esc — չեղարկել",
    },
    "main.btn_start": {
        "ru": "▶   Старт", "en": "▶   Start", "de": "▶   Start", "fr": "▶   Démarrer",
        "es": "▶   Iniciar", "zh": "▶   开始", "tr": "▶   Başlat", "hy": "▶   Սկսել",
    },
    "main.btn_stop": {
        "ru": "⏹   Стоп", "en": "⏹   Stop", "de": "⏹   Stopp", "fr": "⏹   Arrêter",
        "es": "⏹   Detener", "zh": "⏹   停止", "tr": "⏹   Durdur", "hy": "⏹   Կանգնեցնել",
    },
    "main.mode_hold_short": {
        "ru": "удержание", "en": "hold", "de": "halten", "fr": "maintien",
        "es": "mantener", "zh": "按住", "tr": "basılı tut", "hy": "պահել",
    },
    "main.mode_toggle_short": {
        "ru": "переключ.", "en": "toggle", "de": "umschalten", "fr": "bascule",
        "es": "alternar", "zh": "切换", "tr": "geçiş", "hy": "անջատել",
    },
    "main.mode_toggle_long": {
        "ru": "переключение", "en": "toggle", "de": "Umschalten", "fr": "Bascule",
        "es": "Alternar", "zh": "切换模式", "tr": "Geçiş", "hy": "Անջատում",
    },
    "main.recognized_text_label": {
        "ru": "РАСПОЗНАННЫЙ ТЕКСТ", "en": "RECOGNIZED TEXT", "de": "ERKANNTER TEXT",
        "fr": "TEXTE RECONNU", "es": "TEXTO RECONOCIDO", "zh": "识别文本",
        "tr": "TANINAN METİN", "hy": "ՃԱՆԱՉՎԱԾ ՏԵՔՍՏ",
    },
    "main.result_placeholder": {
        "ru": "Нажмите Старт или микрофон и продиктуйте…",
        "en": "Press Start or the mic and dictate…",
        "de": "Drücke Start oder das Mikrofon und diktiere…",
        "fr": "Appuyez sur Démarrer ou le micro et dictez…",
        "es": "Pulsa Iniciar o el micrófono y dicta…",
        "zh": "点击开始或麦克风并开始口述…",
        "tr": "Başlat'a veya mikrofona basıp konuşun…",
        "hy": "Սեղմեք Սկսել կամ խոսափողը և թելադրեք…",
    },
    "main.result_empty": {
        "ru": "(пусто)", "en": "(empty)", "de": "(leer)", "fr": "(vide)",
        "es": "(vacío)", "zh": "（空）", "tr": "(boş)", "hy": "(դատարկ)",
    },
    "main.refine_checking": {
        "ru": "🧠 Ollama: проверка…", "en": "🧠 Ollama: checking…", "de": "🧠 Ollama: wird geprüft…",
        "fr": "🧠 Ollama : vérification…", "es": "🧠 Ollama: comprobando…", "zh": "🧠 Ollama：检查中…",
        "tr": "🧠 Ollama: kontrol ediliyor…", "hy": "🧠 Ollama՝ ստուգում…",
    },
    "main.refine_connected": {
        "ru": "🧠 Ollama: на связи", "en": "🧠 Ollama: online", "de": "🧠 Ollama: online",
        "fr": "🧠 Ollama : en ligne", "es": "🧠 Ollama: en línea", "zh": "🧠 Ollama：在线",
        "tr": "🧠 Ollama: çevrimiçi", "hy": "🧠 Ollama՝ կապված է",
    },
    "main.refine_disconnected": {
        "ru": "🧠 Ollama: офлайн", "en": "🧠 Ollama: offline", "de": "🧠 Ollama: offline",
        "fr": "🧠 Ollama : hors ligne", "es": "🧠 Ollama: sin conexión", "zh": "🧠 Ollama：离线",
        "tr": "🧠 Ollama: çevrimdışı", "hy": "🧠 Ollama՝ անհասանելի",
    },
    "main.settings_title": {
        "ru": "Настройки WinDictoo", "en": "WinDictoo Settings", "de": "WinDictoo-Einstellungen",
        "fr": "Paramètres WinDictoo", "es": "Ajustes de WinDictoo", "zh": "WinDictoo 设置",
        "tr": "WinDictoo Ayarları", "hy": "WinDictoo կարգավորումներ",
    },

    # ------------------------------------------------------------------ tabs
    "tabs.general": {
        "ru": "Основные", "en": "General", "de": "Allgemein", "fr": "Général",
        "es": "General", "zh": "常规", "tr": "Genel", "hy": "Հիմնական",
    },
    "tabs.recognition": {
        "ru": "Распознавание", "en": "Recognition", "de": "Erkennung", "fr": "Reconnaissance",
        "es": "Reconocimiento", "zh": "识别", "tr": "Tanıma", "hy": "Ճանաչում",
    },
    "tabs.refinement": {
        "ru": "Улучшение", "en": "Refinement", "de": "Verbesserung", "fr": "Amélioration",
        "es": "Mejora", "zh": "优化", "tr": "İyileştirme", "hy": "Բարելավում",
    },
    "tabs.privacy": {
        "ru": "Приватность", "en": "Privacy", "de": "Datenschutz", "fr": "Confidentialité",
        "es": "Privacidad", "zh": "隐私", "tr": "Gizlilik", "hy": "Գաղտնիություն",
    },

    # ------------------------------------------------------------ general tab
    "gen.card_hotkey": {
        "ru": "Горячая клавиша", "en": "Hotkey", "de": "Tastenkombination",
        "fr": "Raccourci clavier", "es": "Atajo de teclado", "zh": "快捷键",
        "tr": "Kısayol tuşu", "hy": "Դյուրանցում",
    },
    "gen.hotkey_label": {
        "ru": "Сочетание", "en": "Combination", "de": "Kombination", "fr": "Combinaison",
        "es": "Combinación", "zh": "组合键", "tr": "Kombinasyon", "hy": "Համադրություն",
    },
    "gen.mode_hold": {
        "ru": "Удержание", "en": "Hold", "de": "Halten", "fr": "Maintien",
        "es": "Mantener", "zh": "按住", "tr": "Basılı Tut", "hy": "Պահել",
    },
    "gen.mode_toggle": {
        "ru": "Переключение", "en": "Toggle", "de": "Umschalten", "fr": "Bascule",
        "es": "Alternar", "zh": "切换", "tr": "Geçiş", "hy": "Անջատում",
    },
    "gen.suppress_switch": {
        "ru": "Не пропускать клавишу в приложение (Пробел не двигает курсор)",
        "en": "Don't pass the key to the app (Space won't move the cursor)",
        "de": "Taste nicht an die App weiterleiten (Leertaste bewegt den Cursor nicht)",
        "fr": "Ne pas transmettre la touche à l'application (Espace ne déplace pas le curseur)",
        "es": "No pasar la tecla a la aplicación (Espacio no mueve el cursor)",
        "zh": "不将按键传递给应用程序（空格不会移动光标）",
        "tr": "Tuşu uygulamaya iletme (Boşluk imleci hareket ettirmez)",
        "hy": "Չփոխանցել ստեղնը հավելվածին (Space-ը կուրսորը չի շարժի)",
    },
    "gen.card_insertion": {
        "ru": "Куда вставлять текст", "en": "Where to insert text", "de": "Wohin der Text eingefügt wird",
        "fr": "Où insérer le texte", "es": "Dónde insertar el texto", "zh": "文本插入位置",
        "tr": "Metnin ekleneceği yer", "hy": "Որտեղ տեղադրել տեքստը",
    },
    "gen.insertion_type": {
        "ru": "Печать в поле", "en": "Type into field", "de": "In Feld eintippen",
        "fr": "Saisir dans le champ", "es": "Escribir en el campo", "zh": "输入到字段",
        "tr": "Alana yazdır", "hy": "Մուտքագրել դաշտում",
    },
    "gen.insertion_paste": {
        "ru": "Буфер (Ctrl+V)", "en": "Clipboard (Ctrl+V)", "de": "Zwischenablage (Strg+V)",
        "fr": "Presse-papiers (Ctrl+V)", "es": "Portapapeles (Ctrl+V)", "zh": "剪贴板 (Ctrl+V)",
        "tr": "Pano (Ctrl+V)", "hy": "Փոխանակման բուֆեր (Ctrl+V)",
    },
    "gen.card_mic": {
        "ru": "Микрофон", "en": "Microphone", "de": "Mikrofon", "fr": "Microphone",
        "es": "Micrófono", "zh": "麦克风", "tr": "Mikrofon", "hy": "Խոսափող",
    },
    "gen.mic_default": {
        "ru": "Системный (по умолчанию)", "en": "System default", "de": "Systemstandard",
        "fr": "Système par défaut", "es": "Predeterminado del sistema", "zh": "系统默认",
        "tr": "Sistem varsayılanı", "hy": "Համակարգային (կանխադրված)",
    },
    "gen.mic_hint": {
        "ru": "Полезно, если в системе несколько микрофонов (например, встроенный в ноутбук и гарнитура).",
        "en": "Useful if the system has several microphones (e.g. a laptop's built-in mic and a headset).",
        "de": "Nützlich, wenn das System mehrere Mikrofone hat (z. B. das eingebaute Laptop-Mikrofon und ein Headset).",
        "fr": "Utile si le système possède plusieurs microphones (par ex. le micro intégré du portable et un casque).",
        "es": "Útil si el sistema tiene varios micrófonos (por ejemplo, el micrófono integrado del portátil y unos auriculares).",
        "zh": "如果系统有多个麦克风（例如笔记本内置麦克风和耳机麦克风）会很有用。",
        "tr": "Sistemde birden fazla mikrofon varsa kullanışlıdır (örneğin dizüstü bilgisayarın dahili mikrofonu ve kulaklık).",
        "hy": "Օգտակար է, եթե համակարգն ունի մի քանի խոսափող (օրինակ՝ նոութբուքի ներկառուցված և ականջակալի խոսափողը)։",
    },
    "gen.mic_mode_label": {
        "ru": "Когда микрофон открыт", "en": "When the microphone is open",
        "de": "Wann das Mikrofon geöffnet ist", "fr": "Quand le micro est ouvert",
        "es": "Cuándo está abierto el micrófono", "zh": "麦克风何时开启",
        "tr": "Mikrofon ne zaman açık", "hy": "Երբ խոսափողը բաց է",
    },
    "gen.mic_mode_lazy": {
        "ru": "Полминуты после", "en": "Half a minute after", "de": "Halbe Minute danach",
        "fr": "Demi-minute après", "es": "Medio minuto después", "zh": "结束后半分钟",
        "tr": "Sonrasında yarım dakika", "hy": "Կես րոպե հետո",
    },
    "gen.mic_mode_always": {
        "ru": "Всегда", "en": "Always", "de": "Immer", "fr": "Toujours",
        "es": "Siempre", "zh": "始终", "tr": "Her zaman", "hy": "Միշտ",
    },
    "gen.mic_mode_on_demand": {
        "ru": "Только во время диктовки", "en": "Only while dictating",
        "de": "Nur beim Diktieren", "fr": "Seulement pendant la dictée",
        "es": "Solo al dictar", "zh": "仅在口述时", "tr": "Yalnızca dikte sırasında",
        "hy": "Միայն թելադրության ժամանակ",
    },
    "gen.mic_mode_hint_lazy": {
        "ru": "По умолчанию. Микрофон остаётся открытым 30 секунд после диктовки, поэтому следующая фраза начинает записываться мгновенно.",
        "en": "The default. The microphone stays open for 30 seconds after a dictation, so the next phrase starts recording instantly.",
        "de": "Standard. Das Mikrofon bleibt nach einem Diktat 30 Sekunden offen, sodass der nächste Satz sofort aufgenommen wird.",
        "fr": "Par défaut. Le micro reste ouvert 30 secondes après une dictée, la phrase suivante démarre donc instantanément.",
        "es": "Opción predeterminada. El micrófono permanece abierto 30 segundos tras un dictado, así la siguiente frase empieza a grabarse al instante.",
        "zh": "默认选项。口述结束后麦克风保持开启 30 秒，因此下一句话可立即开始录制。",
        "tr": "Varsayılan. Mikrofon dikteden sonra 30 saniye açık kalır, böylece sonraki cümle anında kaydedilmeye başlar.",
        "hy": "Լռելյայն։ Խոսափողը թելադրությունից հետո բաց է մնում 30 վայրկյան, ուստի հաջորդ արտահայտությունն անմիջապես սկսում է ձայնագրվել։",
    },
    "gen.mic_mode_hint_always": {
        "ru": "Самый быстрый старт записи. Windows будет постоянно показывать значок «микрофон используется», а Bluetooth-гарнитуры переключатся в режим гарнитуры — музыка в них зазвучит хуже.",
        "en": "The fastest start. Windows will show the “microphone in use” indicator the whole time, and Bluetooth headsets switch to their headset profile — music through them sounds worse.",
        "de": "Der schnellste Start. Windows zeigt durchgehend das Symbol „Mikrofon wird verwendet“, und Bluetooth-Headsets wechseln in das Headset-Profil — Musik klingt darüber schlechter.",
        "fr": "Le démarrage le plus rapide. Windows affiche en permanence l'indicateur « micro utilisé » et les casques Bluetooth passent en profil casque — la musique y sonne moins bien.",
        "es": "El inicio más rápido. Windows mostrará todo el tiempo el indicador de «micrófono en uso» y los auriculares Bluetooth pasarán a su perfil de manos libres: la música sonará peor.",
        "zh": "启动最快。Windows 会一直显示“正在使用麦克风”图标，蓝牙耳机也会切换到耳机模式——音乐音质会变差。",
        "tr": "En hızlı başlangıç. Windows sürekli “mikrofon kullanımda” simgesini gösterir ve Bluetooth kulaklıklar kulaklık profiline geçer — müzik daha kötü duyulur.",
        "hy": "Ամենաարագ մեկնարկը։ Windows-ը մշտապես ցույց կտա «խոսափողն օգտագործվում է» նշանը, իսկ Bluetooth ականջակալները կանցնեն ականջակալի ռեժիմ — երաժշտությունը դրանցում կհնչի ավելի վատ։",
    },
    "gen.mic_mode_hint_on_demand": {
        "ru": "Микрофон не занят вообще ничем между диктовками, но открытие устройства занимает до 0,4 секунды — начало фразы может не попасть в запись.",
        "en": "The microphone is left entirely alone between dictations, but opening the device takes up to 0.4 s — the start of a phrase can be clipped.",
        "de": "Das Mikrofon bleibt zwischen Diktaten völlig unberührt, aber das Öffnen des Geräts dauert bis zu 0,4 s — der Anfang eines Satzes kann abgeschnitten werden.",
        "fr": "Le micro n'est pas sollicité entre les dictées, mais l'ouverture du périphérique prend jusqu'à 0,4 s — le début d'une phrase peut être coupé.",
        "es": "El micrófono queda completamente libre entre dictados, pero abrir el dispositivo tarda hasta 0,4 s: el principio de la frase puede cortarse.",
        "zh": "两次口述之间完全不占用麦克风，但打开设备需要最多 0.4 秒——句子开头可能被截掉。",
        "tr": "Mikrofon dikteler arasında hiç meşgul edilmez, ancak cihazın açılması 0,4 saniyeye kadar sürer — cümlenin başı kesilebilir.",
        "hy": "Խոսափողը թելադրությունների միջև ընդհանրապես զբաղված չէ, սակայն սարքի բացումը տևում է մինչև 0,4 վայրկյան — արտահայտության սկիզբը կարող է չգրանցվել։",
    },
    # 1.7.4 merged the theme and interface-language cards into one, so the
    # two separate titles this replaced are gone.
    "gen.card_appearance": {
        "ru": "Внешний вид и язык", "en": "Appearance & language", "de": "Aussehen & Sprache",
        "fr": "Apparence et langue", "es": "Apariencia e idioma", "zh": "外观与语言",
        "tr": "Görünüm ve dil", "hy": "Տեսք և լեզու",
    },
    "gen.card_app": {
        "ru": "Приложение", "en": "Application", "de": "Anwendung", "fr": "Application",
        "es": "Aplicación", "zh": "应用程序", "tr": "Uygulama", "hy": "Ծրագիր",
    },
    "gen.hotkey_assign_failed": {
        "ru": "Не удалось назначить {hotkey}: {error}", "en": "Couldn't assign {hotkey}: {error}",
        "de": "{hotkey} konnte nicht zugewiesen werden: {error}",
        "fr": "Impossible d'assigner {hotkey} : {error}", "es": "No se pudo asignar {hotkey}: {error}",
        "zh": "无法分配 {hotkey}：{error}", "tr": "{hotkey} atanamadı: {error}",
        "hy": "Չհաջողվեց նշանակել {hotkey}․ {error}",
    },
    "gen.autostart_switch": {
        "ru": "Запускать при входе в Windows", "en": "Start when Windows logs in",
        "de": "Beim Windows-Start ausführen", "fr": "Démarrer à l'ouverture de session Windows",
        "es": "Iniciar al iniciar sesión en Windows", "zh": "Windows 登录时启动",
        "tr": "Windows açılışında başlat", "hy": "Գործարկել Windows-ի մուտքի ժամանակ",
    },

    # ------------------------------------------------------- recognition tab
    # No longer Whisper-only: the picker also offers GigaAM and Parakeet.
    "rec.card_model": {
        "ru": "Модель распознавания", "en": "Recognition model", "de": "Erkennungsmodell",
        "fr": "Modèle de reconnaissance", "es": "Modelo de reconocimiento", "zh": "识别模型",
        "tr": "Tanıma modeli", "hy": "Ճանաչման մոդել",
    },
    "rec.langs_all": {
        "ru": "99 языков", "en": "99 languages", "de": "99 Sprachen",
        "fr": "99 langues", "es": "99 idiomas", "zh": "99 种语言",
        "tr": "99 dil", "hy": "99 լեզու",
    },
    "rec.langs_count": {
        "ru": "{n} языков", "en": "{n} languages", "de": "{n} Sprachen",
        "fr": "{n} langues", "es": "{n} idiomas", "zh": "{n} 种语言",
        "tr": "{n} dil", "hy": "{n} լեզու",
    },
    "rec.model_fixed_language": {
        "ru": "Эта модель распознаёт только один язык ({language}) — настройка языка ниже на неё не влияет.",
        "en": "This model recognises one language only ({language}) — the language setting below does not affect it.",
        "de": "Dieses Modell erkennt nur eine Sprache ({language}) — die Spracheinstellung unten wirkt sich nicht darauf aus.",
        "fr": "Ce modèle ne reconnaît qu'une seule langue ({language}) — le réglage de langue ci-dessous n'a aucun effet.",
        "es": "Este modelo reconoce un solo idioma ({language}): el ajuste de idioma de abajo no le afecta.",
        "zh": "该模型仅识别一种语言（{language}），下面的语言设置对其无效。",
        "tr": "Bu model yalnızca tek bir dili tanır ({language}) — aşağıdaki dil ayarı onu etkilemez.",
        "hy": "Այս մոդելը ճանաչում է միայն մեկ լեզու ({language}) — ստորև լեզվի կարգավորումը դրա վրա չի ազդում։",
    },
    "rec.model_detects_language": {
        "ru": "Эта модель определяет язык сама — настройка языка ниже на неё не влияет.",
        "en": "This model detects the language itself — the language setting below does not affect it.",
        "de": "Dieses Modell erkennt die Sprache selbst — die Spracheinstellung unten wirkt sich nicht darauf aus.",
        "fr": "Ce modèle détecte la langue lui-même — le réglage de langue ci-dessous n'a aucun effet.",
        "es": "Este modelo detecta el idioma por sí mismo: el ajuste de idioma de abajo no le afecta.",
        "zh": "该模型会自行检测语言，下面的语言设置对其无效。",
        "tr": "Bu model dili kendisi algılar — aşağıdaki dil ayarı onu etkilemez.",
        "hy": "Այս մոդելն ինքն է որոշում լեզուն — ստորև լեզվի կարգավորումը դրա վրա չի ազդում։",
    },
    "rec.model_hint": {
        "ru": "tiny/base — быстро · small — баланс · large-v3 — точнее",
        "en": "tiny/base — fast · small — balanced · large-v3 — most accurate",
        "de": "tiny/base — schnell · small — ausgewogen · large-v3 — genauer",
        "fr": "tiny/base — rapide · small — équilibré · large-v3 — plus précis",
        "es": "tiny/base — rápido · small — equilibrado · large-v3 — más preciso",
        "zh": "tiny/base — 速度快 · small — 均衡 · large-v3 — 更精确",
        "tr": "tiny/base — hızlı · small — dengeli · large-v3 — daha isabetli",
        "hy": "tiny/base — արագ · small — հավասարակշռված · large-v3 — ավելի ճշգրիտ",
    },
    "rec.btn_load_now": {
        "ru": "Загрузить модель сейчас", "en": "Load model now", "de": "Modell jetzt laden",
        "fr": "Charger le modèle maintenant", "es": "Cargar modelo ahora", "zh": "立即加载模型",
        "tr": "Modeli şimdi yükle", "hy": "Բեռնել մոդելը հիմա",
    },
    "rec.card_params": {
        "ru": "Параметры", "en": "Parameters", "de": "Parameter", "fr": "Paramètres",
        "es": "Parámetros", "zh": "参数", "tr": "Parametreler", "hy": "Պարամետրեր",
    },
    "rec.lang_label": {
        "ru": "Язык речи", "en": "Speech language", "de": "Sprachsprache", "fr": "Langue de la parole",
        "es": "Idioma del habla", "zh": "语音语言", "tr": "Konuşma dili", "hy": "Խոսքի լեզու",
    },
    "rec.threads_label": {
        "ru": "Потоков CPU: {n}", "en": "CPU threads: {n}", "de": "CPU-Threads: {n}",
        "fr": "Threads CPU : {n}", "es": "Hilos de CPU: {n}", "zh": "CPU 线程数：{n}",
        "tr": "CPU iş parçacığı: {n}", "hy": "CPU հոսքեր՝ {n}",
    },
    "rec.card_memory": {
        "ru": "Память", "en": "Memory", "de": "Speicher", "fr": "Mémoire",
        "es": "Memoria", "zh": "内存", "tr": "Bellek", "hy": "Հիշողություն",
    },
    "rec.unload_switch": {
        "ru": "Выгружать модель из ОЗУ при простое (>15 мин)",
        "en": "Unload model from RAM when idle (>15 min)",
        "de": "Modell bei Inaktivität aus dem RAM entladen (>15 Min.)",
        "fr": "Décharger le modèle de la RAM en cas d'inactivité (>15 min)",
        "es": "Descargar el modelo de la RAM en inactividad (>15 min)",
        "zh": "空闲时从内存卸载模型（超过15分钟）",
        "tr": "Boşta kalınca modeli RAM'den kaldır (>15 dk)",
        "hy": "Ապաբեռնել մոդելը հիշողությունից պարապուրդի ժամանակ (>15 րոպե)",
    },
    "rec.unload_hint": {
        "ru": "Освобождает 0.5–3 ГБ памяти на слабых ПК; следующая диктовка после простоя снова платит цену загрузки модели.",
        "en": "Frees 0.5–3 GB of memory on weaker PCs; the next dictation after idle pays the model-load cost again.",
        "de": "Gibt 0,5–3 GB Speicher auf schwächeren PCs frei; die nächste Diktierung nach Inaktivität lädt das Modell erneut.",
        "fr": "Libère 0,5 à 3 Go de mémoire sur les PC moins puissants ; la prochaine dictée après une inactivité recharge le modèle.",
        "es": "Libera de 0,5 a 3 GB de memoria en PC menos potentes; el siguiente dictado tras la inactividad vuelve a pagar el coste de carga del modelo.",
        "zh": "在性能较弱的电脑上可释放 0.5–3 GB 内存；空闲后下一次口述将重新承担模型加载开销。",
        "tr": "Daha zayıf bilgisayarlarda 0,5–3 GB bellek boşaltır; boşta kaldıktan sonraki ilk dikte yeniden model yükleme maliyetine katlanır.",
        "hy": "Ազատում է 0.5–3 ԳԲ հիշողություն թույլ համակարգիչներում. պարապուրդից հետո առաջին թելադրությունը կրկին վճարում է մոդելի բեռնման գինը։",
    },
    "rec.model_will_load": {
        "ru": "Загрузится при следующей диктовке или по кнопке ниже.",
        "en": "Will load on the next dictation, or via the button below.",
        "de": "Wird bei der nächsten Diktierung geladen oder über die Schaltfläche unten.",
        "fr": "Se chargera à la prochaine dictée, ou via le bouton ci-dessous.",
        "es": "Se cargará en el próximo dictado o mediante el botón de abajo.",
        "zh": "将在下次口述时加载，或通过下方按钮加载。",
        "tr": "Bir sonraki diktede veya aşağıdaki düğmeyle yüklenecek.",
        "hy": "Կբեռնվի հաջորդ թելադրության ժամանակ կամ ստորև կոճակով։",
    },

    # -------------------------------------------------------- refinement tab
    "ref.card_what": {
        "ru": "Что это", "en": "What this is", "de": "Was das ist", "fr": "De quoi s'agit-il",
        "es": "Qué es esto", "zh": "这是什么", "tr": "Bu nedir", "hy": "Ինչ է սա",
    },
    "ref.what_text": {
        "ru": "Необязательная функция: локальная нейросеть (LLM) исправляет ошибки распознавания и расставляет знаки препинания. Работает через бесплатную программу Ollama — полностью на этом компьютере, без интернета.",
        "en": "Optional feature: a local neural network (LLM) fixes recognition errors and adds punctuation. It runs through the free Ollama app — entirely on this computer, no internet required.",
        "de": "Optionale Funktion: Ein lokales neuronales Netz (LLM) korrigiert Erkennungsfehler und setzt Satzzeichen. Es läuft über die kostenlose App Ollama — vollständig auf diesem Computer, ohne Internet.",
        "fr": "Fonction facultative : un réseau de neurones local (LLM) corrige les erreurs de reconnaissance et ajoute la ponctuation. Il fonctionne via l'application gratuite Ollama — entièrement sur cet ordinateur, sans internet.",
        "es": "Función opcional: una red neuronal local (LLM) corrige los errores de reconocimiento y añade puntuación. Funciona a través de la aplicación gratuita Ollama — completamente en este ordenador, sin internet.",
        "zh": "可选功能：本地神经网络（LLM）会修正识别错误并添加标点符号。通过免费的 Ollama 程序运行——完全在本机进行，无需联网。",
        "tr": "İsteğe bağlı özellik: yerel bir sinir ağı (LLM) tanıma hatalarını düzeltir ve noktalama işaretleri ekler. Ücretsiz Ollama uygulaması üzerinden çalışır — tamamen bu bilgisayarda, internet olmadan.",
        "hy": "Ընտրովի գործառույթ․ տեղական նեյրոնային ցանցը (LLM) ուղղում է ճանաչման սխալները և դնում կետադրական նշաններ։ Աշխատում է անվճար Ollama ծրագրի միջոցով՝ ամբողջությամբ այս համակարգչում, առանց ինտերնետի։",
    },
    "ref.card_howto": {
        "ru": "Как включить (нужно один раз)", "en": "How to enable it (one-time setup)",
        "de": "So aktivierst du es (einmalige Einrichtung)", "fr": "Comment l'activer (configuration unique)",
        "es": "Cómo activarlo (configuración única)", "zh": "如何启用（一次性设置）",
        "tr": "Nasıl etkinleştirilir (tek seferlik kurulum)", "hy": "Ինչպես միացնել (մեկանգամյա կարգավորում)",
    },
    "ref.step1": {
        "ru": "1.  Установите Ollama (обычная программа для Windows, права администратора не нужны) — кнопка ниже откроет официальный сайт.",
        "en": "1.  Install Ollama (a regular Windows program, no admin rights needed) — the button below opens the official site.",
        "de": "1.  Installiere Ollama (ein normales Windows-Programm, keine Administratorrechte nötig) — die Schaltfläche unten öffnet die offizielle Website.",
        "fr": "1.  Installez Ollama (un programme Windows normal, aucun droit administrateur requis) — le bouton ci-dessous ouvre le site officiel.",
        "es": "1.  Instala Ollama (un programa normal de Windows, no requiere permisos de administrador) — el botón de abajo abre el sitio oficial.",
        "zh": "1.  安装 Ollama（普通的 Windows 程序，无需管理员权限）——下方按钮将打开官方网站。",
        "tr": "1.  Ollama'yı kurun (normal bir Windows programıdır, yönetici izni gerekmez) — aşağıdaki düğme resmi siteyi açar.",
        "hy": "1.  Տեղադրեք Ollama-ն (սովորական Windows ծրագիր է, ադմինիստրատորի իրավունքներ պետք չեն)՝ ստորև կոճակը կբացի պաշտոնական կայքը։",
    },
    "ref.step2": {
        "ru": "2.  После установки Ollama сама запускается и работает в фоне — значок появится в системном трее (рядом с часами). Если не видите его, запустите Ollama один раз из меню Пуск — без неё следующие шаги не сработают.",
        "en": "2.  Once installed, Ollama starts itself and runs in the background — its icon appears in the system tray (near the clock). If you don't see it, launch Ollama once from the Start menu — the next steps won't work without it.",
        "de": "2.  Nach der Installation startet Ollama automatisch und läuft im Hintergrund — ihr Symbol erscheint in der Taskleiste (neben der Uhr). Falls nicht sichtbar, starte Ollama einmal über das Startmenü — ohne sie funktionieren die nächsten Schritte nicht.",
        "fr": "2.  Une fois installé, Ollama démarre seul et fonctionne en arrière-plan — son icône apparaît dans la zone de notification (près de l'horloge). Si vous ne la voyez pas, lancez Ollama une fois depuis le menu Démarrer — les étapes suivantes ne fonctionneront pas sans elle.",
        "es": "2.  Una vez instalado, Ollama se inicia solo y se ejecuta en segundo plano — su icono aparece en la bandeja del sistema (junto al reloj). Si no lo ves, abre Ollama una vez desde el menú Inicio — los siguientes pasos no funcionarán sin él.",
        "zh": "2.  安装后 Ollama 会自动启动并在后台运行——其图标会出现在系统托盘（时钟附近）。如果没看到，请从开始菜单启动一次 Ollama——没有它后续步骤将无法进行。",
        "tr": "2.  Kurulduktan sonra Ollama kendiliğinden başlar ve arka planda çalışır — simgesi sistem tepsisinde (saatin yanında) görünür. Görmüyorsanız Başlat menüsünden Ollama'yı bir kez çalıştırın — o olmadan sonraki adımlar işe yaramaz.",
        "hy": "2.  Տեղադրումից հետո Ollama-ն ինքն է գործարկվում և աշխատում ֆոնային ռեժիմում՝ պատկերակը կհայտնվի համակարգային վահանակում (ժամացույցի կողքին)։ Եթե չեք տեսնում՝ մեկ անգամ գործարկեք Ollama-ն Մեկնարկի ցանկից․ առանց դրա հաջորդ քայլերը չեն աշխատի։",
    },
    "ref.step3": {
        "ru": "3.  Скачайте модель: вторая кнопка скопирует команду — вставьте её\n     в окно «Терминал» (Win+X → Терминал) и нажмите Enter. Модель весит\n     около 2 ГБ — загрузка может занять несколько минут, дождитесь,\n     пока команда закончится.",
        "en": "3.  Download a model: the second button copies the command — paste it\n     into the Terminal window (Win+X → Terminal) and press Enter. The\n     model is about 2 GB — downloading can take several minutes, wait\n     for the command to finish.",
        "de": "3.  Lade ein Modell herunter: die zweite Schaltfläche kopiert den Befehl —\n     füge ihn ins Terminal-Fenster ein (Win+X → Terminal) und drücke\n     Enter. Das Modell ist etwa 2 GB groß — der Download kann einige\n     Minuten dauern, warte, bis der Befehl abgeschlossen ist.",
        "fr": "3.  Téléchargez un modèle : le deuxième bouton copie la commande —\n     collez-la dans la fenêtre Terminal (Win+X → Terminal) et appuyez\n     sur Entrée. Le modèle pèse environ 2 Go — le téléchargement peut\n     prendre plusieurs minutes, attendez que la commande se termine.",
        "es": "3.  Descarga un modelo: el segundo botón copia el comando — pégalo\n     en la ventana de Terminal (Win+X → Terminal) y pulsa Intro. El\n     modelo pesa unos 2 GB — la descarga puede tardar varios minutos,\n     espera a que el comando termine.",
        "zh": "3.  下载模型：第二个按钮会复制命令——将其粘贴到\n     「终端」窗口（Win+X → 终端）中并按 Enter。模型大小约\n     2 GB——下载可能需要几分钟，请等待命令执行完毕。",
        "tr": "3.  Bir model indirin: ikinci düğme komutu kopyalar — bunu\n     Terminal penceresine yapıştırın (Win+X → Terminal) ve Enter'a\n     basın. Model yaklaşık 2 GB'dır — indirme birkaç dakika sürebilir,\n     komutun bitmesini bekleyin.",
        "hy": "3.  Ներբեռնեք մոդել՝ երկրորդ կոճակը կպատճենի հրամանը՝ տեղադրեք այն\n     «Տերմինալ» պատուհանում (Win+X → Տերմինալ) և սեղմեք Enter։ Մոդելը\n     կշռում է շուրջ 2 ԳԲ՝ ներբեռնումը կարող է տևել մի քանի րոպե,\n     սպասեք, մինչև հրամանն ավարտվի։",
    },
    "ref.step4": {
        "ru": "4.  Нажмите «Проверить» внизу. Пишет «не запущена» — проверьте шаг 2.\n     Пишет «моделей нет» — значит шаг 3 ещё не завершился, попробуйте\n     команду ещё раз.",
        "en": "4.  Click \"Check\" below. If it says \"not running\" — see step 2.\n     If it says \"no models\" — step 3 hasn't finished yet, try the\n     command again.",
        "de": "4.  Klicke unten auf „Prüfen“. Steht dort „läuft nicht“ — sieh dir\n     Schritt 2 an. Steht dort „keine Modelle“ — Schritt 3 ist noch\n     nicht fertig, versuche den Befehl erneut.",
        "fr": "4.  Cliquez sur « Vérifier » en bas. Message « non lancé » — voyez\n     l'étape 2. Message « aucun modèle » — l'étape 3 n'est pas encore\n     terminée, réessayez la commande.",
        "es": "4.  Haz clic en «Comprobar» abajo. Si dice «no está en ejecución» —\n     revisa el paso 2. Si dice «no hay modelos» — el paso 3 aún no ha\n     terminado, prueba el comando de nuevo.",
        "zh": "4.  点击下方的「检查」。如果显示「未运行」——请查看第 2 步。\n     如果显示「没有模型」——说明第 3 步尚未完成，请重试该命令。",
        "tr": "4.  Aşağıdaki \"Kontrol Et\"e tıklayın. \"Çalışmıyor\" yazıyorsa — 2.\n     adıma bakın. \"Model yok\" yazıyorsa — 3. adım henüz tamamlanmadı,\n     komutu tekrar deneyin.",
        "hy": "4.  Սեղմեք ստորև «Ստուգել»-ը։ Եթե գրում է «չի աշխատում»՝ ստուգեք\n     2-րդ քայլը։ Եթե գրում է «մոդելներ չկան»՝ 3-րդ քայլը դեռ չի\n     ավարտվել, կրկին փորձեք հրամանը։",
    },
    "ref.step5": {
        "ru": "5.  Включите переключатель «Улучшать текст…» ниже.",
        "en": "5.  Turn on the \"Refine text…\" switch below.",
        "de": "5.  Aktiviere den Schalter „Text verbessern…“ unten.",
        "fr": "5.  Activez le commutateur « Améliorer le texte… » ci-dessous.",
        "es": "5.  Activa el interruptor «Mejorar texto…» de abajo.",
        "zh": "5.  打开下方的「使用本地 LLM 优化文本」开关。",
        "tr": "5.  Aşağıdaki \"Metni iyileştir…\" anahtarını açın.",
        "hy": "5.  Միացրեք ստորև «Բարելավել տեքստը…» անջատիչը։",
    },
    "ref.btn_ollama_site": {
        "ru": "🌐 Открыть сайт Ollama", "en": "🌐 Open Ollama's site", "de": "🌐 Ollama-Website öffnen",
        "fr": "🌐 Ouvrir le site d'Ollama", "es": "🌐 Abrir el sitio de Ollama", "zh": "🌐 打开 Ollama 网站",
        "tr": "🌐 Ollama sitesini aç", "hy": "🌐 Բացել Ollama կայքը",
    },
    "ref.btn_copy_pull": {
        "ru": "⧉ Скопировать команду модели", "en": "⧉ Copy model command", "de": "⧉ Modellbefehl kopieren",
        "fr": "⧉ Copier la commande du modèle", "es": "⧉ Copiar comando del modelo", "zh": "⧉ 复制模型命令",
        "tr": "⧉ Model komutunu kopyala", "hy": "⧉ Պատճենել մոդելի հրամանը",
    },
    "ref.copied_pull": {
        "ru": "Скопировано ✓  (вставьте в Терминал)", "en": "Copied ✓  (paste into Terminal)",
        "de": "Kopiert ✓  (ins Terminal einfügen)", "fr": "Copié ✓  (collez dans le Terminal)",
        "es": "Copiado ✓  (pégalo en Terminal)", "zh": "已复制 ✓（粘贴到终端）",
        "tr": "Kopyalandı ✓  (Terminal'e yapıştırın)", "hy": "Պատճենվեց ✓  (տեղադրեք Տերմինալում)",
    },
    "ref.card_settings": {
        "ru": "Настройки Ollama", "en": "Ollama settings", "de": "Ollama-Einstellungen",
        "fr": "Paramètres Ollama", "es": "Ajustes de Ollama", "zh": "Ollama 设置",
        "tr": "Ollama ayarları", "hy": "Ollama կարգավորումներ",
    },
    "ref.enable_switch": {
        "ru": "Улучшать текст локальной LLM", "en": "Refine text with a local LLM",
        "de": "Text mit lokalem LLM verbessern", "fr": "Améliorer le texte avec un LLM local",
        "es": "Mejorar el texto con un LLM local", "zh": "使用本地 LLM 优化文本",
        "tr": "Yerel LLM ile metni iyileştir", "hy": "Բարելավել տեքստը տեղական LLM-ով",
    },
    "ref.model_placeholder": {
        "ru": "модель, напр. qwen2.5:3b", "en": "model, e.g. qwen2.5:3b", "de": "Modell, z. B. qwen2.5:3b",
        "fr": "modèle, p. ex. qwen2.5:3b", "es": "modelo, p. ej. qwen2.5:3b", "zh": "模型，例如 qwen2.5:3b",
        "tr": "model, örn. qwen2.5:3b", "hy": "մոդել, օր. qwen2.5:3b",
    },
    "ref.checking": {
        "ru": "Проверка…", "en": "Checking…", "de": "Wird geprüft…", "fr": "Vérification…",
        "es": "Comprobando…", "zh": "正在检查…", "tr": "Kontrol ediliyor…", "hy": "Ստուգում…",
    },
    "ref.available": {
        "ru": "Доступно: {names}", "en": "Available: {names}", "de": "Verfügbar: {names}",
        "fr": "Disponible : {names}", "es": "Disponible: {names}", "zh": "可用：{names}",
        "tr": "Mevcut: {names}", "hy": "Հասանելի է․ {names}",
    },
    "ref.no_models": {
        "ru": "Ollama работает, но моделей нет — шаг 2 в инструкции выше.",
        "en": "Ollama is running but has no models — see step 2 above.",
        "de": "Ollama läuft, aber es sind keine Modelle vorhanden — siehe Schritt 2 oben.",
        "fr": "Ollama fonctionne mais n'a aucun modèle — voir l'étape 2 ci-dessus.",
        "es": "Ollama está en ejecución pero no tiene modelos — consulta el paso 2 anterior.",
        "zh": "Ollama 正在运行，但没有模型——请参见上方步骤 2。",
        "tr": "Ollama çalışıyor ama model yok — yukarıdaki 2. adıma bakın.",
        "hy": "Ollama-ն աշխատում է, բայց մոդելներ չկան՝ տես վերևի 2-րդ քայլը։",
    },
    "ref.non_local": {
        "ru": "Адрес должен быть localhost.", "en": "The address must be localhost.",
        "de": "Die Adresse muss localhost sein.", "fr": "L'adresse doit être localhost.",
        "es": "La dirección debe ser localhost.", "zh": "地址必须是 localhost。",
        "tr": "Adres localhost olmalıdır.", "hy": "Հասցեն պետք է լինի localhost։",
    },
    "ref.not_running": {
        "ru": "Ollama не запущена или не установлена: {error}",
        "en": "Ollama is not running or not installed: {error}",
        "de": "Ollama läuft nicht oder ist nicht installiert: {error}",
        "fr": "Ollama n'est pas lancé ou n'est pas installé : {error}",
        "es": "Ollama no se está ejecutando o no está instalado: {error}",
        "zh": "Ollama 未运行或未安装：{error}",
        "tr": "Ollama çalışmıyor veya kurulu değil: {error}",
        "hy": "Ollama-ն չի աշխատում կամ տեղադրված չէ․ {error}",
    },
    "ref.btn_check": {
        "ru": "Проверить", "en": "Check", "de": "Prüfen", "fr": "Vérifier",
        "es": "Comprobar", "zh": "检查", "tr": "Kontrol Et", "hy": "Ստուգել",
    },

    # ------------------------------------------------------------ privacy tab
    "priv.card_data": {
        "ru": "Как WinDictoo обращается с данными", "en": "How WinDictoo handles data",
        "de": "Wie WinDictoo mit Daten umgeht", "fr": "Comment WinDictoo traite les données",
        "es": "Cómo maneja WinDictoo los datos", "zh": "WinDictoo 如何处理数据",
        "tr": "WinDictoo verileri nasıl işler", "hy": "Ինչպես է WinDictoo-ն վարվում տվյալների հետ",
    },
    "priv.p1": {
        "ru": "Звук обрабатывается только на этом компьютере.", "en": "Audio is processed only on this computer.",
        "de": "Audio wird ausschließlich auf diesem Computer verarbeitet.",
        "fr": "L'audio est traité uniquement sur cet ordinateur.",
        "es": "El audio se procesa únicamente en este ordenador.", "zh": "音频仅在本机处理。",
        "tr": "Ses yalnızca bu bilgisayarda işlenir.", "hy": "Ձայնը մշակվում է միայն այս համակարգչում։",
    },
    "priv.p2": {
        "ru": "Без облака, аккаунтов и ключей API.", "en": "No cloud, accounts, or API keys.",
        "de": "Keine Cloud, keine Konten, keine API-Schlüssel.",
        "fr": "Pas de cloud, de comptes ni de clés API.", "es": "Sin nube, cuentas ni claves de API.",
        "zh": "无云服务、账户或 API 密钥。", "tr": "Bulut, hesap veya API anahtarı yok.",
        "hy": "Ոչ ամպ, ոչ հաշիվներ, ոչ API բանալիներ։",
    },
    "priv.p3": {
        "ru": "Аудио не сохраняется на диск.", "en": "Audio is never saved to disk.",
        "de": "Audio wird nie auf der Festplatte gespeichert.", "fr": "L'audio n'est jamais enregistré sur le disque.",
        "es": "El audio nunca se guarda en el disco.", "zh": "音频不会保存到磁盘。",
        "tr": "Ses hiçbir zaman diske kaydedilmez.", "hy": "Ձայնը երբեք չի պահվում սկավառակի վրա։",
    },
    "priv.p4": {
        "ru": "Ollama — только localhost.", "en": "Ollama — localhost only.", "de": "Ollama — nur localhost.",
        "fr": "Ollama — localhost uniquement.", "es": "Ollama — solo localhost.", "zh": "Ollama——仅限 localhost。",
        "tr": "Ollama — yalnızca localhost.", "hy": "Ollama — միայն localhost։",
    },
    "priv.p5": {
        "ru": "Нет аналитики и телеметрии.", "en": "No analytics or telemetry.",
        "de": "Keine Analyse, keine Telemetrie.", "fr": "Aucune analyse ni télémétrie.",
        "es": "Sin analítica ni telemetría.", "zh": "无分析或遥测数据收集。",
        "tr": "Analitik veya telemetri yok.", "hy": "Ոչ վերլուծություն, ոչ հեռաչափում։",
    },
    "priv.card_diagnostics": {
        "ru": "Диагностика", "en": "Diagnostics", "de": "Diagnose", "fr": "Diagnostic",
        "es": "Diagnóstico", "zh": "诊断", "tr": "Tanılama", "hy": "Ախտորոշում",
    },
    "priv.btn_show_onboarding": {
        "ru": "Показать мастер настройки снова", "en": "Show the setup wizard again",
        "de": "Einrichtungsassistenten erneut anzeigen", "fr": "Réafficher l'assistant de configuration",
        "es": "Mostrar de nuevo el asistente de configuración", "zh": "再次显示设置向导",
        "tr": "Kurulum sihirbazını tekrar göster", "hy": "Կրկին ցույց տալ կարգավորման հրաշագործը",
    },
    "priv.btn_open_log": {
        "ru": "Открыть журнал", "en": "Open log", "de": "Protokoll öffnen", "fr": "Ouvrir le journal",
        "es": "Abrir registro", "zh": "打开日志", "tr": "Günlüğü aç", "hy": "Բացել մատյանը",
    },
    "priv.btn_open_config": {
        "ru": "Открыть папку настроек", "en": "Open settings folder", "de": "Einstellungsordner öffnen",
        "fr": "Ouvrir le dossier des paramètres", "es": "Abrir carpeta de ajustes", "zh": "打开设置文件夹",
        "tr": "Ayarlar klasörünü aç", "hy": "Բացել կարգավորումների պանակը",
    },
    "priv.card_about": {
        "ru": "О программе", "en": "About", "de": "Über", "fr": "À propos",
        "es": "Acerca de", "zh": "关于", "tr": "Hakkında", "hy": "Ծրագրի մասին",
    },
    "priv.about_license": {
        "ru": "Открытый код, лицензия MIT — свободно для любого использования, изменения и распространения.",
        "en": "Open source, MIT license — free to use, modify, and distribute for any purpose.",
        "de": "Open Source, MIT-Lizenz — frei nutzbar, änderbar und weitergebbar für jeden Zweck.",
        "fr": "Open source, licence MIT — libre d'utilisation, de modification et de distribution.",
        "es": "Código abierto, licencia MIT — libre de usar, modificar y distribuir para cualquier fin.",
        "zh": "开源，MIT 许可证——可自由用于任何用途、修改和分发。",
        "tr": "Açık kaynak, MIT lisansı — her amaçla özgürce kullanılabilir, değiştirilebilir ve dağıtılabilir.",
        "hy": "Բաց կոդ, MIT լիցենզիա՝ ազատորեն կիրառելի, փոփոխելի և տարածելի ցանկացած նպատակով։",
    },
    "priv.btn_github": {
        "ru": "🌐 Открыть на GitHub", "en": "🌐 Open on GitHub", "de": "🌐 Auf GitHub öffnen",
        "fr": "🌐 Ouvrir sur GitHub", "es": "🌐 Abrir en GitHub", "zh": "🌐 在 GitHub 上打开",
        "tr": "🌐 GitHub'da aç", "hy": "🌐 Բացել GitHub-ում",
    },
    "priv.btn_check_updates": {
        "ru": "🔄 Проверить обновления", "en": "🔄 Check for updates", "de": "🔄 Nach Updates suchen",
        "fr": "🔄 Vérifier les mises à jour", "es": "🔄 Buscar actualizaciones", "zh": "🔄 检查更新",
        "tr": "🔄 Güncellemeleri kontrol et", "hy": "🔄 Ստուգել թարմացումները",
    },
    "priv.btn_eventkauf": {
        "ru": "🔗 Поддержка от eventkauf.com", "en": "🔗 Support by eventkauf.com",
        "de": "🔗 Unterstützt von eventkauf.com", "fr": "🔗 Soutenu par eventkauf.com",
        "es": "🔗 Con el apoyo de eventkauf.com", "zh": "🔗 由 eventkauf.com 支持",
        "tr": "🔗 eventkauf.com desteğiyle", "hy": "🔗 Աջակցությունը՝ eventkauf.com",
    },
    "priv.no_updates": {
        "ru": "Обновлений нет — установлена последняя версия.", "en": "No updates — you have the latest version.",
        "de": "Keine Updates — du hast die neueste Version.", "fr": "Aucune mise à jour — vous avez la dernière version.",
        "es": "Sin actualizaciones — tienes la última versión.", "zh": "没有更新——已是最新版本。",
        "tr": "Güncelleme yok — en son sürüme sahipsiniz.", "hy": "Թարմացումներ չկան՝ տեղադրված է վերջին տարբերակը։",
    },

    # ------------------------------------------------------------ update dialog
    "upd.available_short": {
        "ru": "Доступна версия {version}.", "en": "Version {version} is available.",
        "de": "Version {version} ist verfügbar.", "fr": "La version {version} est disponible.",
        "es": "La versión {version} está disponible.", "zh": "版本 {version} 可用。",
        "tr": "{version} sürümü mevcut.", "hy": "Հասանելի է {version} տարբերակը։",
    },
    "upd.banner": {
        "ru": "🔔  Доступна версия {version} — что нового", "en": "🔔  Version {version} is available — what's new",
        "de": "🔔  Version {version} verfügbar — was ist neu", "fr": "🔔  Version {version} disponible — nouveautés",
        "es": "🔔  Versión {version} disponible — novedades", "zh": "🔔  版本 {version} 现已发布——查看更新内容",
        "tr": "🔔  {version} sürümü mevcut — yenilikler", "hy": "🔔  Հասանելի է {version} տարբերակը՝ ինչն է նոր",
    },
    "upd.dialog_title": {
        "ru": "Доступно обновление", "en": "Update available", "de": "Update verfügbar",
        "fr": "Mise à jour disponible", "es": "Actualización disponible", "zh": "有可用更新",
        "tr": "Güncelleme mevcut", "hy": "Առկա է թարմացում",
    },
    "upd.whats_new": {
        "ru": "Что нового:", "en": "What's new:", "de": "Was ist neu:", "fr": "Nouveautés :",
        "es": "Novedades:", "zh": "更新内容：", "tr": "Yenilikler:", "hy": "Ինչն է նոր.",
    },
    "upd.no_notes": {
        "ru": "(без описания)", "en": "(no description)", "de": "(keine Beschreibung)",
        "fr": "(aucune description)", "es": "(sin descripción)", "zh": "（无说明）",
        "tr": "(açıklama yok)", "hy": "(նկարագրություն չկա)",
    },
    "upd.btn_install": {
        "ru": "⬇ Скачать и установить", "en": "⬇ Download and install", "de": "⬇ Herunterladen und installieren",
        "fr": "⬇ Télécharger et installer", "es": "⬇ Descargar e instalar", "zh": "⬇ 下载并安装",
        "tr": "⬇ İndir ve yükle", "hy": "⬇ Ներբեռնել և տեղադրել",
    },
    "upd.btn_release_page": {
        "ru": "Страница релиза", "en": "Release page", "de": "Release-Seite", "fr": "Page de la version",
        "es": "Página de la versión", "zh": "发布页面", "tr": "Sürüm sayfası", "hy": "Թողարկման էջ",
    },
    "upd.downloading": {
        "ru": "Скачиваю…", "en": "Downloading…", "de": "Wird heruntergeladen…", "fr": "Téléchargement…",
        "es": "Descargando…", "zh": "正在下载…", "tr": "İndiriliyor…", "hy": "Ներբեռնում եմ…",
    },
    "upd.failed": {
        "ru": "Не удалось: {error}", "en": "Failed: {error}", "de": "Fehlgeschlagen: {error}",
        "fr": "Échec : {error}", "es": "Fallo: {error}", "zh": "失败：{error}",
        "tr": "Başarısız: {error}", "hy": "Չհաջողվեց․ {error}",
    },

    # -------------------------------------------------------------- old versions
    "old.banner": {
        "ru": "🧹  Найдены старые версии ({names}) — очистить?",
        "en": "🧹  Older versions found ({names}) — clean up?",
        "de": "🧹  Ältere Versionen gefunden ({names}) — bereinigen?",
        "fr": "🧹  Anciennes versions trouvées ({names}) — nettoyer ?",
        "es": "🧹  Se encontraron versiones antiguas ({names}) — ¿limpiar?",
        "zh": "🧹  发现旧版本（{names}）——是否清理？",
        "tr": "🧹  Eski sürümler bulundu ({names}) — temizlensin mi?",
        "hy": "🧹  Հայտնաբերվել են հին տարբերակներ ({names})՝ մաքրե՞լ",
    },
    "old.dialog_title": {
        "ru": "Старые версии", "en": "Old versions", "de": "Alte Versionen", "fr": "Anciennes versions",
        "es": "Versiones antiguas", "zh": "旧版本", "tr": "Eski sürümler", "hy": "Հին տարբերակներ",
    },
    "old.found_title": {
        "ru": "Найдены более старые установки", "en": "Older installations found",
        "de": "Ältere Installationen gefunden", "fr": "Anciennes installations trouvées",
        "es": "Se encontraron instalaciones antiguas", "zh": "发现较旧的安装",
        "tr": "Daha eski kurulumlar bulundu", "hy": "Հայտնաբերվել են ավելի հին տեղադրումներ",
    },
    "old.explain": {
        "ru": "WinDictoo раньше назывался иначе (VoxWin, WnDic). Их установки остались отдельно от текущей — можно безопасно удалить.",
        "en": "WinDictoo used to have different names (VoxWin, WnDic). Their installations are separate from the current one — they can be safely removed.",
        "de": "WinDictoo hieß früher anders (VoxWin, WnDic). Deren Installationen sind getrennt von der aktuellen — sie können bedenkenlos entfernt werden.",
        "fr": "WinDictoo s'appelait autrefois différemment (VoxWin, WnDic). Leurs installations sont distinctes de l'actuelle — elles peuvent être supprimées en toute sécurité.",
        "es": "WinDictoo antes tenía otros nombres (VoxWin, WnDic). Sus instalaciones son independientes de la actual — se pueden eliminar sin problema.",
        "zh": "WinDictoo 以前有其他名称（VoxWin、WnDic）。它们的安装与当前版本是分开的——可以安全删除。",
        "tr": "WinDictoo eskiden farklı adlar taşıyordu (VoxWin, WnDic). Bunların kurulumları mevcut olandan ayrıdır — güvenle kaldırılabilirler.",
        "hy": "WinDictoo-ն նախկինում այլ անուններ ուներ (VoxWin, WnDic)։ Դրանց տեղադրումները առանձին են ընթացիկից՝ կարելի է անվտանգ հեռացնել։",
    },
    "old.btn_remove": {
        "ru": "🗑 Удалить старые версии", "en": "🗑 Remove old versions", "de": "🗑 Alte Versionen entfernen",
        "fr": "🗑 Supprimer les anciennes versions", "es": "🗑 Eliminar versiones antiguas", "zh": "🗑 删除旧版本",
        "tr": "🗑 Eski sürümleri kaldır", "hy": "🗑 Հեռացնել հին տարբերակները",
    },
    "old.removing": {
        "ru": "Удаляю…", "en": "Removing…", "de": "Wird entfernt…", "fr": "Suppression…",
        "es": "Eliminando…", "zh": "正在删除…", "tr": "Kaldırılıyor…", "hy": "Հեռացնում եմ…",
    },
    "old.done_ok": {
        "ru": "Готово — старые ярлыки исчезнут через несколько секунд.",
        "en": "Done — the old shortcuts will disappear in a few seconds.",
        "de": "Fertig — die alten Verknüpfungen verschwinden in wenigen Sekunden.",
        "fr": "Terminé — les anciens raccourcis disparaîtront dans quelques secondes.",
        "es": "Listo — los accesos directos antiguos desaparecerán en unos segundos.",
        "zh": "完成——旧的快捷方式将在几秒钟后消失。",
        "tr": "Tamamlandı — eski kısayollar birkaç saniye içinde kaybolacak.",
        "hy": "Պատրաստ է՝ հին դյուրանցումները կվերանան մի քանի վայրկյանից։",
    },
    "old.done_partial": {
        "ru": "Не всё получилось удалить — можно вручную через «Установка и удаление программ».",
        "en": "Not everything could be removed — you can do it manually via \"Apps & features\".",
        "de": "Nicht alles konnte entfernt werden — du kannst es manuell über „Apps & Features“ tun.",
        "fr": "Tout n'a pas pu être supprimé — vous pouvez le faire manuellement via « Applications et fonctionnalités ».",
        "es": "No se pudo eliminar todo — puedes hacerlo manualmente desde «Aplicaciones y características».",
        "zh": "并非全部删除成功——可以通过「应用和功能」手动删除。",
        "tr": "Her şey kaldırılamadı — \"Uygulamalar ve özellikler\" üzerinden elle yapabilirsiniz.",
        "hy": "Ամեն ինչ չհաջողվեց հեռացնել՝ կարող եք ձեռքով անել «Ծրագրեր և գործառույթներ»-ի միջոցով։",
    },

    # -------------------------------------------------------------------- preload
    "preload.loading": {
        "ru": "Загружаю модель распознавания…", "en": "Loading recognition model…",
        "de": "Erkennungsmodell wird geladen…", "fr": "Chargement du modèle de reconnaissance…",
        "es": "Cargando modelo de reconocimiento…", "zh": "正在加载识别模型…",
        "tr": "Tanıma modeli yükleniyor…", "hy": "Բեռնում եմ ճանաչման մոդելը…",
    },
    "preload.failed": {
        "ru": "Модель не загрузилась: {error}", "en": "Model failed to load: {error}",
        "de": "Modell konnte nicht geladen werden: {error}", "fr": "Échec du chargement du modèle : {error}",
        "es": "No se pudo cargar el modelo: {error}", "zh": "模型加载失败：{error}",
        "tr": "Model yüklenemedi: {error}", "hy": "Մոդելը չբեռնվեց․ {error}",
    },

    # ------------------------------------------------------------------- onboarding
    "ob.window_title": {
        "ru": "Настройка WinDictoo", "en": "WinDictoo Setup", "de": "WinDictoo-Einrichtung",
        "fr": "Configuration de WinDictoo", "es": "Configuración de WinDictoo", "zh": "WinDictoo 设置向导",
        "tr": "WinDictoo Kurulumu", "hy": "WinDictoo կարգավորում",
    },
    "ob.btn_back": {
        "ru": "Назад", "en": "Back", "de": "Zurück", "fr": "Retour", "es": "Atrás",
        "zh": "上一步", "tr": "Geri", "hy": "Հետ",
    },
    "ob.btn_skip": {
        "ru": "Пропустить", "en": "Skip", "de": "Überspringen", "fr": "Ignorer", "es": "Omitir",
        "zh": "跳过", "tr": "Atla", "hy": "Բաց թողնել",
    },
    "ob.btn_next": {
        "ru": "Далее", "en": "Next", "de": "Weiter", "fr": "Suivant", "es": "Siguiente",
        "zh": "下一步", "tr": "İleri", "hy": "Հաջորդը",
    },
    "ob.btn_start_using": {
        "ru": "Начать!", "en": "Get started!", "de": "Loslegen!", "fr": "Commencer !", "es": "¡Empezar!",
        "zh": "开始使用！", "tr": "Başla!", "hy": "Սկսել!",
    },
    "ob.welcome_title": {
        "ru": "Добро пожаловать", "en": "Welcome", "de": "Willkommen", "fr": "Bienvenue",
        "es": "Bienvenido", "zh": "欢迎", "tr": "Hoş geldiniz", "hy": "Բարի գալուստ",
    },
    "ob.welcome_text": {
        "ru": "Поставьте курсор в любое поле, зажмите горячую клавишу, продиктуйте —\nтекст появится прямо там.",
        "en": "Place the cursor in any field, hold the hotkey, dictate —\nthe text will appear right there.",
        "de": "Setze den Cursor in ein beliebiges Feld, halte die Tastenkombination gedrückt, diktiere —\nder Text erscheint genau dort.",
        "fr": "Placez le curseur dans un champ, maintenez le raccourci, dictez —\nle texte apparaîtra directement là.",
        "es": "Coloca el cursor en cualquier campo, mantén pulsado el atajo, dicta —\nel texto aparecerá justo ahí.",
        "zh": "将光标放在任意输入框中，按住快捷键，开始口述——\n文本会直接出现在那里。",
        "tr": "İmleci herhangi bir alana yerleştirin, kısayolu basılı tutun, konuşun —\nmetin tam orada belirecek.",
        "hy": "Կուրսորը դրեք ցանկացած դաշտում, պահեք դյուրանցումը, թելադրեք —\nտեքստը կհայտնվի հենց այնտեղ։",
    },
    "ob.mic_title": {
        "ru": "Микрофон", "en": "Microphone", "de": "Mikrofon", "fr": "Microphone",
        "es": "Micrófono", "zh": "麦克风", "tr": "Mikrofon", "hy": "Խոսափող",
    },
    "ob.mic_found": {
        "ru": "Найдено устройств ввода: {n}", "en": "Input devices found: {n}",
        "de": "Gefundene Eingabegeräte: {n}", "fr": "Périphériques d'entrée trouvés : {n}",
        "es": "Dispositivos de entrada encontrados: {n}", "zh": "找到输入设备：{n}",
        "tr": "Bulunan giriş aygıtları: {n}", "hy": "Հայտնաբերված մուտքային սարքեր՝ {n}",
    },
    "ob.mic_none": {
        "ru": "нет — подключите микрофон", "en": "none — connect a microphone",
        "de": "keine — schließe ein Mikrofon an", "fr": "aucun — connectez un microphone",
        "es": "ninguno — conecta un micrófono", "zh": "无——请连接麦克风",
        "tr": "yok — bir mikrofon bağlayın", "hy": "չկա՝ միացրեք խոսափող",
    },
    "ob.mic_btn_test": {
        "ru": "🎤  Проверить микрофон", "en": "🎤  Test microphone", "de": "🎤  Mikrofon testen",
        "fr": "🎤  Tester le microphone", "es": "🎤  Probar micrófono", "zh": "🎤  测试麦克风",
        "tr": "🎤  Mikrofonu test et", "hy": "🎤  Ստուգել խոսափողը",
    },
    "ob.mic_btn_stop": {
        "ru": "⏹  Остановить", "en": "⏹  Stop", "de": "⏹  Stopp", "fr": "⏹  Arrêter",
        "es": "⏹  Detener", "zh": "⏹  停止", "tr": "⏹  Durdur", "hy": "⏹  Կանգնեցնել",
    },
    "ob.mic_hint": {
        "ru": "Скажите что-нибудь — полоски должны двигаться. Если нет — проверьте\nПараметры Windows → Конфиденциальность → Микрофон.",
        "en": "Say something — the bars should move. If not, check\nWindows Settings → Privacy → Microphone.",
        "de": "Sag etwas — die Balken sollten sich bewegen. Falls nicht, prüfe\nWindows-Einstellungen → Datenschutz → Mikrofon.",
        "fr": "Dites quelque chose — les barres devraient bouger. Sinon, vérifiez\nParamètres Windows → Confidentialité → Microphone.",
        "es": "Di algo — las barras deberían moverse. Si no, comprueba\nConfiguración de Windows → Privacidad → Micrófono.",
        "zh": "请说点什么——音量条应有反应。如果没有，请检查\nWindows 设置 → 隐私 → 麦克风。",
        "tr": "Bir şeyler söyleyin — çubuklar hareket etmeli. Etmiyorsa\nWindows Ayarları → Gizlilik → Mikrofon'u kontrol edin.",
        "hy": "Ասեք ինչ-որ բան՝ գծերը պետք է շարժվեն։ Եթե ոչ՝ ստուգեք\nWindows կարգավորումներ → Գաղտնիություն → Խոսափող։",
    },
    "ob.model_title": {
        "ru": "Модель распознавания", "en": "Recognition model", "de": "Erkennungsmodell",
        "fr": "Modèle de reconnaissance", "es": "Modelo de reconocimiento", "zh": "识别模型",
        "tr": "Tanıma modeli", "hy": "Ճանաչման մոդել",
    },
    "ob.model_text": {
        "ru": "Первая в списке — лучший выбор для вашего языка. Модели Whisper понимают больше языков, но работают заметно медленнее.",
        "en": "The first in the list is the best choice for your language. The Whisper models understand more languages but are markedly slower.",
        "de": "Das erste in der Liste ist die beste Wahl für Ihre Sprache. Die Whisper-Modelle verstehen mehr Sprachen, sind aber deutlich langsamer.",
        "fr": "Le premier de la liste est le meilleur choix pour votre langue. Les modèles Whisper comprennent plus de langues mais sont nettement plus lents.",
        "es": "El primero de la lista es la mejor opción para tu idioma. Los modelos Whisper entienden más idiomas, pero son bastante más lentos.",
        "zh": "列表中的第一个最适合你的语言。Whisper 模型支持的语言更多，但明显更慢。",
        "tr": "Listedeki ilk model diliniz için en iyi seçimdir. Whisper modelleri daha fazla dil anlar ama belirgin şekilde yavaştır.",
        "hy": "Ցանկի առաջինը լավագույն ընտրությունն է ձեր լեզվի համար։ Whisper մոդելներն ավելի շատ լեզու են հասկանում, բայց նկատելիորեն դանդաղ են։",
    },
    "ob.model_gigaam": {
        "ru": "GigaAM v3 · ~216 МБ · лучший для русского",
        "en": "GigaAM v3 · ~216 MB · best for Russian",
        "de": "GigaAM v3 · ~216 MB · am besten für Russisch",
        "fr": "GigaAM v3 · ~216 Mo · le meilleur pour le russe",
        "es": "GigaAM v3 · ~216 MB · el mejor para el ruso",
        "zh": "GigaAM v3 · 约216MB · 俄语最佳",
        "tr": "GigaAM v3 · ~216 MB · Rusça için en iyisi",
        "hy": "GigaAM v3 · ~216 ՄԲ · լավագույնը ռուսերենի համար",
    },
    "ob.model_parakeet": {
        "ru": "Parakeet v3 · ~639 МБ · быстрый, 25 европейских языков",
        "en": "Parakeet v3 · ~639 MB · fast, 25 European languages",
        "de": "Parakeet v3 · ~639 MB · schnell, 25 europäische Sprachen",
        "fr": "Parakeet v3 · ~639 Mo · rapide, 25 langues européennes",
        "es": "Parakeet v3 · ~639 MB · rápido, 25 idiomas europeos",
        "zh": "Parakeet v3 · 约639MB · 快速，25 种欧洲语言",
        "tr": "Parakeet v3 · ~639 MB · hızlı, 25 Avrupa dili",
        "hy": "Parakeet v3 · ~639 ՄԲ · արագ, 25 եվրոպական լեզու",
    },
    "ob.model_tiny": {
        "ru": "tiny · ~75 МБ · быстрее всего", "en": "tiny · ~75 MB · fastest", "de": "tiny · ~75 MB · am schnellsten",
        "fr": "tiny · ~75 Mo · le plus rapide", "es": "tiny · ~75 MB · el más rápido", "zh": "tiny · 约75MB · 最快",
        "tr": "tiny · ~75 MB · en hızlı", "hy": "tiny · ~75 ՄԲ · ամենաարագը",
    },
    "ob.model_base": {
        "ru": "base · ~145 МБ", "en": "base · ~145 MB", "de": "base · ~145 MB", "fr": "base · ~145 Mo",
        "es": "base · ~145 MB", "zh": "base · 约145MB", "tr": "base · ~145 MB", "hy": "base · ~145 ՄԲ",
    },
    "ob.model_small": {
        "ru": "Whisper small · ~485 МБ · 99 языков", "en": "Whisper small · ~485 MB · 99 languages",
        "de": "Whisper small · ~485 MB · 99 Sprachen", "fr": "Whisper small · ~485 Mo · 99 langues",
        "es": "Whisper small · ~485 MB · 99 idiomas", "zh": "Whisper small · 约485MB · 99 种语言",
        "tr": "Whisper small · ~485 MB · 99 dil", "hy": "Whisper small · ~485 ՄԲ · 99 լեզու",
    },
    "ob.model_medium": {
        "ru": "medium · ~1.5 ГБ · точнее", "en": "medium · ~1.5 GB · more accurate", "de": "medium · ~1,5 GB · genauer",
        "fr": "medium · ~1,5 Go · plus précis", "es": "medium · ~1,5 GB · más preciso", "zh": "medium · 约1.5GB · 更精确",
        "tr": "medium · ~1,5 GB · daha isabetli", "hy": "medium · ~1.5 ԳԲ · ավելի ճշգրիտ",
    },
    "ob.btn_load_now": {
        "ru": "Загрузить сейчас", "en": "Load now", "de": "Jetzt laden", "fr": "Charger maintenant",
        "es": "Cargar ahora", "zh": "立即加载", "tr": "Şimdi yükle", "hy": "Բեռնել հիմա",
    },
    "ob.hotkey_title": {
        "ru": "Горячая клавиша", "en": "Hotkey", "de": "Tastenkombination", "fr": "Raccourci clavier",
        "es": "Atajo de teclado", "zh": "快捷键", "tr": "Kısayol tuşu", "hy": "Դյուրանցում",
    },
    "ob.hotkey_text": {
        "ru": "Сейчас: {hotkey}. Удерживайте её во время диктовки.",
        "en": "Currently: {hotkey}. Hold it down while dictating.",
        "de": "Aktuell: {hotkey}. Halte sie beim Diktieren gedrückt.",
        "fr": "Actuellement : {hotkey}. Maintenez-le enfoncé pendant la dictée.",
        "es": "Actualmente: {hotkey}. Mantenlo pulsado mientras dictas.",
        "zh": "当前：{hotkey}。口述时请按住它。",
        "tr": "Şu anda: {hotkey}. Dikte ederken basılı tutun.",
        "hy": "Ներկայումս՝ {hotkey}։ Պահեք այն թելադրելիս։",
    },
    "ob.hotkey_hint": {
        "ru": "По умолчанию Ctrl+Space: две клавиши — удобно зажимать одной рукой.",
        "en": "Default is Ctrl+Space: two keys — easy to hold with one hand.",
        "de": "Standard ist Strg+Leertaste: zwei Tasten — bequem mit einer Hand zu halten.",
        "fr": "Par défaut Ctrl+Espace : deux touches — facile à maintenir d'une seule main.",
        "es": "Por defecto es Ctrl+Espacio: dos teclas — fácil de mantener con una mano.",
        "zh": "默认是 Ctrl+空格：两个按键——单手即可按住。",
        "tr": "Varsayılan Ctrl+Boşluk: iki tuş — tek elle basılı tutmak kolaydır.",
        "hy": "Կանխադրված է Ctrl+Space՝ երկու ստեղն, հեշտ է պահել մեկ ձեռքով։",
    },
    "ob.test_title": {
        "ru": "Проверка диктовки", "en": "Test dictation", "de": "Diktat testen", "fr": "Test de dictée",
        "es": "Probar el dictado", "zh": "测试口述", "tr": "Dikteyi test et", "hy": "Փորձարկել թելադրությունը",
    },
    "ob.test_text": {
        "ru": "Нажмите, скажите пару фраз, остановите. Текст появится ниже —\nникуда не вставляется.",
        "en": "Click, say a couple of phrases, stop. The text will appear below —\nit isn't inserted anywhere.",
        "de": "Klicken, ein paar Sätze sagen, stoppen. Der Text erscheint unten —\ner wird nirgendwo eingefügt.",
        "fr": "Cliquez, dites quelques phrases, arrêtez. Le texte apparaîtra ci-dessous —\nil n'est inséré nulle part.",
        "es": "Haz clic, di un par de frases, detente. El texto aparecerá abajo —\nno se inserta en ningún sitio.",
        "zh": "点击、说几句话、停止。文本会显示在下方——\n不会插入到任何地方。",
        "tr": "Tıklayın, birkaç cümle söyleyin, durdurun. Metin aşağıda görünecek —\nhiçbir yere eklenmez.",
        "hy": "Սեղմեք, ասեք մի քանի արտահայտություն, կանգնեցրեք։ Տեքստը կհայտնվի ներքևում —\nչի տեղադրվում որևէ տեղ։",
    },
    "ob.test_btn_start": {
        "ru": "🎤  Начать запись", "en": "🎤  Start recording", "de": "🎤  Aufnahme starten",
        "fr": "🎤  Démarrer l'enregistrement", "es": "🎤  Empezar a grabar", "zh": "🎤  开始录音",
        "tr": "🎤  Kaydı başlat", "hy": "🎤  Սկսել ձայնագրումը",
    },
    "ob.done_title": {
        "ru": "Всё готово", "en": "All set", "de": "Alles bereit", "fr": "Tout est prêt",
        "es": "Todo listo", "zh": "一切就绪", "tr": "Her şey hazır", "hy": "Ամեն ինչ պատրաստ է",
    },
    "ob.done_text": {
        "ru": "WinDictoo живёт в системном трее (значок микрофона).\n\nПоставьте курсор в поле, зажмите {hotkey}, продиктуйте —\nтекст появится там. Настройки всегда доступны из окна или трея.\n\nУдачной диктовки!",
        "en": "WinDictoo lives in the system tray (the microphone icon).\n\nPlace the cursor in a field, hold {hotkey}, dictate —\nthe text will appear there. Settings are always available from the window or tray.\n\nHappy dictating!",
        "de": "WinDictoo lebt in der Taskleiste (das Mikrofonsymbol).\n\nSetze den Cursor in ein Feld, halte {hotkey} gedrückt, diktiere —\nder Text erscheint dort. Die Einstellungen sind immer über das Fenster oder die Taskleiste erreichbar.\n\nViel Spaß beim Diktieren!",
        "fr": "WinDictoo réside dans la zone de notification (l'icône du micro).\n\nPlacez le curseur dans un champ, maintenez {hotkey}, dictez —\nle texte y apparaîtra. Les paramètres sont toujours accessibles depuis la fenêtre ou la zone de notification.\n\nBonne dictée !",
        "es": "WinDictoo vive en la bandeja del sistema (el icono del micrófono).\n\nColoca el cursor en un campo, mantén pulsado {hotkey}, dicta —\nel texto aparecerá ahí. Los ajustes siempre están disponibles desde la ventana o la bandeja.\n\n¡Feliz dictado!",
        "zh": "WinDictoo 常驻于系统托盘（麦克风图标）。\n\n将光标放在输入框中，按住 {hotkey}，开始口述——\n文本会出现在那里。设置随时可从窗口或托盘中打开。\n\n祝口述愉快！",
        "tr": "WinDictoo sistem tepsisinde yaşar (mikrofon simgesi).\n\nİmleci bir alana yerleştirin, {hotkey} tuşunu basılı tutun, konuşun —\nmetin orada belirecek. Ayarlara her zaman pencereden veya tepsiden ulaşabilirsiniz.\n\nİyi dikteler!",
        "hy": "WinDictoo-ն ապրում է համակարգային վահանակում (խոսափողի պատկերակ)։\n\nԴրեք կուրսորը դաշտում, պահեք {hotkey}, թելադրեք —\nտեքստը կհայտնվի այնտեղ։ Կարգավորումները միշտ հասանելի են պատուհանից կամ վահանակից։\n\nՀաջող թելադրություն!",
    },

    # ------------------------------------------------------------------------ tray
    "tray.open": {
        "ru": "Открыть WinDictoo", "en": "Open WinDictoo", "de": "WinDictoo öffnen", "fr": "Ouvrir WinDictoo",
        "es": "Abrir WinDictoo", "zh": "打开 WinDictoo", "tr": "WinDictoo'yu aç", "hy": "Բացել WinDictoo-ն",
    },
    "tray.status": {
        "ru": "Статус: {label}", "en": "Status: {label}", "de": "Status: {label}", "fr": "Statut : {label}",
        "es": "Estado: {label}", "zh": "状态：{label}", "tr": "Durum: {label}", "hy": "Կարգավիճակ․ {label}",
    },
    "tray.cancel_dictation": {
        "ru": "Отменить диктовку", "en": "Cancel dictation", "de": "Diktat abbrechen", "fr": "Annuler la dictée",
        "es": "Cancelar dictado", "zh": "取消口述", "tr": "Dikteyi iptal et", "hy": "Չեղարկել թելադրությունը",
    },
    "tray.settings": {
        "ru": "Настройки", "en": "Settings", "de": "Einstellungen", "fr": "Paramètres",
        "es": "Ajustes", "zh": "设置", "tr": "Ayarlar", "hy": "Կարգավորումներ",
    },
    "tray.quit": {
        "ru": "Выход", "en": "Quit", "de": "Beenden", "fr": "Quitter", "es": "Salir",
        "zh": "退出", "tr": "Çıkış", "hy": "Ելք",
    },

    # -------------------------------------------------------------- app messages
    "app.mic_unavailable": {
        "ru": "Микрофон недоступен: {error}", "en": "Microphone unavailable: {error}",
        "de": "Mikrofon nicht verfügbar: {error}", "fr": "Microphone indisponible : {error}",
        "es": "Micrófono no disponible: {error}", "zh": "麦克风不可用：{error}",
        "tr": "Mikrofon kullanılamıyor: {error}", "hy": "Խոսափողը հասանելի չէ․ {error}",
    },
    "app.mic_silent": {
        "ru": "Микрофон не улавливает звук — проверьте, что он включён, не заглушен и выбран верный в Настройках → Микрофон",
        "en": "The microphone isn't picking up sound — check that it's turned on, not muted, and the right one is selected in Settings → Microphone",
        "de": "Das Mikrofon nimmt keinen Ton auf — prüfe, ob es eingeschaltet, nicht stummgeschaltet ist und das richtige in Einstellungen → Mikrofon ausgewählt ist",
        "fr": "Le microphone ne capte aucun son — vérifiez qu'il est allumé, non coupé, et que le bon est sélectionné dans Paramètres → Microphone",
        "es": "El micrófono no capta sonido — comprueba que esté encendido, no silenciado y que el correcto esté seleccionado en Ajustes → Micrófono",
        "zh": "麦克风未采集到声音——请检查是否已开启、未静音，并在「设置 → 麦克风」中选择了正确的设备",
        "tr": "Mikrofon ses algılamıyor — açık olduğundan, sessize alınmadığından ve Ayarlar → Mikrofon'da doğru olanın seçildiğinden emin olun",
        "hy": "Խոսափողը ձայն չի ընդունում՝ ստուգեք, որ այն միացված է, չի խլացված, և Կարգավորումներ → Խոսափող բաժնում ընտրված է ճիշտը",
    },
    "app.too_short": {
        "ru": "Запись слишком короткая — удерживайте клавишу дольше",
        "en": "Recording too short — hold the key down longer",
        "de": "Aufnahme zu kurz — halte die Taste länger gedrückt",
        "fr": "Enregistrement trop court — maintenez la touche plus longtemps",
        "es": "Grabación demasiado corta — mantén la tecla pulsada más tiempo",
        "zh": "录音时间太短——请按住按键更长时间",
        "tr": "Kayıt çok kısa — tuşu daha uzun süre basılı tutun",
        "hy": "Ձայնագրությունը շատ կարճ է՝ ստեղնը պահեք ավելի երկար",
    },
    "app.no_speech": {
        "ru": "Речь не распознана", "en": "No speech recognized", "de": "Keine Sprache erkannt",
        "fr": "Aucune parole reconnue", "es": "No se reconoció ninguna voz", "zh": "未识别到语音",
        "tr": "Konuşma algılanmadı", "hy": "Խոսք չի ճանաչվել",
    },
    "app.refine_fallback": {
        "ru": "Улучшение недоступно — вставлен исходный текст",
        "en": "Refinement unavailable — the original text was used",
        "de": "Verbesserung nicht verfügbar — der Originaltext wurde eingefügt",
        "fr": "Amélioration indisponible — le texte original a été inséré",
        "es": "Mejora no disponible — se insertó el texto original",
        "zh": "优化功能不可用——已插入原始文本",
        "tr": "İyileştirme kullanılamıyor — orijinal metin eklendi",
        "hy": "Բարելավումը հասանելի չէ՝ տեղադրվել է սկզբնական տեքստը",
    },
    "app.clipboard_paste_hint": {
        "ru": "Текст в буфере обмена — вставьте через Ctrl+V",
        "en": "Text is in the clipboard — paste it with Ctrl+V",
        "de": "Text ist in der Zwischenablage — mit Strg+V einfügen",
        "fr": "Le texte est dans le presse-papiers — collez-le avec Ctrl+V",
        "es": "El texto está en el portapapeles — pégalo con Ctrl+V",
        "zh": "文本已在剪贴板中——请使用 Ctrl+V 粘贴",
        "tr": "Metin panoda — Ctrl+V ile yapıştırın",
        "hy": "Տեքստը փոխանակման բուֆերում է՝ տեղադրեք Ctrl+V-ով",
    },

    # ------------------------------------------------------- state labels (full)
    "state.idle": {
        "ru": "Готов к диктовке", "en": "Ready to dictate", "de": "Bereit zum Diktieren", "fr": "Prêt à dicter",
        "es": "Listo para dictar", "zh": "准备就绪，可以口述", "tr": "Dikteye hazır", "hy": "Պատրաստ է թելադրության",
    },
    "state.recording": {
        "ru": "Слушаю…", "en": "Listening…", "de": "Höre zu…", "fr": "Écoute…",
        "es": "Escuchando…", "zh": "正在聆听…", "tr": "Dinliyor…", "hy": "Լսում եմ…",
    },
    "state.transcribing": {
        "ru": "Распознаю…", "en": "Transcribing…", "de": "Erkenne…", "fr": "Transcription…",
        "es": "Transcribiendo…", "zh": "正在识别…", "tr": "Yazıya döküyor…", "hy": "Ճանաչում եմ…",
    },
    "state.refining": {
        "ru": "Улучшаю текст…", "en": "Refining text…", "de": "Verbessere Text…", "fr": "Amélioration du texte…",
        "es": "Mejorando el texto…", "zh": "正在优化文本…", "tr": "Metin iyileştiriliyor…", "hy": "Բարելավում եմ տեքստը…",
    },
    "state.inserting": {
        "ru": "Вставляю…", "en": "Inserting…", "de": "Füge ein…", "fr": "Insertion…",
        "es": "Insertando…", "zh": "正在插入…", "tr": "Ekleniyor…", "hy": "Տեղադրում եմ…",
    },
    "state.done": {
        "ru": "Готово", "en": "Done", "de": "Fertig", "fr": "Terminé", "es": "Listo",
        "zh": "完成", "tr": "Tamamlandı", "hy": "Ավարտված",
    },
    "state.cancelled": {
        "ru": "Отменено", "en": "Cancelled", "de": "Abgebrochen", "fr": "Annulé", "es": "Cancelado",
        "zh": "已取消", "tr": "İptal edildi", "hy": "Չեղարկված",
    },
    "state.error": {
        "ru": "Ошибка", "en": "Error", "de": "Fehler", "fr": "Erreur", "es": "Error",
        "zh": "错误", "tr": "Hata", "hy": "Սխալ",
    },

    # ------------------------------------------------------ tray state labels
    "tray.idle": {
        "ru": "Готов", "en": "Ready", "de": "Bereit", "fr": "Prêt", "es": "Listo",
        "zh": "就绪", "tr": "Hazır", "hy": "Պատրաստ",
    },
    "tray.recording": {
        "ru": "Слушаю…", "en": "Listening…", "de": "Höre zu…", "fr": "Écoute…",
        "es": "Escuchando…", "zh": "正在聆听…", "tr": "Dinliyor…", "hy": "Լսում եմ…",
    },
    "tray.transcribing": {
        "ru": "Распознавание…", "en": "Transcribing…", "de": "Erkennung läuft…", "fr": "Transcription…",
        "es": "Transcribiendo…", "zh": "正在识别…", "tr": "Yazıya dökülüyor…", "hy": "Ճանաչում…",
    },
    "tray.refining": {
        "ru": "Улучшение…", "en": "Refining…", "de": "Verbessern…", "fr": "Amélioration…",
        "es": "Mejorando…", "zh": "正在优化…", "tr": "İyileştiriliyor…", "hy": "Բարելավում…",
    },
    "tray.inserting": {
        "ru": "Вставка…", "en": "Inserting…", "de": "Einfügen…", "fr": "Insertion…",
        "es": "Insertando…", "zh": "正在插入…", "tr": "Ekleniyor…", "hy": "Տեղադրում…",
    },
    "tray.done": {
        "ru": "Готово", "en": "Done", "de": "Fertig", "fr": "Terminé", "es": "Listo",
        "zh": "完成", "tr": "Tamamlandı", "hy": "Ավարտված",
    },
    "tray.cancelled": {
        "ru": "Отменено", "en": "Cancelled", "de": "Abgebrochen", "fr": "Annulé", "es": "Cancelado",
        "zh": "已取消", "tr": "İptal edildi", "hy": "Չեղարկված",
    },
    "tray.error": {
        "ru": "Ошибка", "en": "Error", "de": "Fehler", "fr": "Erreur", "es": "Error",
        "zh": "错误", "tr": "Hata", "hy": "Սխալ",
    },
}


def t(key: str, **kwargs) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current) or entry.get("ru") or key
    return text.format(**kwargs) if kwargs else text


def state_label(state) -> str:
    """Full hero/overlay label for a windictoo.app.State value."""
    return t(f"state.{state}")


def tray_label(state) -> str:
    """Short tray tooltip/menu label for a windictoo.app.State value."""
    return t(f"tray.{state}")
