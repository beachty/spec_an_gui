from dataclasses import dataclass

@dataclass
class PRBReading:
    report: str
    prb_num: int
    power: float
    rru: str = ''
    branch: str = ''
    port: str = ''
    cell: str = ''