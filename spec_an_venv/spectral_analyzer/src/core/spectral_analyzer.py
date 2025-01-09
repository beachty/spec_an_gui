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
from collections import defaultdict
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
        self.enbid: str = ''
        self.readings: List[PRBReading] = []
        self.log_path = ''
        self.logfile_contents: Dict[Tuple[str, str], str] = {}
        self.sector_cell_pairs = []
        self.enb_id = None
        self.sector_stopfile_times = {}

    def set_sector_cells(self, sector_cells: List[Tuple[str, str]]):
        self.sector_cells = sector_cells

    def set_pairs_and_enbid(self, pairs: List[Tuple[str, str]], enbid: str):
        """Set sector-cell pairs and ENB ID for processing"""
        self.sector_cell_pairs = pairs
        self.enb_id = enbid

    def construct_amos_command(self, enbid: str, seed: str) -> str:
        """Construct AMOS command with provided cell ID and seed timestamp."""
        self.enbid = enbid[:6]
        enbid = self.enbid

        cmd = (
            f'amos {enbid} "l+ /home/shared/{self.remote_user}/spec_an_gui/{seed}.log; func ref_loop; get \\$mo sectorcarrierref > \\$seccarref;'
            f'\\$splitref = split(\\$seccarref); for \\$j = 6 to \\$split_last; \\$seccarref = \\$splitref[\\$j];'
            f'pget \\$seccarref,PmUlInterferenceReport=.* pmradiorecinterferencepwrbrprb [^0];'
            f'get \\$seccarref,PmUlInterferenceReport=.* rfbranchrxref; get rfbranch rfportref;'
            f'get \\$mo EUtranCellFDDId; done; endfunc; lt all; mr active_cells;'
            f'ma active_cells eutrancellfdd.* operationalstate 1; for \\$mo in active_cells;ref_loop;done; mr active_cells; l-; pv logfile$;"'
        )
        return cmd

    def read_channel_output(self) -> str:
        """Read channel output until shell prompt."""
        output = ""
        while True:
            if self.sane.channel.recv_ready():
                chunk = self.sane.channel.recv(65535).decode()
                output += chunk
                if re.search(r':~\$', output):
                    break
            time.sleep(0.1)
        return output

    def get_username_from_prompt(self, output: str) -> str:
        """Extract username from shell prompt"""
        prompt_pattern = r'(\w+)@[\w-]+:~\$'
        if match := re.search(prompt_pattern, output):
            return match.group(1)
        # handle cases of: ctchgrp@scp-1-scripting:NASHVILLE1:~$
        prompt_pattern = r'(\w+)@[\w-]+:[\w-]+:~\$'
        if match := re.search(prompt_pattern, output):
            return match.group(1)
        raise ValueError("Could not detect username from prompt")

    def check_directory_exists(self, path: str) -> bool:
        """Check if directory exists on remote system using bash test command"""
        try:
            # Use bash test command - returns 0 if directory exists
            self.sane.channel.send(f'test -d {path} && echo "EXISTS_YEP" || echo "NOT_EXISTS"\n')
            output = self.read_channel_output().strip()
            return "EXISTS_YEP" in output
        except Exception as e:
            print(f"Error checking directory: {e}")
            return False
    
    def run_amos(self, enbid: str) -> bool:
        """Execute AMOS command and store logfile path."""
        if not self.sane or not self.sane.channel:
            print("ERROR: No active SANE session")
            raise ConnectionError("No active SANE session")
                
        try:
            # Get initial prompt to detect username
            self.sane.channel.send('\n')
            output = self.read_channel_output()
            self.remote_user = self.get_username_from_prompt(output)
            print(f"Detected user from prompt: {self.remote_user}")

            # Check and create log directory if needed
            log_dir = f'/home/shared/{self.remote_user}/spec_an_gui/'
            if not self.check_directory_exists(log_dir):
                print(f"Creating log directory: {log_dir}")
                self.sane.channel.send(f'mkdir -p {log_dir}\n')
                self.read_channel_output()
            else:
                print(f"Log directory already exists: {log_dir}")

            # Generate seed timestamp and continue with AMOS command
            seed = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Construct and execute command
            cmd = self.construct_amos_command(enbid, seed)
            print(f"\n=== Executing AMOS Command for {enbid} ===")
            print(f"Command: {cmd}\n")
            self.sane.parent.log_debug(f"Executing AMOS command for {enbid}")
            self.sane.channel.send(cmd + '\n')
            
            # Collect output
            output = self.read_channel_output()
            # print("\n=== Raw Output ===")
            # print(output)
            # print("================\n")
                    
            # Extract logfile path from output
            for line in output.splitlines():
                if line.startswith('$logfile = '):
                    logfile = line.split('=')[1].strip()
                    self.log_path = logfile
                    print(f"Found logfile: {logfile}")
                    self.sane.parent.log_debug(f"Stored logfile for {enbid}: {logfile}")
                    return True
                        
            print(f"ERROR: No logfile path found in output for {enbid}")
            self.sane.parent.log_debug(f"Logfile path not found in AMOS output for {enbid}")
            return False
                
        except Exception as e:
            error_msg = f"AMOS command failed for {enbid}: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.sane.parent.log_debug(error_msg)
            raise

    def read_logfile(self, enbid: str) -> bool:
        """
        Read the logfile content for a given sector-cell pair and store it.
        Returns: True if successful, False otherwise.
        """
        logfile = self.log_path
        if not logfile:
            self.display_error(f"No logfile found for {enbid}")
            return False
    
        if not self.sane or not self.sane.channel:
            self.sane.parent.log_debug("No active SANE channel available")
            raise RuntimeError("No active SANE channel available")
            
        try:
            cmd = f'cat {logfile}\n'
            self.sane.parent.log_debug(f"Reading logfile for {enbid}: {logfile}")
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
                self.sane.parent.log_debug(f"No content received from logfile for {enbid}")
                return False
                
            content_lines = content.splitlines()[1:-1]
            clean_content = '\n'.join(content_lines)
            
            # Store content in dictionary
            self.logfile_contents = clean_content
            self.sane.parent.log_debug(f"Logfile content stored for {enbid}")
            return True
                
        except Exception as e:
            self.sane.parent.log_debug(f"ERROR: Failed to read logfile for {enbid}: {str(e)}")
            return False
        
    def parse_prb_data(self, sc: str, cell: str, output: str, samples: int = 1):
        print(f"\n=== Starting PRB Data Parse for Sector Carrier {sc} and Cell {cell} ===")
        
        # Extract stopfile time
        stopfile_time = self.parse_stopfile_time(output, sc)
        print(f"Found stopfile time for SC {sc}: {stopfile_time}")
        
        self.readings.clear()
        lines = output.splitlines()

        # Updated regex pattern to be more flexible with FDD formats
        cell_sc_pattern = re.compile(
            rf'EUtranCellFDD={cell}\s+sectorCarrierRef.*?\[.*?\].*?\n((?:\s*>>>\s*sectorCarrierRef\s*=\s*ENodeBFunction=\d+,SectorCarrier=[\w\d]+\n?)*)',
            re.DOTALL
        )

        # Other patterns remain the same
        prb_pattern = re.compile(
            r'SectorCarrier=([\w\d]+),PmUlInterferenceReport=(\d+)\s+pmRadioRecInterferencePwrBrPrb(\d+)\s+(\d+)'
        )
        branch_pattern = re.compile(
            r'SectorCarrier=([\w\d]+),PmUlInterferenceReport=(\d+)\s+rfBranchRxRef\s+AntennaUnitGroup=([\w\d]+),RfBranch=(\d+)'
        )
        port_pattern = re.compile(
            r'AntennaUnitGroup=([\w\d]+),RfBranch=(\d+)\s+rfPortRef\s+FieldReplaceableUnit=RRU-([\w\d]+),RfPort=([A-Z])'
        )

        # Data structures
        sector_map = {
            'cell': None,
            'au_group': None,
            'rru': None,
            'branch_to_port': {},    
            'report_to_branch': {},  
            'readings': defaultdict(list)  
        }

        output_text = '\n'.join(lines)
        
        # Update cell mapping section
        if cell_match := cell_sc_pattern.search(output_text):
            sector_carriers_text = cell_match.group(1)
            print("\nRegex Match Results:")
            print(f"Matched Cell: {cell}")
            print(f"Raw Carrier Text:\n{sector_carriers_text}")
            
            # Extract individual sector carriers
            sc_pattern = re.compile(r'SectorCarrier=([\w\d]+)')
            sector_carriers = sc_pattern.findall(sector_carriers_text)
            print(f"\nExtracted Carriers: {sector_carriers}")
            
            # Only map if provided sector carrier matches
            if sc == "*" or sc in sector_carriers:
                sector_map['cell'] = cell
                print(f"\nSuccess: Mapped Cell {cell} to Sector Carrier {sc}")
                print(f"All bound sector carriers: {sector_carriers}")
            else:
                print(f"\nWarning: Sector Carrier {sc} not found in carriers: {sector_carriers}")
        else:
            print(f"\nError: No pattern match found for Cell {cell}")
            print("Current Pattern:", cell_sc_pattern.pattern)
    
        # Step 2: Collect PRB readings 
        for prb_match in prb_pattern.finditer(output_text):
            sector, report, prb_num, power = prb_match.groups()
            if sc == "*" or sector == sc:
                print(f"Found PRB reading: SC={sector} Report={report} PRB={prb_num} Power={power}")
                sector_map['readings'][report].append((int(prb_num), int(power)))
    
        # Step 3: Map Reports to Branches
        for branch_match in branch_pattern.finditer(output_text):
            sector, report, au_group, branch = branch_match.groups() 
            if sc == "*" or sector == sc:
                sector_map['au_group'] = au_group
                sector_map['report_to_branch'][report] = branch
                print(f"Mapped Report {report} to Branch {branch}")
    
        # Step 4: Map Branches to Ports
        for port_match in port_pattern.finditer(output_text):
            au_group, branch, rru, port = port_match.groups()
            if au_group == sector_map['au_group']:
                sector_map['rru'] = f"RRU-{rru}"
                sector_map['branch_to_port'][branch] = port
                print(f"Mapped Branch {branch} to Port {port}")
    
        # Create final readings
        for report, prb_readings in sector_map['readings'].items():
            branch = sector_map['report_to_branch'].get(report)
            if branch:
                port = sector_map['branch_to_port'].get(branch)
                for prb_num, power in prb_readings:
                    reading = PRBReading(
                        report=f"pmRadioRecInterferencePwrBrPrb{prb_num}",
                        prb_num=prb_num,
                        power=power,
                        rru=sector_map['rru'],
                        branch=branch,
                        port=port,
                        cell=sector_map['cell'],
                        sector_carrier=sc,
                        interference_report=int(report)
                    )
                    self.readings.append(reading)
    
        print("\n=== Final Mappings ===")
        print(f"Sector: {sc}")
        print(f"Cell: {sector_map['cell']}")
        print(f"RRU: {sector_map['rru']}")
        print(f"Branch->Port: {sector_map['branch_to_port']}")
        print(f"Report->Branch: {sector_map['report_to_branch']}")
        print(f"Total Readings: {len(self.readings)}")

    def parse_stopfile_time(self, output: str, sector: str) -> str:
            """Extract stopfile time for a sector carrier from output."""
            lines = output.splitlines()
            current_sector = None
            
            for line in lines:
                if f'SectorCarrier={sector},' in line:
                    current_sector = sector
                elif current_sector and '-' in line and ':' in line:
                    # Match timestamp format: 250109-08:35:24-0600
                    if match := re.match(r'(\d{6}-\d{2}:\d{2}:\d{2}-\d{4})', line):
                        self.sector_stopfile_times[sector] = match.group(1)
                        return match.group(1)
            return None

    def calculate_samples(self, sector: str) -> int:
        """Calculate samples for a sector using its stored stopfile time."""
        try:
            stopfile_time = self.sector_stopfile_times.get(sector)
            if not stopfile_time:
                self.sane.parent.log_debug(f"No stopfile time found for sector {sector}")
                return 0

            # Extract time components from format: YYMMDD-HH:MM:SS-TZ
            time_part = stopfile_time.split('-')[1]  # HH:MM:SS
            minutes = int(time_part.split(':')[1]) % 15
            seconds = int(time_part.split(':')[2])

            # Calculate samples
            samples = ((60 * minutes) + seconds) * 1000 / 40
            return int(samples)

        except Exception as e:
            self.sane.parent.log_debug(f"Error calculating samples for {sector}: {str(e)}")
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

        # Group readings by branch/port combination
        grouped_readings = defaultdict(list)
        for reading in self.readings:
            key = (reading.branch, reading.port)
            grouped_readings[key].append(reading)

        num_plots = len(grouped_readings)
        rows = math.ceil(math.sqrt(num_plots))
        cols = math.ceil(num_plots / rows)

        fig = plt.figure(figsize=(15, 5*rows))
        
        # Set both figure window title and suptitle
        fig.canvas.manager.set_window_title(f"{sc}_{self.readings[0].cell}")
        fig.suptitle(f"PRB Power Distribution - Sector Carrier: {sc} | FDD: {self.readings[0].cell}",
                    fontsize=16, weight='bold')
    
        for idx, ((branch, port), readings) in enumerate(grouped_readings.items(), 1):
            ax = fig.add_subplot(rows, cols, idx)
            
            # Plot data
            prb_nums = [r.prb_num for r in readings]
            powers = [r.power for r in readings]
            
            cmap = LinearSegmentedColormap.from_list("custom", ["green", "yellow", "red"])
            norm = plt.Normalize(self.chart_min, self.chart_max)
            colors = cmap(norm(powers))
    
            bars = ax.barh(prb_nums,
                        [p - self.chart_min for p in powers],
                        left=self.chart_min,
                        color=colors,
                        edgecolor='black',
                        align='edge')
    
            # Configure subplot
            ax.set_title(f"Branch {branch} | {readings[0].rru} | Port {port}")
            ax.set_xlabel("Power (dBm)")
            ax.set_ylabel("PRB Number")
            ax.set_xlim(self.chart_min, self.chart_max)
            
            # Set custom y-ticks at intervals of 5
            yticks = list(range(0, max(prb_nums) + 5, 5))
            ax.set_yticks(yticks)
            
            ax.invert_yaxis()
            ax.grid(True, axis='x', linestyle='--', alpha=0.5)
    
            # Add power labels
            for bar, power in zip(bars, powers):
                ax.text(power + 0.5,
                    bar.get_y() + bar.get_height()/2,
                    f"{power:.2f}",
                    va='center',
                    fontsize=8,
                    color='red')
    
        plt.tight_layout()
        plt.show(block=False)

    def display_error(self, message: str):
        print(f"ERROR: {message}")

    def process_sector_cell(self, sector: str, cell: str, enbid: str) -> bool:
        """Process a sector-cell pair after AMOS command execution"""
        if not self.logfile_contents:
            self.display_error(f"No logfile content found for {enbid}")
            return False
        
        # Pass cell to parse_prb_data
        self.parse_prb_data(sector, cell, self.logfile_contents)
        
        # 3. Calculate samples (fixed argument count)
        samples = self.calculate_samples(sector)
        if samples == 0:
            self.display_error(f"Invalid sample count for {sector}-{cell}")
            return False
        
        # 4. Calculate power for each reading
        for reading in self.readings:
            raw_power = reading.power
            calculated_power = self.calculate_power(raw_power, samples)
            reading.power = calculated_power
        
        # 5. Display results
        self.draw_power_bars(sector)
        return True
    
    def process_all_pairs(self) -> bool:
        """Process all sector-cell pairs"""
        if not self.sector_cell_pairs or not self.enb_id:
            raise ValueError("Sector-cell pairs and ENB ID must be set before processing")
            
        # Run AMOS command once for all pairs
        if not self.run_amos(self.enb_id):
            self.sane.parent.log_debug(f"Failed to execute AMOS command for ENB {self.enb_id}")
            return False
            
        # Read logfile once
        if not self.read_logfile(self.enb_id):
            self.display_error(f"Failed to read logfile for {self.enb_id}")
            return False
    
        # Process each sector-cell pair
        success = True
        for sector, cell in self.sector_cell_pairs:
            try:
                self.sane.parent.log_debug(f"Processing pair: {sector}-{cell}")
                if sector == "*":
                    # Fetch all available sector carriers for the given cell
                    available_sectors = self.get_available_sectors(cell)
                    for available_sector in available_sectors:
                        if not self.process_sector_cell(available_sector, cell, self.enb_id):
                            self.sane.parent.log_debug(f"Failed to process {available_sector}-{cell}")
                            success = False
                else:
                    if not self.process_sector_cell(sector, cell, self.enb_id):
                        self.sane.parent.log_debug(f"Failed to process {sector}-{cell}")
                        success = False
                    
            except Exception as e:
                self.sane.parent.log_debug(f"Error processing {sector}-{cell}: {str(e)}")
                success = False
                
        return success

    def get_available_sectors(self, cell: str) -> List[str]:
        """Fetch all available sector carriers for a given cell from logfile contents"""
        sector_carriers = []
        cell_sc_pattern = re.compile(
            rf'EUtranCellFDD={cell}\s+sectorCarrierRef.*?\[.*?\].*?\n((?:\s*>>>\s*sectorCarrierRef\s*=\s*ENodeBFunction=\d+,SectorCarrier=[\w\d]+\n?)*)',
            re.DOTALL
        )
        output_text = self.logfile_contents
        if cell_match := cell_sc_pattern.search(output_text):
            sector_carriers_text = cell_match.group(1)
            sc_pattern = re.compile(r'SectorCarrier=([\w\d]+)')
            sector_carriers = sc_pattern.findall(sector_carriers_text)
        return sector_carriers