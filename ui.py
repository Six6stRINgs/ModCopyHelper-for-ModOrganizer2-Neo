import mobase
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt

from .logger import get_logger 

class SimpleCopySettingsDialog(QDialog): 
    def __init__(self, organizer: mobase.IOrganizer, current_selected_mods: list[str], parent=None):
        super().__init__(parent)
        self._organizer = organizer
        self._logger = get_logger()
        self._initial_selected_mods = set(current_selected_mods)
        self._current_selected_mods_on_dialog = set(current_selected_mods)

        self.setWindowTitle(f"{self._logger.name} Settings") 
        self.setMinimumSize(500, 400)

        self._mod_list_widget = QListWidget()
        self._mod_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        
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
        main_layout.addWidget(self._mod_list_widget)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self._ok_button)
        button_layout.addWidget(self._cancel_button)
        button_layout.addWidget(self._apply_button)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        self._mod_list_widget.itemSelectionChanged.connect(self._update_apply_button_state)

    def _populate_mod_list(self):
        self._mod_list_widget.clear()
        all_mods_manager = self._organizer.modList()
        all_mod_names = sorted(all_mods_manager.allMods(), key=str.lower) 
        filter_text = self._filter_input.text().lower()

        for mod_name in all_mod_names:
            if filter_text and filter_text not in mod_name.lower():
                continue
            mod = all_mods_manager.getMod(mod_name)
            if not mod: continue

            item = QListWidgetItem(mod_name)
            item.setData(Qt.ItemDataRole.UserRole, mod_name) 

            if mod_name in self._current_selected_mods_on_dialog:
                 item.setSelected(True)

            is_mod_active = False 
            try:
                is_mod_active = mod.active() 
            except AttributeError:
                self._logger.warning(
                    f"Could not determine active state for mod '{mod_name}' via active(). Assuming enabled for UI."
                )
                is_mod_active = True 

            if not is_mod_active:
                item.setForeground(Qt.GlobalColor.gray) 
                item.setToolTip(f"{mod_name} (Disabled in MO2 or state unknown)")
            else:
                 item.setToolTip(f"{mod_name} (Enabled in MO2)")

            self._mod_list_widget.addItem(item)
        
        
        for i in range(self._mod_list_widget.count()):
            item = self._mod_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) in self._current_selected_mods_on_dialog:
                item.setSelected(True)

    def _filter_mods(self):
        self._populate_mod_list()

    def _update_apply_button_state(self):
        currently_selected_ui = set()
        for item in self._mod_list_widget.selectedItems():
            currently_selected_ui.add(item.data(Qt.ItemDataRole.UserRole))
        
        
        self._apply_button.setEnabled(currently_selected_ui != self._initial_selected_mods)

    def get_selected_mods(self) -> list[str]:
        selected_mods = []
        for item in self._mod_list_widget.selectedItems():
            selected_mods.append(item.data(Qt.ItemDataRole.UserRole))
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