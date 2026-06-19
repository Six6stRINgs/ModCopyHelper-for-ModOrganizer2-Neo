import mobase
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QAbstractItemView, QMessageBox,
    QHeaderView, QMenu
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QAction

from .logger import get_logger 

COLUMN_CHECK = 0
COLUMN_NAME = 1
COLUMN_PRIORITY = 2
COLUMN_STATUS = 3

IS_SEPARATOR_ROLE = Qt.ItemDataRole.UserRole + 1
MOD_NAME_ROLE = Qt.ItemDataRole.UserRole + 2
PRIORITY_SORT_ROLE = Qt.ItemDataRole.UserRole + 3
CONFLICT_ROLE = Qt.ItemDataRole.UserRole + 4

CONFLICT_COLOR = QColor(220, 50, 50)
SELECTED_BG_COLOR = QColor(60, 120, 200, 60)
TRANSPARENT_COLOR = QColor(0, 0, 0, 0)

DEFAULT_SEPARATOR_COLOR = QColor(100, 149, 237)

def _parse_variant_color(color_str: str) -> QColor | None:
    if color_str.startswith('"') and color_str.endswith('"'):
        color_str = color_str[1:-1]
    
    if not color_str.startswith("@Variant("):
        return None
    
    raw = color_str[9:]
    if raw.endswith(")"):
        raw = raw[:-1]
    
    result = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == '\\' and i + 1 < len(raw):
            next_char = raw[i + 1]
            if next_char == '0':
                result.append(0)
                i += 2
            elif next_char == 'x':
                hex_digits = ""
                j = i + 2
                while j < len(raw) and j < i + 4 and raw[j] in '0123456789abcdefABCDEF':
                    hex_digits += raw[j]
                    j += 1
                if hex_digits:
                    result.append(int(hex_digits, 16))
                    i = j
                else:
                    result.append(ord('x'))
                    i += 2
            else:
                result.append(ord(next_char))
                i += 2
        else:
            result.append(ord(raw[i]))
            i += 1
    
    raw_bytes = bytes(result)
    
    if len(raw_bytes) < 13:
        return None
    
    if raw_bytes[0:4] != b'\x00\x00\x00\x43':
        return None
    
    r = raw_bytes[7]
    g = raw_bytes[9]
    b = raw_bytes[11]
    
    return QColor(r, g, b)

def _get_separator_color(mod_path: str) -> QColor:
    meta_path = Path(mod_path) / "meta.ini"
    if not meta_path.exists():
        return DEFAULT_SEPARATOR_COLOR
    
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('color='):
                    color_str = line[6:]
                    color = _parse_variant_color(color_str)
                    if color and color.isValid():
                        return color
    except Exception:
        pass
    
    return DEFAULT_SEPARATOR_COLOR

class ModTreeWidgetItem(QTreeWidgetItem):
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == COLUMN_PRIORITY:
            return self.data(COLUMN_PRIORITY, PRIORITY_SORT_ROLE) < other.data(COLUMN_PRIORITY, PRIORITY_SORT_ROLE)
        return super().__lt__(other)

class SimpleCopySettingsDialog(QDialog): 
    def __init__(self, organizer: mobase.IOrganizer, current_selected_mods: list[str], parent=None):
        super().__init__(parent)
        self._organizer = organizer
        self._logger = get_logger()
        self._initial_selected_mods = set(current_selected_mods)
        self._current_selected_mods_on_dialog = set(current_selected_mods)
        self._updating_checks = False
        self._last_clicked_item = None

        self.setWindowTitle(f"{self._logger.name} Settings") 
        self.setMinimumSize(600, 500)

        self._mod_tree_widget = QTreeWidget()
        self._mod_tree_widget.setHeaderLabels(["", "Mod Name", "Priority", "Status"])
        self._mod_tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._mod_tree_widget.setRootIsDecorated(False)
        self._mod_tree_widget.setAlternatingRowColors(True)
        self._mod_tree_widget.setSortingEnabled(True)
        self._mod_tree_widget.header().setSortIndicatorShown(True)
        self._mod_tree_widget.header().setSectionsClickable(True)
        self._mod_tree_widget.header().setStretchLastSection(False)
        self._mod_tree_widget.header().setSectionResizeMode(COLUMN_CHECK, QHeaderView.ResizeMode.Fixed)
        self._mod_tree_widget.header().setSectionResizeMode(COLUMN_NAME, QHeaderView.ResizeMode.Stretch)
        self._mod_tree_widget.header().setSectionResizeMode(COLUMN_PRIORITY, QHeaderView.ResizeMode.ResizeToContents)
        self._mod_tree_widget.header().setSectionResizeMode(COLUMN_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        self._mod_tree_widget.header().resizeSection(COLUMN_CHECK, 30)
        self._mod_tree_widget.itemChanged.connect(self._on_item_changed)
        self._mod_tree_widget.viewport().installEventFilter(self)
        self._mod_tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._mod_tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter mods by name...")
        self._filter_input.textChanged.connect(self._filter_mods)

        self._populate_mod_list()

        self._ok_button = QPushButton("OK")
        self._ok_button.clicked.connect(self.accept)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        self._apply_button = QPushButton("Apply")
        self._apply_button.clicked.connect(self._apply_changes)
        self._apply_button.setEnabled(False) 

        auto_disable = self._organizer.pluginSetting("ModCopyHelper", "autoDisable")
        
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Select mods to copy to game directory on launch:"))
        
        if auto_disable:
            warning_label = QLabel("⚠ Selected mods will be automatically disabled in MO2 after Apply.")
            warning_label.setStyleSheet("color: orange; font-weight: bold;")
            main_layout.addWidget(warning_label)
        
        hint_label = QLabel("右键菜单：选择/取消/全选/反选 | Shift+点击：连续选择")
        hint_label.setStyleSheet("color: gray; font-size: 11px;")
        main_layout.addWidget(hint_label)
        
        main_layout.addWidget(self._filter_input)
        main_layout.addWidget(self._mod_tree_widget)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self._ok_button)
        button_layout.addWidget(self._cancel_button)
        button_layout.addWidget(self._apply_button)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)

    def _populate_mod_list(self):
        self._updating_checks = True
        self._mod_tree_widget.setSortingEnabled(False)
        self._mod_tree_widget.clear()
        all_mods_manager = self._organizer.modList()
        all_mod_names = sorted(all_mods_manager.allMods(), key=str.lower) 
        filter_text = self._filter_input.text().lower()

        for mod_name in all_mod_names:
            if filter_text and filter_text not in mod_name.lower():
                continue
            mod = all_mods_manager.getMod(mod_name)
            if not mod: continue

            is_separator = mod.isSeparator()
            priority = all_mods_manager.priority(mod_name)

            item = ModTreeWidgetItem()
            item.setText(COLUMN_NAME, mod_name)
            item.setText(COLUMN_PRIORITY, str(priority))
            item.setData(COLUMN_NAME, MOD_NAME_ROLE, mod_name)
            item.setData(COLUMN_PRIORITY, PRIORITY_SORT_ROLE, priority)
            item.setTextAlignment(COLUMN_PRIORITY, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if is_separator:
                item.setData(COLUMN_CHECK, IS_SEPARATOR_ROLE, True)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsSelectable)
                
                separator_color = _get_separator_color(mod.absolutePath())
                item.setForeground(COLUMN_NAME, separator_color)
                item.setForeground(COLUMN_PRIORITY, separator_color)
                font = item.font(COLUMN_NAME)
                font.setBold(True)
                item.setFont(COLUMN_NAME, font)
                item.setFont(COLUMN_PRIORITY, font)
                item.setTextAlignment(COLUMN_NAME, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip(COLUMN_NAME, f"{mod_name} (Separator)")
            else:
                item.setData(COLUMN_CHECK, IS_SEPARATOR_ROLE, False)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                is_mod_active = bool(all_mods_manager.state(mod_name) & mobase.ModState.ACTIVE)
                
                is_selected = mod_name in self._current_selected_mods_on_dialog
                has_conflict = is_selected and is_mod_active
                
                if has_conflict:
                    item.setData(COLUMN_CHECK, CONFLICT_ROLE, True)
                    item.setText(COLUMN_STATUS, "⚠ Conflict")
                    item.setForeground(COLUMN_STATUS, CONFLICT_COLOR)
                    item.setFont(COLUMN_STATUS, self._bold_font())
                    item.setForeground(COLUMN_NAME, CONFLICT_COLOR)
                    item.setToolTip(COLUMN_NAME, f"{mod_name}\n⚠ This mod is enabled in MO2 AND selected in plugin!\nIt will be disabled in MO2 on Apply.")
                    item.setToolTip(COLUMN_STATUS, "警告：此模组同时在MO2中启用！\n请取消勾选或在MO2中禁用此模组。\nApply后将自动在MO2中禁用。")
                    if is_selected:
                        item.setCheckState(COLUMN_CHECK, Qt.CheckState.Checked)
                    else:
                        item.setCheckState(COLUMN_CHECK, Qt.CheckState.Unchecked)
                else:
                    item.setData(COLUMN_CHECK, CONFLICT_ROLE, False)
                    if is_selected:
                        item.setText(COLUMN_STATUS, "✔")
                        item.setForeground(COLUMN_STATUS, QColor(50, 180, 50))
                        item.setToolTip(COLUMN_STATUS, "此模组已选中，将在启动时复制到游戏目录")
                    else:
                        item.setText(COLUMN_STATUS, "")
                        item.setToolTip(COLUMN_STATUS, "")
                    
                    if not is_mod_active:
                        item.setForeground(COLUMN_NAME, Qt.GlobalColor.gray)
                        item.setForeground(COLUMN_PRIORITY, Qt.GlobalColor.gray)
                        item.setToolTip(COLUMN_NAME, f"{mod_name} (Disabled in MO2)")
                    else:
                        item.setToolTip(COLUMN_NAME, f"{mod_name} (Enabled in MO2)")
                    
                    if is_selected:
                        item.setCheckState(COLUMN_CHECK, Qt.CheckState.Checked)
                    else:
                        item.setCheckState(COLUMN_CHECK, Qt.CheckState.Unchecked)

            self._mod_tree_widget.addTopLevelItem(item)
        
        self._mod_tree_widget.setSortingEnabled(True)
        self._mod_tree_widget.sortByColumn(COLUMN_PRIORITY, Qt.SortOrder.AscendingOrder)
        self._updating_checks = False

    def _bold_font(self):
        font = self.font()
        font.setBold(True)
        return font

    def _on_item_changed(self, item, column):
        if self._updating_checks:
            return
        if column == COLUMN_CHECK:
            self._update_item_conflict_status(item)
            self._update_apply_button_state()

    def _update_item_conflict_status(self, item):
        if item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
            return
        
        mod_name = item.data(COLUMN_NAME, MOD_NAME_ROLE)
        if not mod_name:
            return
        
        is_selected = item.checkState(COLUMN_CHECK) == Qt.CheckState.Checked
        modlist = self._organizer.modList()
        is_mod_active = bool(modlist.state(mod_name) & mobase.ModState.ACTIVE)
        has_conflict = is_selected and is_mod_active
        
        if has_conflict:
            item.setData(COLUMN_CHECK, CONFLICT_ROLE, True)
            item.setText(COLUMN_STATUS, "⚠ Conflict")
            item.setForeground(COLUMN_STATUS, CONFLICT_COLOR)
            item.setFont(COLUMN_STATUS, self._bold_font())
            item.setForeground(COLUMN_NAME, CONFLICT_COLOR)
            item.setBackground(COLUMN_CHECK, SELECTED_BG_COLOR)
            item.setBackground(COLUMN_NAME, SELECTED_BG_COLOR)
            item.setBackground(COLUMN_PRIORITY, SELECTED_BG_COLOR)
            item.setBackground(COLUMN_STATUS, SELECTED_BG_COLOR)
            item.setToolTip(COLUMN_NAME, f"{mod_name}\n⚠ This mod is enabled in MO2 AND selected in plugin!\nIt will be disabled in MO2 on Apply.")
            item.setToolTip(COLUMN_STATUS, "警告：此模组同时在MO2中启用！\n请取消勾选或在MO2中禁用此模组。\nApply后将自动在MO2中禁用。")
        else:
            item.setData(COLUMN_CHECK, CONFLICT_ROLE, False)
            item.setFont(COLUMN_STATUS, self.font())
            
            if is_selected:
                item.setText(COLUMN_STATUS, "✔")
                item.setForeground(COLUMN_STATUS, QColor(50, 180, 50))
                item.setToolTip(COLUMN_STATUS, "此模组已选中，将在启动时复制到游戏目录")
                item.setBackground(COLUMN_CHECK, SELECTED_BG_COLOR)
                item.setBackground(COLUMN_NAME, SELECTED_BG_COLOR)
                item.setBackground(COLUMN_PRIORITY, SELECTED_BG_COLOR)
                item.setBackground(COLUMN_STATUS, SELECTED_BG_COLOR)
            else:
                item.setText(COLUMN_STATUS, "")
                item.setForeground(COLUMN_STATUS, TRANSPARENT_COLOR)
                item.setToolTip(COLUMN_STATUS, "")
                item.setBackground(COLUMN_CHECK, TRANSPARENT_COLOR)
                item.setBackground(COLUMN_NAME, TRANSPARENT_COLOR)
                item.setBackground(COLUMN_PRIORITY, TRANSPARENT_COLOR)
                item.setBackground(COLUMN_STATUS, TRANSPARENT_COLOR)
            
            if is_mod_active:
                item.setForeground(COLUMN_NAME, QColor(Qt.GlobalColor.black))
                item.setForeground(COLUMN_PRIORITY, QColor(Qt.GlobalColor.black))
                item.setToolTip(COLUMN_NAME, f"{mod_name} (Enabled in MO2)")
            else:
                item.setForeground(COLUMN_NAME, Qt.GlobalColor.gray)
                item.setForeground(COLUMN_PRIORITY, Qt.GlobalColor.gray)
                item.setToolTip(COLUMN_NAME, f"{mod_name} (Disabled in MO2)")

    def _filter_mods(self):
        self._populate_mod_list()

    def eventFilter(self, obj, event):
        if obj == self._mod_tree_widget.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent):
                if event.button() == Qt.MouseButton.RightButton:
                    return False
                
                item = self._mod_tree_widget.itemAt(event.pos())
                if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                    column = self._mod_tree_widget.columnAt(event.pos().x())
                    if column == COLUMN_NAME or column == COLUMN_CHECK:
                        modifiers = event.modifiers()
                        if modifiers & Qt.KeyboardModifier.ShiftModifier and self._last_clicked_item:
                            self._shift_select_range(item)
                        else:
                            current_state = item.checkState(COLUMN_CHECK)
                            new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
                            item.setCheckState(COLUMN_CHECK, new_state)
                            self._update_item_conflict_status(item)
                        self._last_clicked_item = item
                        return True
        return super().eventFilter(obj, event)

    def _show_context_menu(self, position):
        menu = QMenu(self)
        
        item = self._mod_tree_widget.itemAt(position)
        
        if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
            if item.checkState(COLUMN_CHECK) == Qt.CheckState.Checked:
                deselect_action = QAction("取消选择", self)
                deselect_action.triggered.connect(lambda: self._toggle_item(item, False))
                menu.addAction(deselect_action)
            else:
                select_action = QAction("选择", self)
                select_action.triggered.connect(lambda: self._toggle_item(item, True))
                menu.addAction(select_action)
            menu.addSeparator()
        
        select_all_action = QAction("全选可见", self)
        select_all_action.triggered.connect(self._select_all_visible)
        menu.addAction(select_all_action)
        
        deselect_all_action = QAction("取消全选", self)
        deselect_all_action.triggered.connect(self._deselect_all_visible)
        menu.addAction(deselect_all_action)
        
        invert_action = QAction("反选", self)
        invert_action.triggered.connect(self._invert_selection)
        menu.addAction(invert_action)
        
        menu.exec(self._mod_tree_widget.viewport().mapToGlobal(position))

    def _toggle_item(self, item, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        item.setCheckState(COLUMN_CHECK, state)
        self._update_item_conflict_status(item)
        self._update_apply_button_state()

    def _shift_select_range(self, end_item):
        if not self._last_clicked_item:
            return
        
        start_index = self._mod_tree_widget.indexOfTopLevelItem(self._last_clicked_item)
        end_index = self._mod_tree_widget.indexOfTopLevelItem(end_item)
        
        if start_index > end_index:
            start_index, end_index = end_index, start_index
        
        target_state = end_item.checkState(COLUMN_CHECK)
        new_state = Qt.CheckState.Unchecked if target_state == Qt.CheckState.Checked else Qt.CheckState.Checked
        
        for i in range(start_index, end_index + 1):
            item = self._mod_tree_widget.topLevelItem(i)
            if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                item.setCheckState(COLUMN_CHECK, new_state)
                self._update_item_conflict_status(item)
        self._update_apply_button_state()

    def _select_all_visible(self):
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                item.setCheckState(COLUMN_CHECK, Qt.CheckState.Checked)
                self._update_item_conflict_status(item)
        self._update_apply_button_state()

    def _deselect_all_visible(self):
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                item.setCheckState(COLUMN_CHECK, Qt.CheckState.Unchecked)
                self._update_item_conflict_status(item)
        self._update_apply_button_state()

    def _invert_selection(self):
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                current = item.checkState(COLUMN_CHECK)
                new_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
                item.setCheckState(COLUMN_CHECK, new_state)
                self._update_item_conflict_status(item)
        self._update_apply_button_state()
                item.setBackground(COLUMN_STATUS, SELECTED_BG_COLOR)
                self._update_item_conflict_status(item)
        self._preview_items.clear()
        self._update_apply_button_state()

    def _select_all_visible(self):
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                item.setCheckState(COLUMN_CHECK, Qt.CheckState.Checked)
                self._update_item_conflict_status(item)
        self._update_apply_button_state()

    def _deselect_all_visible(self):
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                item.setCheckState(COLUMN_CHECK, Qt.CheckState.Unchecked)
                self._update_item_conflict_status(item)
        self._update_apply_button_state()

    def _invert_selection(self):
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item and not item.data(COLUMN_CHECK, IS_SEPARATOR_ROLE):
                current = item.checkState(COLUMN_CHECK)
                new_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
                item.setCheckState(COLUMN_CHECK, new_state)
                self._update_item_conflict_status(item)
        self._update_apply_button_state()

    def _update_apply_button_state(self):
        currently_selected_ui = set()
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item.checkState(COLUMN_CHECK) == Qt.CheckState.Checked:
                mod_name = item.data(COLUMN_NAME, MOD_NAME_ROLE)
                if mod_name:
                    currently_selected_ui.add(mod_name)
        
        self._apply_button.setEnabled(currently_selected_ui != self._initial_selected_mods)

    def get_selected_mods(self) -> list[str]:
        selected_mods = []
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item.checkState(COLUMN_CHECK) == Qt.CheckState.Checked:
                mod_name = item.data(COLUMN_NAME, MOD_NAME_ROLE)
                if mod_name:
                    selected_mods.append(mod_name)
        return sorted(list(set(selected_mods)), key=str.lower) 

    def _apply_changes(self):
        self._current_selected_mods_on_dialog = set(self.get_selected_mods())
        self._initial_selected_mods = self._current_selected_mods_on_dialog 
        self._apply_button.setEnabled(False) 
        self._logger.info(f"UI Apply: Selection changed to {self._current_selected_mods_on_dialog}")

    def accept(self):
        self._apply_changes() 
        super().accept() 

    @staticmethod
    def ask_yes_no(parent, title: str, message: str) -> bool:
        reply = QMessageBox.question(parent, title, message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No) 
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def show_error(parent, title: str, message: str):
        QMessageBox.critical(parent, title, message, QMessageBox.StandardButton.Ok)
