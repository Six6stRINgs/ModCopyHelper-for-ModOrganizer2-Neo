import mobase
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QLineEdit, QAbstractItemView, QMessageBox,
    QHeaderView
)
from PyQt6.QtCore import Qt

from .logger import get_logger 

COLUMN_NAME = 0
COLUMN_PRIORITY = 1

class SimpleCopySettingsDialog(QDialog): 
    def __init__(self, organizer: mobase.IOrganizer, current_selected_mods: list[str], parent=None):
        super().__init__(parent)
        self._organizer = organizer
        self._logger = get_logger()
        self._initial_selected_mods = set(current_selected_mods)
        self._current_selected_mods_on_dialog = set(current_selected_mods)

        self.setWindowTitle(f"{self._logger.name} Settings") 
        self.setMinimumSize(500, 400)

        self._mod_tree_widget = QTreeWidget()
        self._mod_tree_widget.setHeaderLabels(["Mod Name", "Priority"])
        self._mod_tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._mod_tree_widget.setRootIsDecorated(False)
        self._mod_tree_widget.setAlternatingRowColors(True)
        self._mod_tree_widget.setSortingEnabled(True)
        self._mod_tree_widget.header().setSortIndicatorShown(True)
        self._mod_tree_widget.header().setSectionsClickable(True)
        self._mod_tree_widget.header().setStretchLastSection(False)
        self._mod_tree_widget.header().setSectionResizeMode(COLUMN_NAME, QHeaderView.ResizeMode.Stretch)
        self._mod_tree_widget.header().setSectionResizeMode(COLUMN_PRIORITY, QHeaderView.ResizeMode.ResizeToContents)
        
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
        
        self._mod_tree_widget.itemSelectionChanged.connect(self._update_apply_button_state)

    def _populate_mod_list(self):
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

            priority = all_mods_manager.priority(mod_name)

            item = QTreeWidgetItem()
            item.setText(COLUMN_NAME, mod_name)
            item.setText(COLUMN_PRIORITY, str(priority))
            item.setData(COLUMN_NAME, Qt.ItemDataRole.UserRole, mod_name)
            item.setData(COLUMN_PRIORITY, Qt.ItemDataRole.DisplayRole, priority)
            item.setTextAlignment(COLUMN_PRIORITY, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            is_mod_active = False 
            try:
                is_mod_active = mod.active() 
            except AttributeError:
                self._logger.warning(
                    f"Could not determine active state for mod '{mod_name}' via active(). Assuming enabled for UI."
                )
                is_mod_active = True 

            if not is_mod_active:
                item.setForeground(COLUMN_NAME, Qt.GlobalColor.gray)
                item.setForeground(COLUMN_PRIORITY, Qt.GlobalColor.gray)
                item.setToolTip(COLUMN_NAME, f"{mod_name} (Disabled in MO2 or state unknown)")
            else:
                item.setToolTip(COLUMN_NAME, f"{mod_name} (Enabled in MO2)")

            if mod_name in self._current_selected_mods_on_dialog:
                item.setSelected(True)

            self._mod_tree_widget.addTopLevelItem(item)
        
        self._mod_tree_widget.setSortingEnabled(True)
        self._mod_tree_widget.sortByColumn(COLUMN_PRIORITY, Qt.SortOrder.AscendingOrder)

    def _filter_mods(self):
        self._populate_mod_list()

    def _update_apply_button_state(self):
        currently_selected_ui = set()
        for item in self._mod_tree_widget.selectedItems():
            currently_selected_ui.add(item.data(COLUMN_NAME, Qt.ItemDataRole.UserRole))
        
        self._apply_button.setEnabled(currently_selected_ui != self._initial_selected_mods)

    def get_selected_mods(self) -> list[str]:
        selected_mods = []
        for item in self._mod_tree_widget.selectedItems():
            selected_mods.append(item.data(COLUMN_NAME, Qt.ItemDataRole.UserRole))
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
