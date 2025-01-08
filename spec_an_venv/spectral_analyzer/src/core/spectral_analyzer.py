import os
import re
import sys
import time
import math
import shutil
import paramiko
import logging
import warnings
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
from .prb_reading import PRBReading
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

class SpectralAnalyzer:
    def __init__(self, sane, chart_max=-95, chart_min=-125):
        # Configure matplotlib to suppress console output
        plt.set_loglevel('WARNING')
        warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
        warnings.filterwarnings('ignore', category=UserWarning, module='PIL')
        warnings.filterwarnings('ignore', category=UserWarning, module='PngImagePlugin')

        self.sane = sane
        self.chart_max = chart_max
        self.chart_min = chart_min
        self.sector_cells: List[Tuple[str, str]] = []
        self.sector_logs: Dict[Tuple[str, str], str] = {}  # (sector, cell) -> logfile path
        self.readings: List[PRBReading] = []
        self.logfile = ''
        self.logfile_contents: Dict[Tuple[str, str], str] = {}

    def set_sector_cells(self, sector_cells: List[Tuple[str, str]]):
        self.sector_cells = sector_cells

    def construct_amos_command(self, sector: str, cell: str) -> str:
        cmd = (
            f'amos {cell[:6]} "func ref_loop;'
            f' get \\$mo sectorcarrierref > \\$seccarref;'
            f' \\$splitref = split(\\$seccarref);'
            f' for \\$j = 6 to \\$split_last;'
            f' \\$seccarref = \\$splitref[\\$j];'
            f' if \\$seccarref ~ ^ENodeBFunction=.*,SectorCarrier={sector};'
            f' l+mmo;'
            f' pget \\$seccarref,PmUlInterferenceReport=.* pmradiorecinterferencepwrbrprb [^0];'
            f' get \\$seccarref,PmUlInterferenceReport=.* rfbranchrxref;'
            f' get rfbranch rfportref;'
            f' get \\$mo EUtranCellFDDId;'
            f' l-;'
            f' fi;done;endfunc;'
            f' lt all;mr active_cells;'
            f' ma active_cells eutrancellfdd.*{cell} operationalstate 1;'
            f' for \\$mo in active_cells;ref_loop;done; mr active_cells; pv logfile$;"'
        )

        return cmd
    
    def run_amos(self, sector: str, cell: str) -> bool:
        """
        Execute AMOS command for sector-cell pair and store logfile path.
        Returns: True if successful, False otherwise.
        """
        if not self.sane or not self.sane.channel:
            raise ConnectionError("No active SANE session")
                
        try:
            # Construct and send AMOS command
            cmd = self.construct_amos_command(sector, cell)
            self.sane.parent.log_debug(f"Executing AMOS command for {sector}-{cell}")
            self.sane.channel.send(cmd + '\n')
                
            # Collect output
            output = ""
            while True:
                if self.sane.channel.recv_ready():
                    chunk = self.sane.channel.recv(65535).decode()
                    output += chunk
                    if re.search(r':~\$', output):
                        break
                time.sleep(0.1)
                    
            # Extract logfile path from output
            for line in output.splitlines():
                if line.startswith('$logfile = '):
                    logfile = line.split('=')[1].strip()
                    self.sector_logs[(sector, cell)] = logfile
                    self.sane.parent.log_debug(f"Stored logfile for {sector}-{cell}: {logfile}")
                    return True
                        
            self.sane.parent.log_debug(f"Logfile path not found in AMOS output for {sector}-{cell}")
            return False
                
        except Exception as e:
            self.sane.parent.log_debug(f"AMOS command failed for {sector}-{cell}: {str(e)}")
            raise

    def read_logfile(self, sector: str, cell: str) -> bool:
        """
        Read the logfile content for a given sector-cell pair and store it.
        Returns: True if successful, False otherwise.
        """
        logfile = self.sector_logs.get((sector, cell))
        if not logfile:
            self.display_error(f"No logfile found for {sector}-{cell}")
            return False
    
        if not self.sane or not self.sane.channel:
            self.sane.parent.log_debug("No active SANE channel available")
            raise RuntimeError("No active SANE channel available")
            
        try:
            cmd = f'cat {logfile}\n'
            self.sane.parent.log_debug(f"Reading logfile for {sector}-{cell}: {logfile}")
            self.sane.channel.send(cmd)
    
            content = ""
            while True:
                if self.sane.channel.recv_ready():
                    chunk = self.sane.channel.recv(65535).decode()
                    content += chunk
                    if re.search(r':~\$', content):
                        break
                time.sleep(0.1)
                
            if not content:
                self.sane.parent.log_debug(f"No content received from logfile for {sector}-{cell}")
                return False
                
            content_lines = content.splitlines()[1:-1]
            clean_content = '\n'.join(content_lines)
            
            # Store content in dictionary
            self.logfile_contents[(sector, cell)] = clean_content
            self.sane.parent.log_debug(f"Logfile content stored for {sector}-{cell}")
            return True
                
        except Exception as e:
            self.sane.parent.log_debug(f"ERROR: Failed to read logfile for {sector}-{cell}: {str(e)}")
            return False
        
    def read_prb_logfile(self, sector: str, cell: str) -> bool:
        """
        Read and parse PRB data from the stored logfile content.
        Returns: True if successful, False otherwise.
        """
        try:
            content = self.logfile_contents.get((sector, cell))
            if not content:
                self.sane.parent.log_debug(f"No logfile content available for {sector}-{cell}")
                return False
    
            self.parse_prb_data(sector, content)
            self.sane.parent.log_debug(f"Parsed PRB data for {sector}-{cell}")
            return True
        except Exception as e:
            self.sane.parent.log_debug(f"ERROR: Failed to parse PRB data for {sector}-{cell}: {str(e)}")
            return False

    def parse_prb_data(self, sc: str, output: str, samples: int = 1):
        # print("\n=== PRB Data Parsing Started ===")
        # print(f"Processing SectorCarrier: {sc}")
        
        self.readings.clear()
        lines = output.splitlines()
        if '$' in sc:
            sc = sc.replace('$', '')
            # print(f"Cleaned SectorCarrier: {sc}")
        
        sc_escaped = re.escape(sc)

        # Initialize network elements
        antenna_unit_group = None
        rf_branch = None
        rru_port = None
        cell = None

        # Compile regex patterns
        prb_pattern = (
            rf'^SectorCarrier={sc_escaped},PmUlInterferenceReport=1\s+'
            r'(pmRadioRecInterferencePwrBrPrb\d+)\s+(\d+)'
        )
        prb_regex = re.compile(prb_pattern)

        # Patterns to extract branch, RRU port, and cell
        branch_pattern = re.compile(
            r'SectorCarrier=(\w+),PmUlInterferenceReport=1\s+rfBranchRxRef\s+AntennaUnitGroup=(\w+),RfBranch=(\d+)'
        )
        rfport_pattern = re.compile(
            r'AntennaUnitGroup=(\w+),RfBranch=(\d+)\s+rfPortRef\s+FieldReplaceableUnit=RRU-(\w+),RfPort=([A-Z])'
        )
        cell_pattern = re.compile(
            r'EUtranCellFDD=(\w+)\s+eUtranCellFDDId\s+\1'
        )
        
        # First pass: Find network elements
        # print("\n=== Scanning Network Elements ===")
        for line in lines:
            if branch_match := branch_pattern.search(line):
                sector_carrier, antenna_unit_group, rf_branch = branch_match.groups()
                # print(f"Found Branch - AU: {antenna_unit_group}, Branch: {rf_branch}")
            
            elif rfport_match := rfport_pattern.search(line):
                ag, rb, rru, port = rfport_match.groups()
                if ag == antenna_unit_group and rb == rf_branch:
                    rru_port = f"{rru}, Port {port}"
                    # print(f"Found RRU Port: {rru_port}")
            
            elif cell_match := cell_pattern.search(line):
                cell = cell_match.group(1)
                # print(f"Found Cell: {cell}")

        # Second pass: Collect PRB readings
        # print("\n=== Collecting PRB Data ===")
        for line in lines:
            if match := prb_regex.search(line):
                report, power = match.groups()
                prb_num = int(re.findall(r'\d+', report)[-1])
                raw_power = int(power)
                
                # print(f"PRB {prb_num:3d} - Raw Power: {raw_power:6d}")
                
                prb_reading = PRBReading(
                    report=report,
                    prb_num=prb_num,
                    power=raw_power,  # Store raw power, calculate later
                    rru=rru_port.split(',')[0] if rru_port else '',
                    branch=rf_branch if rf_branch else '',
                    port=rru_port.split(',')[1].strip() if rru_port else '',
                    cell=cell if cell else ''
                )
                self.readings.append(prb_reading)

        self.readings.sort(key=lambda x: x.prb_num)
        
        # print(f"\n=== Parse Summary ===")
        # print(f"PRBs found: {len(self.readings)}")
        # print(f"Network Config:")
        # print(f"- AU Group: {antenna_unit_group or 'Not found'}")
        # print(f"- RF Branch: {rf_branch or 'Not found'}")
        # print(f"- RRU Port: {rru_port or 'Not found'}")
        # print(f"- Cell: {cell or 'Not found'}")

    def calculate_samples(self, sector: str, cell: str) -> int:
        """
        Calculate the number of samples based on the logfile content.
        Returns: Number of samples or 0 if invalid.
        """
        try:
            content = self.logfile_contents.get((sector, cell))
            if not content:
                self.sane.parent.log_debug(f"No logfile content available for {sector}-{cell}")
                return 0
            lines = content.splitlines()
            samp_time = None
            for line in lines:
                if 'stopfile=' in line:
                    parts = line.split()
                    samp_time = parts[0]  # e.g., '250103-16:33:41-0600'
                    break
            else:
                # print("INFO: No stopfile entry found in the logfile.")
                return 0

            # Extract minutes and seconds from samp_time
            # samp_time format: 'YYMMDD-HH:MM:SS-TZ'
            time_part = samp_time.split('-')[1]  # '16:33:41'
            samp_min = int(time_part.split(':')[1]) % 15
            samp_sec = int(time_part.split(':')[2])

            # Calculate samples
            samples = ((60 * samp_min) + samp_sec) * 1000 / 40  # Equivalent to *25
            # print(f"INFO: Calculating samples: ((60 * {samp_min}) + {samp_sec}) * 1000 / 40 = {samples}")

            return samples
        except Exception as e:
            # print(f"INFO: Error calculating samples: {e}")
            return 0

    def calculate_power(self, power: float, samples: int) -> float:
        try:
            if samples == 0:
                raise ZeroDivisionError("Samples count is zero.")

            avg_power_mw = power / samples
            # print(f"INFO: Average Power (mW) = {power} / {samples} = {avg_power_mw}")

            # Corrected exponent from 2**44 to 2**-44 to match Bash script
            factor = 2 ** -44
            # print(f"INFO: Using factor = 2^-44 = {factor}")

            adjusted_power = avg_power_mw * factor
            # print(f"INFO: Adjusted Power = {avg_power_mw} * {factor} = {adjusted_power}")

            p_dbm = 10 * math.log10(adjusted_power)
            # print(f"INFO: Calculating p_dbm = 10 * log10({adjusted_power}) = {p_dbm}")

            return p_dbm

        except ZeroDivisionError as zde:
            print(f"ERROR: {zde}")
            return self.chart_min  # Return min power on error

        except ValueError as ve:
            print(f"ERROR: Invalid value encountered: {ve}")
            return self.chart_min  # Return min power on error

        except Exception as e:
            print(f"ERROR: Unexpected error in calculate_power: {e}")
            return self.chart_min  # Return min power on error

    def draw_power_bars(self, sc):
        if not self.readings:
            self.display_error("No readings to display")
            return
        
        plt.figure(f"SC: {sc} | FDD: {self.readings[0].cell}")

        # Clear previous plot
        plt.clf()
        plt.cla()

        # Prepare data
        prb_nums = [r.prb_num for r in self.readings]
        powers = [r.power for r in self.readings]

        min_pwr = min(powers)
        max_pwr = max(powers)

        # Retrieve sector carrier (Assuming it's stored as an attribute)
        sector_carrier = sc

        cmap = LinearSegmentedColormap.from_list("custom", ["green", "yellow", "red"])

        norm = plt.Normalize(self.chart_min, self.chart_max)
        colors = cmap(norm(powers))

        # Set plot title with metadata including sector carrier
        title = (
            f"\nPRB Power Distribution - Sector: {sector_carrier} | "
            f"Cell: {self.readings[0].cell} | "
            f"RRU: {self.readings[0].rru} | "
            f"Branch: {self.readings[0].branch} | "
            f"Port: {self.readings[0].port}"
        )
        plt.title(title, fontsize=12, weight='bold', color='black')

        # Configure axes
        plt.xlabel("Power (dBm)")
        plt.ylabel("PRB Number")

        # Invert colors: set background to skyblue and bars to white
        ax = plt.gca()
        ax.set_facecolor('white')
        fig = plt.gcf()
        fig.set_facecolor('white')

        # Create horizontal bar plot with bars starting from -125
        bars = plt.barh(prb_nums, 
                       [p - self.chart_min for p in powers],
                       left=self.chart_min,
                       color=colors,
                       edgecolor='black',
                       align='edge')

        # Set fixed x-axis limits
        plt.xlim(self.chart_min, self.chart_max)
        plt.gca().invert_yaxis()

        # Add grid with transparent lines
        plt.grid(True, axis='x', linestyle='--', alpha=0.5)

        # Add labels next to each bar
        for bar, power in zip(bars, powers):
            plt.text(
                power + 0.5,  # Slightly offset the label
                bar.get_y() + bar.get_height() / 2,
                f"{power:.2f} dBm",
                va='center',
                fontsize=8,
                color='red'
            )

        # Set y-axis labels for each PRB and adjust layout to prevent overlap
        plt.yticks(prb_nums)
        
        # Adjust figure size based on number of PRBs to prevent overlap
        num_prbs = len(prb_nums)
        fig.set_size_inches(10, max(6, num_prbs * 0.2))

        # Improve layout
        plt.tight_layout()

        # Show the plot
        plt.show(block = False)

    def display_error(self, message: str):
        print(f"ERROR: {message}")

    def process_sector_cell(self, sector: str, cell: str) -> bool:
        """Process a sector-cell pair through the complete analysis pipeline"""
        # print(f"\n=== Processing {sector}-{cell} ===")
        
        # 1. Read logfile
        if not self.read_logfile(sector, cell):
            self.display_error(f"Failed to read logfile for {sector}-{cell}")
            return False
        
        # 2. Read and parse PRB data
        if not self.read_prb_logfile(sector, cell):
            self.display_error(f"Failed to parse PRB data for {sector}-{cell}")
            return False
                
        # print(f"Found {len(self.readings)} PRB readings")
        
        # 3. Calculate samples
        samples = self.calculate_samples(sector, cell)
        if samples == 0:
            self.display_error(f"Invalid sample count for {sector}-{cell}")
            return False
        
        # print(f"Calculated samples: {samples}")
        
        # 4. Calculate power for each reading
        # print("\nCalculating power values...")
        for reading in self.readings:
            raw_power = reading.power
            calculated_power = self.calculate_power(raw_power, samples)
            reading.power = calculated_power
            # print(f"PRB {reading.prb_num:3d}: {raw_power:6d} -> {reading.power:8.2f} dBm")
        
        # 5. Display results
        # print("\nDisplaying power distribution...")
        self.draw_power_bars(sector)
        return True