import mobase
import json
import shutil
from pathlib import Path

from .logger import get_logger, PLUGIN_NAME 

SETTINGS_FILE_NAME = "modcopyhelper_settings.json" 
MANIFEST_FILE_NAME = "modcopyhelper_manifest.json" 
MCH_CATEGORY = "ModCopyHelper"

class SimpleCopyLogic:
    def __init__(self, organizer: mobase.IOrganizer):
        self._organizer = organizer
        self._logger = get_logger()
        self._profile_path: Path = None
        self._settings_path: Path = None
        self._manifest_path: Path = None
        self._selected_mods: list[str] = []
        self._copied_files_manifest: dict[str, list[str]] = {"copied_files": [], "copied_dirs": []}
        self._game_path: Path = None
        self._is_game_running = False

    def _ensure_paths_initialized(self):
        if self._profile_path is None and self._organizer.profilePath():
            self._profile_path = Path(self._organizer.profilePath())
            self._settings_path = self._profile_path / SETTINGS_FILE_NAME
            self._manifest_path = self._profile_path / MANIFEST_FILE_NAME
            self._logger.debug(f"Profile paths initialized: {self._profile_path}")

        if self._game_path is None:
            managed_game = self._organizer.managedGame()
            if managed_game:
                game_dir_obj = managed_game.gameDirectory()
                if game_dir_obj and game_dir_obj.path() and game_dir_obj.exists():
                    self._game_path = Path(game_dir_obj.path())
                    self._logger.debug(f"Game path initialized: {self._game_path}")
                else:
                    self._logger.warning(
                        f"Game directory object from managedGame is not valid or does not exist: "
                        f"{game_dir_obj.path() if game_dir_obj else 'None'}"
                    )
            else:
                self._logger.warning("Managed game instance is not available for game path init.")

    def load_settings(self):
        self._ensure_paths_initialized()
        if not self._settings_path:
            self._logger.warning("Cannot load settings: Profile path not yet available.")
            self._selected_mods = []
            return

        if self._settings_path.exists():
            try:
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self._selected_mods = settings.get("selected_mods", []) 
                    self._logger.info(f"Settings loaded from '{self._settings_path}'. Selected mods: {len(self._selected_mods)}")
            except json.JSONDecodeError as e:
                self._logger.error(f"Error decoding settings JSON from '{self._settings_path}': {e}")
                self._selected_mods = []
            except Exception as e: 
                self._logger.error(f"Failed to load settings from '{self._settings_path}': {e}", exc_info=True)
                self._selected_mods = []
        else:
            self._logger.info(f"Settings file '{self._settings_path}' not found. Using empty selection.")
            self._selected_mods = []
        
        self._load_manifest()

    def save_settings(self):
        self._ensure_paths_initialized()
        if not self._settings_path:
            self._logger.error("Cannot save settings: Profile path not yet available.")
            return False
        
        if self._is_game_running:
            self._logger.warning("Attempted to save settings while game is running. Operation skipped.")
            return False
            
        try:
            settings = {"selected_mods": self._selected_mods} 
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            self._logger.info(f"Settings saved to '{self._settings_path}'. Selected mods: {len(self._selected_mods)}")
            return True
        except Exception as e: 
            self._logger.error(f"Failed to save settings to '{self._settings_path}': {e}", exc_info=True)
            return False

    def get_selected_mods(self) -> list[str]:
        self._ensure_paths_initialized()
        return list(self._selected_mods) 

    def set_selected_mods(self, mod_names: list[str]):
        if self._is_game_running:
            self._logger.warning("Attempted to set selected mods while game is running. Operation skipped.")
            return
        self._selected_mods = mod_names
        self.save_settings()

    def _load_manifest(self):
        self._ensure_paths_initialized()
        if not self._manifest_path:
            self._logger.warning("Cannot load manifest: Profile path not yet available.")
            self._copied_files_manifest = {"copied_files": [], "copied_dirs": []}
            return

        if self._manifest_path.exists():
            try:
                with open(self._manifest_path, 'r', encoding='utf-8') as f:
                    self._copied_files_manifest = json.load(f)
                self._logger.info(f"Manifest loaded from '{self._manifest_path}'. "
                                  f"Files: {len(self._copied_files_manifest.get('copied_files',[]))}, "
                                  f"Dirs: {len(self._copied_files_manifest.get('copied_dirs',[]))}")
            except json.JSONDecodeError as e:
                self._logger.error(f"Error decoding manifest JSON from '{self._manifest_path}': {e}")
                self._copied_files_manifest = {"copied_files": [], "copied_dirs": []}
            except Exception as e:
                self._logger.error(f"Failed to load manifest from '{self._manifest_path}': {e}", exc_info=True)
                self._copied_files_manifest = {"copied_files": [], "copied_dirs": []}
        else:
            self._copied_files_manifest = {"copied_files": [], "copied_dirs": []}
            self._logger.info(f"Manifest file '{self._manifest_path}' not found. Initializing empty manifest.")

    def _save_manifest(self):
        self._ensure_paths_initialized()
        if not self._manifest_path:
            self._logger.error("Cannot save manifest: Profile path not yet available.")
            return
        try:
            with open(self._manifest_path, 'w', encoding='utf-8') as f:
                json.dump(self._copied_files_manifest, f, indent=4)
            self._logger.info(f"Manifest saved to '{self._manifest_path}'")
        except Exception as e:
            self._logger.error(f"Failed to save manifest to '{self._manifest_path}': {e}", exc_info=True)

    def _clear_manifest_file(self):
        self._ensure_paths_initialized()
        self._copied_files_manifest = {"copied_files": [], "copied_dirs": []}
        if self._manifest_path :
            if self._manifest_path.exists():
                try:
                    self._manifest_path.unlink()
                    self._logger.info(f"Manifest file '{self._manifest_path}' cleared.")
                except Exception as e:
                    self._logger.error(f"Failed to delete manifest file '{self._manifest_path}': {e}", exc_info=True)
            self._save_manifest()
        else:
            self._logger.warning("Cannot clear manifest file: Profile path not yet available.")

    def check_and_handle_previous_crash(self):
        self._ensure_paths_initialized()
        if not self._manifest_path:
            self._logger.warning("Cannot check for previous crash: Profile path not yet available.")
            return
        self._load_manifest()
        if self._copied_files_manifest and \
           (self._copied_files_manifest.get("copied_files") or self._copied_files_manifest.get("copied_dirs")):
            self._logger.warning(
                f"Manifest file '{self._manifest_path}' indicates a previous unclean shutdown. Attempting to clean up."
            )
            self.remove_files_from_game_directory(force_from_manifest=True)

    def copy_files_to_game_directory(self) -> bool: 
        self._logger.debug("copy_files_to_game_directory: Entered method.")
        self._ensure_paths_initialized()
        if not self._game_path:
            self._logger.error("copy_files_to_game_directory: Game directory path is not available. Aborting copy.")
            return False
        if not self._profile_path:
            self._logger.error("copy_files_to_game_directory: Profile path is not available. Aborting copy.")
            return False
            
        if not self._selected_mods:
            self._logger.debug("copy_files_to_game_directory: No mods in self._selected_mods, attempting to load settings.")
            self.load_settings()

        if not self._selected_mods:
            self._logger.info("copy_files_to_game_directory: No mods selected for copying. Nothing to do.")
            return True

        self._logger.debug(f"copy_files_to_game_directory: Selected mods for copy: {self._selected_mods}")
        self.check_and_handle_previous_crash()

        modlist = self._organizer.modList()
        files_to_copy: list[tuple[Path, Path]] = []
        dirs_to_copy: list[tuple[Path, Path]] = []
        current_manifest_files = []
        current_manifest_dirs = []
        any_item_to_process = False

        for mod_name in self._selected_mods:
            mod = modlist.getMod(mod_name)
            if not mod:
                self._logger.warning(f"copy_files_to_game_directory: Mod '{mod_name}' not found. Skipping.")
                continue

            mod_path = Path(mod.absolutePath())
            self._logger.info(f"copy_files_to_game_directory: Processing mod '{mod_name}' from '{mod_path}'")

            items_in_mod_dir = list(mod_path.iterdir())
            if not items_in_mod_dir:
                self._logger.info(f"copy_files_to_game_directory: Mod '{mod_name}' directory '{mod_path}' is empty. Skipping.")
                continue
            
            any_item_to_process = True
            for item in items_in_mod_dir:
                destination_path = self._game_path / item.name
                self._logger.debug(f"copy_files_to_game_directory: Preparing to copy '{item}' to '{destination_path}'")
                
                if destination_path.exists(): 
                    self._logger.info(f"copy_files_to_game_directory: Destination '{destination_path}' already exists. It will be overwritten.")
                
                if item.is_file():
                    self._logger.debug(f"copy_files_to_game_directory: Adding file to copy list: '{item}' -> '{destination_path}'")
                    files_to_copy.append((item, destination_path))
                elif item.is_dir():
                    self._logger.debug(f"copy_files_to_game_directory: Adding directory to copy list: '{item}' -> '{destination_path}'")
                    dirs_to_copy.append((item, destination_path))
        
        if not any_item_to_process:
            self._logger.info("copy_files_to_game_directory: No actual items found in selected mods to process.")
            return True

        if not files_to_copy and not dirs_to_copy: 
            self._logger.info("copy_files_to_game_directory: No files or directories were ultimately queued for copying.")
            return True

        copied_something = False
        self._logger.debug(f"copy_files_to_game_directory: Starting actual copy. Files: {len(files_to_copy)}, Dirs: {len(dirs_to_copy)}")
        try:
            for src, dest in dirs_to_copy:
                self._logger.info(f"Copying directory: '{src}' -> '{dest}'")
                
                shutil.copytree(src, dest, dirs_exist_ok=True) 
                current_manifest_dirs.append(str(dest.relative_to(self._game_path)))
                copied_something = True
            
            for src, dest in files_to_copy:
                self._logger.info(f"Copying file: '{src}' -> '{dest}'")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest) 
                current_manifest_files.append(str(dest.relative_to(self._game_path)))
                copied_something = True

            if copied_something:
                self._copied_files_manifest["copied_files"] = current_manifest_files
                self._copied_files_manifest["copied_dirs"] = current_manifest_dirs
                self._save_manifest()
                self._logger.info("copy_files_to_game_directory: Mod files/dirs copied successfully.")
            else:
                self._logger.info("copy_files_to_game_directory: No files or directories were actually copied.")

            self._logger.debug("copy_files_to_game_directory: Finished copy process. Returning True.")
            return True

        except (IOError, OSError, shutil.Error) as e:
            self._logger.error(f"copy_files_to_game_directory: Error during file/dir copy operation: {e}", exc_info=True)
            self._rollback_copy(current_manifest_files, current_manifest_dirs)
            self._clear_manifest_file()
            return False
        except Exception as e_unexpected:
            self._logger.error(f"copy_files_to_game_directory: Unexpected error during copy: {e_unexpected}", exc_info=True)
            self._rollback_copy(current_manifest_files, current_manifest_dirs)
            self._clear_manifest_file()
            return False

    def _rollback_copy(self, files_to_remove_rel: list[str], dirs_to_remove_rel: list[str]):
        self._ensure_paths_initialized()
        if not self._game_path:
            self._logger.error("Rollback cannot proceed: Game path not available.")
            return

        for rel_path_str in reversed(dirs_to_remove_rel): 
            abs_path = self._game_path / rel_path_str
            if abs_path.is_dir(): 
                try:
                    shutil.rmtree(abs_path)
                    self._logger.info(f"Rolled back directory: '{abs_path}'")
                except Exception as e_del:
                    self._logger.error(f"Rollback failed for directory '{abs_path}': {e_del}", exc_info=True)
            elif abs_path.exists(): 
                 self._logger.warning(f"Rollback: Expected directory but found file or symlink at '{abs_path}'. Not removing.")

        for rel_path_str in files_to_remove_rel: 
            abs_path = self._game_path / rel_path_str
            if abs_path.is_file(): 
                try:
                    abs_path.unlink()
                    self._logger.info(f"Rolled back file: '{abs_path}'")
                except Exception as e_del:
                    self._logger.error(f"Rollback failed for file '{abs_path}': {e_del}", exc_info=True)
            elif abs_path.exists(): 
                 self._logger.warning(f"Rollback: Expected file but found directory or symlink at '{abs_path}'. Not removing.")


    def remove_files_from_game_directory(self, force_from_manifest=False):
        self._ensure_paths_initialized()
        if not self._game_path:
            self._logger.error("Cannot remove files: Game directory path is not available.")
            return True
        if not self._profile_path and not force_from_manifest:
             self._logger.warning("Cannot remove files effectively: Profile path is not available for manifest.")
        
        self._is_game_running = False 

        if not force_from_manifest:
            self._load_manifest()
        
        if not self._copied_files_manifest or \
           not (self._copied_files_manifest.get("copied_files") or self._copied_files_manifest.get("copied_dirs")):
            self._logger.info("No files recorded in manifest to remove.")
            self._clear_manifest_file() 
            return True

        self._logger.info("Attempting to remove copied files/dirs from game directory based on manifest.")
        
        
        files_in_manifest = self._copied_files_manifest.get("copied_files", [])
        for rel_path_str in files_in_manifest:
            file_path = self._game_path / rel_path_str
            if file_path.is_file(): 
                try:
                    file_path.unlink()
                    self._logger.info(f"Removed file: '{file_path}'")
                except (IOError, OSError) as e: 
                    self._logger.error(f"Failed to remove file '{file_path}': {e}.", exc_info=True)
            elif file_path.exists(): 
                 self._logger.warning(f"Manifested item '{file_path}' is not a file. Not removing.")
            else: 
                 self._logger.info(f"Manifested file '{file_path}' not found for removal.")

        dirs_in_manifest = sorted(
            self._copied_files_manifest.get("copied_dirs", []), 
            key=lambda p: len(Path(p).parts),  
            reverse=True
        )
        for rel_path_str in dirs_in_manifest:
            dir_path = self._game_path / rel_path_str
            if dir_path.is_dir(): 
                try:
                    
                    shutil.rmtree(dir_path)
                    self._logger.info(f"Removed directory: '{dir_path}'")
                except (IOError, OSError) as e: 
                    self._logger.error(f"Failed to remove directory '{dir_path}': {e}.", exc_info=True)
            elif dir_path.exists(): 
                self._logger.warning(f"Manifested item '{dir_path}' is not a directory. Not removing.")
            else: 
                 self._logger.info(f"Manifested directory '{dir_path}' not found for removal.")

        self._logger.info("File/Dir removal process finished.")
        self._clear_manifest_file()
        return True

    def map_file_for_overwrite(self, file_path_str: str) -> str:
        self._ensure_paths_initialized()
        if not self._game_path:
            return file_path_str
        if not self._is_game_running: 
            return file_path_str

        file_path = Path(file_path_str)
        try:
            relative_to_game = file_path.relative_to(self._game_path)
        except ValueError: 
            return file_path_str
        
        copied_dirs_rel = self._copied_files_manifest.get("copied_dirs", [])
        for rel_dir_str in copied_dirs_rel:
            if not rel_dir_str or rel_dir_str == ".": continue
            copied_dir_abs = self._game_path / rel_dir_str
            try:
                file_path.relative_to(copied_dir_abs) 
                overwrite_target_path = Path(self._organizer.overwritePath()) / relative_to_game
                overwrite_target_path.parent.mkdir(parents=True, exist_ok=True)
                self._logger.debug(f"Redirecting '{file_path}' (in copied dir '{copied_dir_abs}') to '{overwrite_target_path}'")
                return str(overwrite_target_path)
            except ValueError:
                continue
        
        copied_files_rel = self._copied_files_manifest.get("copied_files", [])
        for rel_file_str in copied_files_rel:
            if not rel_file_str or rel_file_str == ".": continue
            if relative_to_game == Path(rel_file_str):
                overwrite_target_path = Path(self._organizer.overwritePath()) / relative_to_game
                overwrite_target_path.parent.mkdir(parents=True, exist_ok=True)
                self._logger.debug(f"Redirecting '{file_path}' (exact match) to '{overwrite_target_path}'")
                return str(overwrite_target_path)

        return file_path_str

    def handle_profile_change(self):
        self._logger.info("Profile changed. Re-initializing paths and settings.")
        self._profile_path = None
        self._settings_path = None
        self._manifest_path = None
        
        self._ensure_paths_initialized()
        self.load_settings()
        self.check_and_handle_previous_crash()
        self.sync_mod_tags()

    def set_game_running_status(self, is_running: bool):
        self._is_game_running = is_running
        self._logger.info(f"Game running status set to {is_running}.")

    def sync_mod_tags(self):
        self._ensure_paths_initialized()
        modlist = self._organizer.modList()
        all_mods = modlist.allMods()

        self._logger.info(f"Syncing mod categories. Selected mods: {len(self._selected_mods)}")

        for mod_name in all_mods:
            mod = modlist.getMod(mod_name)
            if not mod or mod.isSeparator():
                continue

            current_categories = list(mod.categories())
            is_selected = mod_name in self._selected_mods

            if is_selected:
                if MCH_CATEGORY not in current_categories:
                    try:
                        mod.addCategory(MCH_CATEGORY)
                        self._logger.info(f"Added category '{MCH_CATEGORY}' to '{mod_name}'")
                    except Exception as e:
                        self._logger.error(f"Failed to add category to '{mod_name}': {e}")
            else:
                if MCH_CATEGORY in current_categories:
                    try:
                        result = mod.removeCategory(MCH_CATEGORY)
                        self._logger.info(f"Removed category '{MCH_CATEGORY}' from '{mod_name}': {result}")
                    except Exception as e:
                        self._logger.error(f"Failed to remove category from '{mod_name}': {e}")

        self._logger.info(f"Mod categories sync completed.")

    def disable_selected_mods_in_mo2(self):
        if not self._selected_mods:
            return

        modlist = self._organizer.modList()
        disabled_count = 0

        for mod_name in self._selected_mods:
            try:
                mod = modlist.getMod(mod_name)
                if mod and not mod.isSeparator():
                    is_active = bool(modlist.state(mod_name) & mobase.ModState.ACTIVE)
                    if is_active:
                        modlist.setActive(mod_name, False)
                        disabled_count += 1
                        self._logger.info(f"Disabled mod '{mod_name}' in MO2")
            except Exception as e:
                self._logger.error(f"Failed to disable mod '{mod_name}': {e}", exc_info=True)

        if disabled_count > 0:
            self._logger.info(f"Auto-disabled {disabled_count} selected mods in MO2.")