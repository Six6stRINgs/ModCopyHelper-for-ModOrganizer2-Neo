import mobase
from pathlib import Path
import configparser

PLUGIN_NAME = "ModCopyHelper"

TRANSLATIONS = {
    "en": {
        # Column headers
        "column_name": "Mod Name",
        "column_priority": "Priority",
        "column_status": "Status",
        
        # Settings dialog
        "dialog_title": "Settings",
        "select_mods_label": "Select mods to copy to game directory on launch:",
        "auto_disable_warning": "⚠ Selected mods will be automatically disabled in MO2 after Apply.",
        "hint_label": "Right-click menu: Select/Deselect/Select All/Invert | Shift+click: range select",
        "ok_button": "OK",
        "cancel_button": "Cancel",
        "apply_button": "Apply",
        
        # Context menu
        "menu_select": "Select",
        "menu_deselect": "Deselect",
        "menu_select_all": "Select All Visible",
        "menu_deselect_all": "Deselect All",
        "menu_invert": "Invert Selection",
        
        # Status column
        "status_conflict": "⚠ Conflict",
        "status_conflict_tooltip": "Warning: This mod is enabled in MO2 AND selected in plugin!\nPlease deselect or disable in MO2.\nIt will be auto-disabled in MO2 on Apply.",
        "status_selected": "✔",
        "status_selected_tooltip": "This mod is selected, will be copied to game directory on launch",
        
        # Mod tooltips
        "mod_enabled": "(Enabled in MO2)",
        "mod_disabled": "(Disabled in MO2)",
        "mod_separator": "(Separator)",
        "mod_conflict": "⚠ This mod is enabled in MO2 AND selected in plugin!\nIt will be disabled in MO2 on Apply.",
        
        # Filter
        "filter_placeholder": "Filter mods by name...",
        
        # Plugin settings
        "setting_enabled": "Enable {name}",
        "setting_log_level": "Logging Level (DEBUG, INFO, WARNING, ERROR)",
        "setting_auto_disable": "Auto-disable selected mods in MO2",
        "setting_language": "Language (auto, en, zh_CN)",
        
        # Profile not loaded
        "profile_not_loaded_title": "Profile Not Loaded",
        "profile_not_loaded_msg": "A ModOrganizer profile must be loaded to configure {name}.",
    },
    "zh_CN": {
        # Column headers
        "column_name": "模组名",
        "column_priority": "优先级",
        "column_status": "状态",
        
        # Settings dialog
        "dialog_title": "设置",
        "select_mods_label": "选择要在启动时复制到游戏目录的模组：",
        "auto_disable_warning": "⚠ 选中的模组将在Apply后自动在MO2中禁用。",
        "hint_label": "右键菜单：选择/取消/全选/反选 | Shift+点击：连续选择",
        "ok_button": "确定",
        "cancel_button": "取消",
        "apply_button": "应用",
        
        # Context menu
        "menu_select": "选择",
        "menu_deselect": "取消选择",
        "menu_select_all": "全选可见",
        "menu_deselect_all": "取消全选",
        "menu_invert": "反选",
        
        # Status column
        "status_conflict": "⚠ 冲突",
        "status_conflict_tooltip": "警告：此模组同时在MO2中启用！\n请取消勾选或在MO2中禁用此模组。\nApply后将自动在MO2中禁用。",
        "status_selected": "✔",
        "status_selected_tooltip": "此模组已选中，将在启动时复制到游戏目录",
        
        # Mod tooltips
        "mod_enabled": "(MO2中已启用)",
        "mod_disabled": "(MO2中已禁用)",
        "mod_separator": "(分隔符)",
        "mod_conflict": "⚠ 此模组同时在MO2中启用！\n请取消勾选或在MO2中禁用此模组。\nApply后将自动在MO2中禁用。",
        
        # Filter
        "filter_placeholder": "按名称筛选模组...",
        
        # Plugin settings
        "setting_enabled": "启用 {name}",
        "setting_log_level": "日志级别 (DEBUG, INFO, WARNING, ERROR)",
        "setting_auto_disable": "自动在MO2中禁用选中的模组",
        "setting_language": "语言 (auto, en, zh_CN)",
        
        # Profile not loaded
        "profile_not_loaded_title": "未加载配置文件",
        "profile_not_loaded_msg": "需要加载ModOrganizer配置文件才能配置{name}。",
    }
}

_current_lang = "en"
_translator = None

def _find_mo2_config() -> Path | None:
    plugin_dir = Path(__file__).resolve().parent
    mo2_dir = plugin_dir.parent.parent
    config_path = mo2_dir / "ModOrganizer.ini"
    if config_path.exists():
        return config_path
    return None

def get_system_language() -> str:
    try:
        config_path = _find_mo2_config()
        if config_path:
            config = configparser.ConfigParser()
            config.read(config_path, encoding='utf-8')
            lang = config.get('Settings', 'language', fallback='en')
            if lang in TRANSLATIONS:
                return lang
            base_lang = lang.split('_')[0]
            for key in TRANSLATIONS:
                if key.startswith(base_lang):
                    return key
    except Exception:
        pass
    return "en"

def init_translations(organizer: mobase.IOrganizer = None):
    global _current_lang
    
    lang_override = None
    if organizer:
        lang_override = organizer.pluginSetting(PLUGIN_NAME, "language")
    
    if lang_override and lang_override != "auto" and lang_override in TRANSLATIONS:
        _current_lang = lang_override
    else:
        _current_lang = get_system_language()

def tr(key: str, **kwargs) -> str:
    text = TRANSLATIONS.get(_current_lang, TRANSLATIONS["en"]).get(key)
    if text is None:
        text = TRANSLATIONS["en"].get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

def get_current_language() -> str:
    return _current_lang
