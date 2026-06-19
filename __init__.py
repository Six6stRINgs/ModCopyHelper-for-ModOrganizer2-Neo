import mobase
from PyQt6.QtWidgets import QMessageBox
from PyQt6 import QtGui 
from pathlib import Path

from .logger import setup_logger, get_logger, PLUGIN_NAME as PLUGIN_NAME_CONST
from .logic import SimpleCopyLogic
from .ui import SimpleCopySettingsDialog

class ModCopyHelperPlugin(mobase.IPluginTool, mobase.IPluginFileMapper): 
    def __init__(self):
        mobase.IPluginTool.__init__(self)
        mobase.IPluginFileMapper.__init__(self)

        self._organizer: mobase.IOrganizer = None
        self._logic: SimpleCopyLogic = None
        self._settings_dialog: SimpleCopySettingsDialog = None 
        self._logger = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        
        if not self._organizer.pluginSetting(PLUGIN_NAME_CONST, "logLevel"):
            self._organizer.setPluginSetting(PLUGIN_NAME_CONST, "logLevel", "INFO") 
        
        global LOGGER 
        LOGGER = setup_logger(self._organizer)
        self._logger = get_logger()

        self._logic = SimpleCopyLogic(self._organizer)

        if self._organizer.profilePath():
            self._logic._ensure_paths_initialized()
            self._logic.load_settings()
            self._logic.check_and_handle_previous_crash()
            self._logic.sync_mod_tags()
        else:
            self._logger.info("Profile not yet available during init. Path/settings load deferred.")

        self._organizer.onAboutToRun(
            lambda executable_path, is_app_launch, user_data: self._on_about_to_run(executable_path, is_app_launch, user_data)
        )
        self._organizer.onFinishedRun(
            lambda executable_path, exit_code: self._on_finished_run(executable_path, exit_code)
        )
        self._organizer.onProfileChanged(
            lambda old_profile, new_profile: self._on_profile_changed(old_profile, new_profile)
        )
        self._logger.info(f"{self.name()} initialized.")
        return True

    def name(self) -> str:
        return PLUGIN_NAME_CONST 

    def author(self) -> str:
        return "41Channel" 

    def description(self) -> str:
        return "Copies selected mod files to the game directory on launch and removes them on exit. Redirects output."

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0) 
        
    def isActive(self) -> bool:
        return True 

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", f"Enable {self.name()}", True), 
            mobase.PluginSetting("logLevel", "Logging Level (DEBUG, INFO, WARNING, ERROR)", "INFO"),
            mobase.PluginSetting("autoDisable", "Auto-disable selected mods in MO2", True)
        ]

    def displayName(self) -> str:
        return f"{self.name()} Settings" 

    def tooltip(self) -> str:
        return f"Configure which mods are copied by {self.name()}" 

    def icon(self) -> QtGui.QIcon:
        return QtGui.QIcon() 

    def display(self):
        if not self._organizer.profilePath():
            QMessageBox.warning(None, "Profile Not Loaded", 
                                f"A ModOrganizer profile must be loaded to configure {self.name()}.")
            return

        self._logic.load_settings() 
        current_selection = self._logic.get_selected_mods()
        
        self._settings_dialog = SimpleCopySettingsDialog(self._organizer, current_selection)
        
        if self._settings_dialog.exec(): 
            newly_selected_mods = self._settings_dialog.get_selected_mods()
            self._logic.set_selected_mods(newly_selected_mods)
            self._logic.sync_mod_tags()
            
            auto_disable = self._organizer.pluginSetting(PLUGIN_NAME_CONST, "autoDisable")
            if auto_disable:
                self._logic.disable_selected_mods_in_mo2()
            
            self._logger.info(f"Settings applied via dialog. New selection: {newly_selected_mods}")
        else:
            self._logger.info("Settings dialog cancelled.")

    def mappings(self) -> list[mobase.Mapping]:
        return [] 

    def mapFile(self, file_path: str, case_sensitive: bool) -> str:
        if not self._logic or not self._logic._is_game_running:
            return file_path
        return self._logic.map_file_for_overwrite(file_path)

    def _is_executable_managed(self, executable_path_input: str) -> bool:
        if not self._organizer or not self._organizer.managedGame():
            self._logger.debug("_is_executable_managed: No managed game.")
            return False
        
        managed_game_instance = self._organizer.managedGame()
        primary_game_exe_name = ""
        
        if hasattr(managed_game_instance, 'binaryName'):
            try:
                binary_name_val = managed_game_instance.binaryName()
                if binary_name_val:
                    primary_game_exe_name = binary_name_val.lower()
                    self._logger.debug(
                        f"_is_executable_managed: Primary game exe name from binaryName(): '{primary_game_exe_name}'"
                    )
                else:
                    self._logger.warning("_is_executable_managed: binaryName() returned empty string.")
            except Exception as e:
                self._logger.error(f"_is_executable_managed: Error calling binaryName(): {e}", exc_info=True)
        else:
            self._logger.warning("_is_executable_managed: managedGame instance lacks 'binaryName' attribute.")

        if not primary_game_exe_name:
            self._logger.error("_is_executable_managed: Failed to determine primary game executable name.")
            return False
            
        launched_exe_name = Path(executable_path_input).name.lower()
        self._logger.debug(f"_is_executable_managed: Comparing launched '{launched_exe_name}' with primary '{primary_game_exe_name}'")

        if launched_exe_name == primary_game_exe_name:
            self._logger.info(f"Main game executable '{launched_exe_name}' is being launched. {self.name()} will activate.")
            return True
            
        self._logger.debug(
            f"Executable '{launched_exe_name}' is not the primary game executable. {self.name()} will not activate."
        )
        return False

    def _on_about_to_run(self, executable_path: str, is_app_launch: bool, user_data) -> bool: 
        self._logger.debug(f"onAboutToRun: Entered for '{executable_path}', isApp: {is_app_launch}")
        
        actual_executable_path_str = executable_path
        if hasattr(executable_path, 'path') and callable(executable_path.path): 
            actual_executable_path_str = executable_path.path()
        elif hasattr(executable_path, 'filePath') and callable(executable_path.filePath): 
            actual_executable_path_str = executable_path.filePath()
        actual_executable_path_str = str(actual_executable_path_str) 

        self._logger.debug(f"onAboutToRun: Processed executable path is '{actual_executable_path_str}'")

        if not self._is_executable_managed(actual_executable_path_str):
            self._logger.debug(f"onAboutToRun: Executable '{actual_executable_path_str}' not managed. Skipping operations.")
            return True 

        self._logger.info(f"onAboutToRun: Executable '{actual_executable_path_str}' IS managed. Proceeding with operations.")
        self._logic.set_game_running_status(False) 

        self._logger.debug("onAboutToRun: Calling self._logic.copy_files_to_game_directory (unconditional overwrite).")
        copy_success = False
        try:
            copy_success = self._logic.copy_files_to_game_directory() 
            self._logger.info(f"onAboutToRun: copy_files_to_game_directory returned: {copy_success}")
        except Exception as e_copy_call:
            self._logger.error(
                f"onAboutToRun: Exception during call to copy_files_to_game_directory: {e_copy_call}", exc_info=True
            )
            copy_success = False 
        
        if copy_success:
            self._logger.info("onAboutToRun: Files copied (or no copy needed). Proceeding with game launch. Returning True.")
            self._logic.set_game_running_status(True)
            return True
        else:
            self._logger.error("onAboutToRun: File copy operation failed. Aborting game launch. Returning False.")
            
            return False
            
    def _on_finished_run(self, executable_path: str, exit_code: int): 
        self._logger.debug(f"onFinishedRun: Entered for '{executable_path}', exitCode: {exit_code}")
        
        if not self._logic._is_game_running: 
            self._logger.info("Game finished, but was not managed by this plugin in this session. No cleanup needed.")
            return

        self._logic.remove_files_from_game_directory()
        self._logic.set_game_running_status(False) 
        self._logger.info("Game finished. Copied files (if any) removed.")

    def _on_profile_changed(self, old_profile: mobase.IProfile, new_profile: mobase.IProfile): 
        old_profile_name = old_profile.name() if old_profile else "None"
        new_profile_name = new_profile.name() if new_profile else "None"
        self._logger.info(f"Profile changed from '{old_profile_name}' to '{new_profile_name}'.")
        
        if self._logic: 
            self._logic.handle_profile_change()

def createPlugin() -> mobase.IPlugin:
    return ModCopyHelperPlugin()