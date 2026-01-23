from abc import ABC, abstractmethod
import pandas as pd

class BaseImporter(ABC):
    def __init__(self, user):
        self.user = user
        self.stats = {
            'new_sales': 0,
            'existing_sales': 0,
            'errors': 0,
            'products_not_found': set(),
            'customers_created': 0,
            'customers_updated': 0,
        }

    @abstractmethod
    def process_file(self, file_obj):
        """
        Main entry point. Reads file, cleans data, and imports sales.
        Returns stats dict.
        """
        pass

    def _get_stats_summary(self):
        self.stats['products_not_found'] = list(self.stats['products_not_found'])
        return self.stats
