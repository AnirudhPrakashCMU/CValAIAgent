import json
import logging
import os
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Any, Callable

import jmespath
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..config import settings
from ..models.schemas import MappingsData

logger = logging.getLogger(settings.SERVICE_NAME + ".loader")


class MappingsFileHandler(FileSystemEventHandler):
    """
    Watchdog event handler that detects changes to the mappings file
    and triggers a reload callback.
    """

    def __init__(self, mappings_file_path: Path, reload_callback: Callable[[], None]):
        self.mappings_file_path = mappings_file_path
        self.reload_callback = reload_callback
        logger.info(f"Watching for changes to mappings file: {mappings_file_path}")

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path) == self.mappings_file_path:
            logger.info(f"Detected change to mappings file: {event.src_path}")
            self.reload_callback()


class MappingsLoader:
    """
    Manages loading and hot-reloading of the design mappings file.
    Provides access to the parsed mappings data.
    """

    def __init__(self):
        self.mappings_file_path = settings.get_absolute_mappings_path()
        self.mappings_data: Optional[MappingsData] = None
        self.last_modified_time: float = 0
        self.observer: Optional[Observer] = None
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        
        # Load the mappings file initially
        self.load_mappings()
        
        # Set up file watcher if hot reload is enabled
        if settings.ENABLE_HOT_RELOAD:
            self._setup_file_watcher()
        else:
            logger.info("Hot reload is disabled. Mappings will not be automatically reloaded.")

    def _setup_file_watcher(self):
        """Set up a watchdog observer to monitor the mappings file for changes."""
        try:
            self.observer = Observer()
            handler = MappingsFileHandler(self.mappings_file_path, self.load_mappings)
            # Watch the directory containing the file
            self.observer.schedule(handler, self.mappings_file_path.parent, recursive=False)
            self.observer.start()
            logger.info(f"File watcher started for {self.mappings_file_path}")
        except Exception as e:
            logger.error(f"Failed to set up file watcher: {e}", exc_info=True)
            self.observer = None

    def load_mappings(self) -> bool:
        """
        Load and parse the mappings file.
        Returns True if the file was successfully loaded and parsed.
        """
        with self.lock:
            try:
                if not self.mappings_file_path.exists():
                    logger.error(f"Mappings file not found: {self.mappings_file_path}")
                    return False
                
                # Check if the file has been modified since last load
                current_mtime = os.path.getmtime(self.mappings_file_path)
                if current_mtime <= self.last_modified_time:
                    logger.debug("Mappings file has not changed since last load.")
                    return True  # File hasn't changed, no need to reload
                
                logger.info(f"Loading mappings from {self.mappings_file_path}")
                with open(self.mappings_file_path, 'r') as f:
                    raw_data = json.load(f)
                
                # Parse and validate the data using Pydantic model
                self.mappings_data = MappingsData(**raw_data)
                self.last_modified_time = current_mtime
                logger.info(
                    f"Mappings loaded successfully: "
                    f"{len(self.mappings_data.brands)} brands, "
                    f"{len(self.mappings_data.styles)} styles, "
                    f"{len(self.mappings_data.tailwind_token_map)} token mappings"
                )
                return True
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse mappings file: {e}", exc_info=True)
                return False
            except Exception as e:
                logger.error(f"Error loading mappings: {e}", exc_info=True)
                return False

    def get_mappings(self) -> Optional[MappingsData]:
        """Get the current mappings data."""
        with self.lock:
            return self.mappings_data

    def get_brand_properties(self, brand_id: str) -> Dict[str, Any]:
        """
        Get the properties for a specific brand.
        Returns an empty dict if the brand is not found.
        """
        with self.lock:
            if not self.mappings_data:
                return {}
            return self.mappings_data.brands.get(brand_id.lower(), {})

    def get_style_properties(self, style_id: str) -> Dict[str, Any]:
        """
        Get the properties for a specific style.
        Returns an empty dict if the style is not found.
        """
        with self.lock:
            if not self.mappings_data:
                return {}
            return self.mappings_data.styles.get(style_id.lower(), {})

    def get_tailwind_class(self, token: str) -> str:
        """
        Get the Tailwind CSS class for a specific token.
        Returns the token itself if no mapping is found.
        """
        with self.lock:
            if not self.mappings_data:
                return token
            return self.mappings_data.tailwind_token_map.get(token, token)

    def query_mappings(self, jmespath_query: str) -> Any:
        """
        Query the mappings data using JMESPath syntax.
        Useful for complex queries across the mappings data.
        """
        with self.lock:
            if not self.mappings_data:
                return None
            try:
                return jmespath.search(jmespath_query, self.mappings_data.model_dump())
            except Exception as e:
                logger.error(f"JMESPath query error: {e}", exc_info=True)
                return None

    def stop_file_watcher(self):
        """Stop the file watcher if it's running."""
        if self.observer and self.observer.is_alive():
            logger.info("Stopping file watcher...")
            self.observer.stop()
            self.observer.join(timeout=2.0)
            logger.info("File watcher stopped.")

    def __del__(self):
        """Ensure the file watcher is stopped when the object is garbage collected."""
        self.stop_file_watcher()


# Create a singleton instance of the MappingsLoader
_loader_instance = None


def get_mappings_loader() -> MappingsLoader:
    """
    Get the singleton instance of MappingsLoader.
    This ensures that there's only one instance monitoring the file.
    """
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = MappingsLoader()
    return _loader_instance


# Optionally provide a cached accessor for frequently accessed mappings
@lru_cache(maxsize=settings.LRU_CACHE_MAXSIZE if settings.ENABLE_LRU_CACHE else 0)
def get_cached_mappings() -> Optional[MappingsData]:
    """
    Get the current mappings data with caching.
    The cache is invalidated when the mappings file changes.
    """
    return get_mappings_loader().get_mappings()


if __name__ == "__main__":
    # Example usage for testing this module directly
    logging.basicConfig(level=logging.DEBUG)
    
    loader = get_mappings_loader()
    mappings = loader.get_mappings()
    
    if mappings:
        print(f"Loaded {len(mappings.brands)} brands:")
        for brand in mappings.brands:
            print(f"  - {brand}")
        
        print(f"\nLoaded {len(mappings.styles)} styles:")
        for style in mappings.styles:
            print(f"  - {style}")
        
        # Example JMESPath query
        button_styles = loader.query_mappings("styles[?contains(keys(@), 'button')]")
        if button_styles:
            print("\nButton-related styles:")
            for style in button_styles:
                print(f"  - {style}")
    
    # If hot reload is enabled, keep the script running to observe file changes
    if settings.ENABLE_HOT_RELOAD:
        try:
            print("\nWatching for changes to mappings file. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping file watcher...")
        finally:
            loader.stop_file_watcher()
