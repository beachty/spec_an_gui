from dataclasses import dataclass
from typing import List, Dict
from collections import defaultdict

@dataclass
class PRBReading:
    report: str
    prb_num: int
    power: float
    rru: str = ''
    branch: str = ''
    port: str = ''
    cell: str = ''
    sector_carrier: str = ''
    frequency: str = ''  # DL or UL frequency
    interference_report: int = 0

    @property
    def branch_port_key(self) -> str:
        """Generate unique key for branch-port combination"""
        return f"{self.branch}_{self.port}"

    @property
    def sector_carrier_key(self) -> str:
        """Generate unique key for sector carrier pair"""
        return f"{self.sector_carrier}_{self.frequency}"

class PRBReadingCollection:
    def __init__(self):
        self.readings: List[PRBReading] = []

    def add_reading(self, reading: PRBReading):
        self.readings.append(reading)

    def get_sector_carrier_groups(self) -> Dict[str, Dict[str, List[PRBReading]]]:
        """
        Groups readings by sector carrier pairs and their branch-port combinations
        Returns: Dict[sector_carrier_key, Dict[branch_port_key, readings]]
        """
        groups = defaultdict(lambda: defaultdict(list))
        for reading in self.readings:
            groups[reading.sector_carrier_key][reading.branch_port_key].append(reading)
        return dict(groups)

    def get_unique_branch_ports(self) -> List[str]:
        """Returns list of unique branch-port combinations"""
        return list(set(reading.branch_port_key for reading in self.readings))

    def get_unique_sector_carriers(self) -> List[str]:
        """Returns list of unique sector carrier pairs"""
        return list(set(reading.sector_carrier_key for reading in self.readings))