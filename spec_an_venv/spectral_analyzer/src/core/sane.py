import paramiko
import time
import re
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Tuple
from contextlib import contextmanager
from ..utils.enm_data import enm_map
from ..gui.credentials_dialog import CredentialsDialog
from ..gui.enm_selection_dialog import EnmSelectionDialog

class SANE:
    def __init__(self, parent):
        self.parent = parent
        self.ssh = None
        self.channel = None
        self.output = ""
        self.enm_map = enm_map  # Add global enm_map reference
        self.prompts = {
            'menu': r'Please Enter Selection: >',
            'neid': r'Please enter NEID Number: >',
            'bash': r':~\$'
        }
    
    def get_enm_selection(self):
        dialog = EnmSelectionDialog(self.parent, self.enm_map)  # Pass enm_map to dialog
        self.parent.wait_window(dialog)
        return dialog.result
        
    def get_credentials(self):
        dialog = CredentialsDialog(self.parent)
        self.parent.wait_window(dialog)
        return dialog.result
    
    def sane_authentication(self, debug=False):
        hostname = '***REMOVED***'
        port = 22
        
        if debug:
            credentials = ('***REMOVED***', '***REMOVED***')
        else:
            credentials = self.get_credentials()
        if not credentials:
            return False, None
            
        username, password = credentials
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname, port, username, password)
            self.ssh = ssh
            return True, ssh
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            return False, None
            
    def get_enm_details(self, enb_id: str, is_s1: bool) -> Tuple[str, int]:
        """Returns tuple of (enm_name, neid) for given ENB ID"""
        if len(enb_id) < 3 or not enb_id[:3].isdigit():
            raise ValueError("Invalid eNB ID format")
    
        market = int(enb_id[:3])
        
        if 300 <= market < 600:
            market -= 300
        if 600 <= market < 900:
            market -= 600
    
        if 14 <= market <= 19:
            choice = self.get_enm_selection()
            if choice == "ENM1":
                enm_name = "***REMOVED***"
            elif choice == "ENM2":
                enm_name = "***REMOVED***"
            else:
                raise ValueError("ENM selection cancelled")
                
            enm_info = self.enm_map.get(enm_name)
            return enm_name, enm_info.neid_s1 if is_s1 else enm_info.neid_s2
    
        for enm_name, enm_info in self.enm_map.items():
            if market in enm_info.markets:
                return enm_name, enm_info.neid_s1 if is_s1 else enm_info.neid_s2
    
        return "DEFAULT", market
        
    def sane_select(self, enm_name, enm_server_id):
        if not self.ssh:
            raise ConnectionError("Not connected to SANE")
            
        try:
            self.parent.log_debug(f"Opening session for ENM {enm_name} ({enm_server_id})")
            channel = self.ssh.get_transport().open_session()
            channel.get_pty()
            channel.invoke_shell()
            
            # Wait for menu prompt
            self._wait_for_prompt(channel, 'menu')
            self.parent.log_debug("Sending menu selection: 5")
            channel.send('5')
            
            # Wait for NEID prompt
            self._wait_for_prompt(channel, 'neid')
            self.parent.log_debug(f"Sending NEID: {enm_server_id}")
            channel.send(f'{enm_server_id}\n')

            # Wait for bash prompt
            self._wait_for_prompt(channel, 'bash')
            self.parent.log_debug("Session established")
            
            self.channel = channel
            return channel
            
        except Exception as e:
            self.parent.log_debug(f"ERROR: {str(e)}")
            messagebox.showerror("ENM Connection Error", str(e))
            return None
            
    def _wait_for_prompt(self, channel, prompt_type, timeout=30):

        self.parent.log_debug(f"Waiting for {prompt_type} prompt...")
        self.output = ""
        start_time = time.time()
        last_output_time = time.time()
        
        while True:
            current_time = time.time()
            
            # Check for overall timeout
            if current_time - start_time > timeout:
                self.parent.log_debug(f"TIMEOUT! Full output:\n{self.output}")
                raise TimeoutError(f"Timeout waiting for {prompt_type} prompt")
            
            # Check for data
            if channel.recv_ready():
                new_data = channel.recv(65535).decode()
                self.output += new_data
                last_output_time = current_time
                # self.parent.log_debug(f"Received chunk: {new_data}")
                
                if re.search(self.prompts[prompt_type], self.output):
                    self.parent.log_debug(f"Found {prompt_type} prompt")
                    time.sleep(0.5)  # Allow buffer to settle
                    return True
            
            # Small delay between checks
            time.sleep(0.1)
            
            # If no new data for 5 seconds, check if we missed prompt
            if current_time - last_output_time > 5:
                if re.search(self.prompts[prompt_type], self.output):
                    self.parent.log_debug(f"Found {prompt_type} prompt after delay")
                    return True
                
def close(self):
    """Close the SSH connection and clean up resources."""
    try:
        if self.channel and not self.channel.closed:
            self.channel.close()
            self.logger.debug("SSH channel closed.")
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            self.client.close()
            self.logger.debug("SSH client closed.")
    except Exception as e:
        self.logger.error(f"Error closing SANE connection: {e}")