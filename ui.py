import mobase
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QAbstractItemView, QMessageBox,
    QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from .logger import get_logger 

COLUMN_NAME = 0
COLUMN_PRIORITY = 1

IS_SEPARATOR_ROLE = Qt.ItemDataRole.UserRole + 1
MOD_NAME_ROLE = Qt.ItemDataRole.UserRole + 2
PRIORITY_SORT_ROLE = Qt.ItemDataRole.UserRole + 3

SEPARATOR_COLOR = QColor(100, 149, 237)

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

        self.setWindowTitle(f"{self._logger.name} Settings") 
        self.setMinimumSize(500, 400)

        self._mod_tree_widget = QTreeWidget()
        self._mod_tree_widget.setHeaderLabels(["", "Mod Name", "Priority"])
        self._mod_tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._mod_tree_widget.setRootIsDecorated(False)
        self._mod_tree_widget.setAlternatingRowColors(True)
        self._mod_tree_widget.setSortingEnabled(True)
        self._mod_tree_widget.header().setSortIndicatorShown(True)
        self._mod_tree_widget.header().setSectionsClickable(True)
        self._mod_tree_widget.header().setStretchLastSection(False)
        self._mod_tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._mod_tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._mod_tree_widget.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._mod_tree_widget.header().resizeSection(0, 30)
        self._mod_tree_widget.itemChanged.connect(self._on_item_changed)
        
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

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Select mods to copy to game directory on launch:"))
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
            item.setText(1, mod_name)
            item.setText(2, str(priority))
            item.setData(1, MOD_NAME_ROLE, mod_name)
            item.setData(2, PRIORITY_SORT_ROLE, priority)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if is_separator:
                item.setData(0, IS_SEPARATOR_ROLE, True)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(1, SEPARATOR_COLOR)
                item.setForeground(2, SEPARATOR_COLOR)
                font = item.font(1)
                font.setBold(True)
                item.setFont(1, font)
                item.setFont(2, font)
                item.setTextAlignment(1, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip(1, f"{mod_name} (Separator)")
            else:
                item.setData(0, IS_SEPARATOR_ROLE, False)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                is_mod_active = bool(all_mods_manager.state(mod_name) & mobase.ModState.ACTIVE)
                if not is_mod_active:
                    item.setForeground(1, Qt.GlobalColor.gray)
                    item.setForeground(2, Qt.GlobalColor.gray)
                    item.setToolTip(1, f"{mod_name} (Disabled in MO2)")
                else:
                    item.setToolTip(1, f"{mod_name} (Enabled in MO2)")
                
                if mod_name in self._current_selected_mods_on_dialog:
                    item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)

            self._mod_tree_widget.addTopLevelItem(item)
        
        self._mod_tree_widget.setSortingEnabled(True)
        self._mod_tree_widget.sortByColumn(2, Qt.SortOrder.AscendingOrder)
        self._updating_checks = False

    def _on_item_changed(self, item, column):
        if self._updating_checks:
            return
        if column == 0:
            self._update_apply_button_state()

    def _filter_mods(self):
        self._populate_mod_list()

    def _update_apply_button_state(self):
        currently_selected_ui = set()
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                mod_name = item.data(1, MOD_NAME_ROLE)
                if mod_name:
                    currently_selected_ui.add(mod_name)
        
        self._apply_button.setEnabled(currently_selected_ui != self._initial_selected_mods)

    def get_selected_mods(self) -> list[str]:
        selected_mods = []
        for i in range(self._mod_tree_widget.topLevelItemCount()):
            item = self._mod_tree_widget.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                mod_name = item.data(1, MOD_NAME_ROLE)
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
